"""
DR (Disaster Recovery) Analysis Routes
"""
from flask import Blueprint, jsonify
import pandas as pd
from utils.db import get_db_connection

dr_bp = Blueprint('dr', __name__, url_prefix='/api')


# Common replica naming patterns
REPLICA_PATTERNS = ['_dr', '_replica', '_rep', '-dr', '-replica', '-rep', '_backup', '-backup']


def get_base_name(vm_name):
    """Extract base VM name by removing replica suffixes"""
    name = str(vm_name).lower()
    for pattern in REPLICA_PATTERNS:
        if pattern in name:
            return name.replace(pattern, '')
    return name


def match_replicas(production_vms, replica_candidates):
    """Match replica VMs with their production counterparts"""
    matched_pairs = []
    unmatched_replicas = []
    
    production_vms = production_vms.copy()
    replica_candidates = replica_candidates.copy()
    
    production_vms['BaseName'] = production_vms['VM'].apply(get_base_name)
    replica_candidates['BaseName'] = replica_candidates['VM'].apply(get_base_name)
    
    # Create lookup for production VMs
    prod_by_base = production_vms.groupby('BaseName').first().to_dict('index')
    
    for _, replica in replica_candidates.iterrows():
        base_name = replica['BaseName']
        
        # Check if there's a matching production VM
        if base_name in prod_by_base:
            prod = prod_by_base[base_name]
            # Only match if in different datacenter
            if replica['Datacenter'] != prod['Datacenter']:
                matched_pairs.append(create_pair_dict(prod, replica))
                continue
        
        # Check for VMs with same name in different DC
        same_name_prod = production_vms[
            (production_vms['VM'].str.lower() == replica['VM'].lower()) & 
            (production_vms['Datacenter'] != replica['Datacenter'])
        ]
        
        if len(same_name_prod) > 0:
            prod = same_name_prod.iloc[0]
            matched_pairs.append(create_pair_dict(prod, replica))
        else:
            # Check if this looks like a replica
            has_replica_pattern = any(p in replica['VM'].lower() for p in REPLICA_PATTERNS)
            if has_replica_pattern:
                unmatched_replicas.append({
                    'vm': replica['VM'],
                    'datacenter': replica['Datacenter'],
                    'cluster': replica['Cluster'],
                    'vcpu': int(replica['CPUs']),
                    'memory_gb': round(replica['Memory'] / 1024, 2),
                    'disk_gb': round(replica['DiskMiB'] / 1024, 2)
                })
    
    return matched_pairs, unmatched_replicas


def create_pair_dict(prod, replica):
    """Create a matched pair dictionary"""
    return {
        'production_vm': prod['VM'],
        'production_dc': prod['Datacenter'],
        'production_cluster': prod['Cluster'],
        'production_host': prod['Host'],
        'replica_vm': replica['VM'],
        'replica_dc': replica['Datacenter'],
        'replica_cluster': replica['Cluster'],
        'replica_host': replica['Host'],
        'vcpu': int(prod['CPUs']),
        'memory_gb': round(prod['Memory'] / 1024, 2),
        'disk_gb': round(prod['DiskMiB'] / 1024, 2),
        'os': prod['OS'],
        'source': prod['Source']
    }


def calculate_dc_flows(matched_pairs):
    """Calculate DC-to-DC replication flows"""
    dc_flows = {}
    for pair in matched_pairs:
        flow_key = f"{pair['production_dc']} → {pair['replica_dc']}"
        if flow_key not in dc_flows:
            dc_flows[flow_key] = {
                'source_dc': pair['production_dc'],
                'target_dc': pair['replica_dc'],
                'vm_count': 0,
                'total_vcpu': 0,
                'total_memory_gb': 0,
                'total_disk_gb': 0
            }
        dc_flows[flow_key]['vm_count'] += 1
        dc_flows[flow_key]['total_vcpu'] += pair['vcpu']
        dc_flows[flow_key]['total_memory_gb'] += pair['memory_gb']
        dc_flows[flow_key]['total_disk_gb'] += pair['disk_gb']
    return dc_flows


def calculate_dr_site_capacity(matched_pairs, vhost):
    """Calculate DR site capacity and readiness"""
    dr_sites = {}
    unique_dr_dcs = set(pair['replica_dc'] for pair in matched_pairs)
    
    for dc in unique_dr_dcs:
        dc_hosts = vhost[vhost['Datacenter'] == dc]
        if len(dc_hosts) > 0:
            total_cores = int(dc_hosts['Cores'].sum())
            total_memory_gb = round(dc_hosts['MemoryMB'].sum() / 1024, 2)
            avg_cpu_usage = round(dc_hosts['CPUUsage'].mean(), 1)
            avg_mem_usage = round(dc_hosts['MemUsage'].mean(), 1)
            
            # Calculate required resources
            required_vcpu = sum(p['vcpu'] for p in matched_pairs if p['replica_dc'] == dc)
            required_memory_gb = sum(p['memory_gb'] for p in matched_pairs if p['replica_dc'] == dc)
            required_disk_gb = sum(p['disk_gb'] for p in matched_pairs if p['replica_dc'] == dc)
            replicated_vm_count = len([p for p in matched_pairs if p['replica_dc'] == dc])
            
            # Available capacity
            available_cpu_pct = 100 - avg_cpu_usage
            available_mem_pct = 100 - avg_mem_usage
            
            # Capacity ratio
            cpu_capacity_ratio = (required_vcpu / total_cores * 100) if total_cores > 0 else 0
            mem_capacity_ratio = (required_memory_gb / total_memory_gb * 100) if total_memory_gb > 0 else 0
            
            # DR Readiness Score
            cpu_ready = min(100, available_cpu_pct / cpu_capacity_ratio * 100) if cpu_capacity_ratio > 0 else 100
            mem_ready = min(100, available_mem_pct / mem_capacity_ratio * 100) if mem_capacity_ratio > 0 else 100
            readiness_score = round((cpu_ready + mem_ready) / 2, 1)
            
            dr_sites[dc] = {
                'datacenter': dc,
                'host_count': int(len(dc_hosts)),
                'total_cores': int(total_cores),
                'total_memory_gb': float(total_memory_gb),
                'current_cpu_usage_pct': float(avg_cpu_usage),
                'current_mem_usage_pct': float(avg_mem_usage),
                'replicated_vm_count': int(replicated_vm_count),
                'required_vcpu': int(required_vcpu),
                'required_memory_gb': float(required_memory_gb),
                'required_disk_gb': float(required_disk_gb),
                'cpu_capacity_ratio': float(round(cpu_capacity_ratio, 1)),
                'mem_capacity_ratio': float(round(mem_capacity_ratio, 1)),
                'readiness_score': float(readiness_score),
                'failover_feasible': bool(readiness_score >= 80)
            }
    
    return dr_sites


@dr_bp.route('/dr-analysis')
def api_dr_analysis():
    """Disaster Recovery analysis - match replicas with production VMs"""
    conn = get_db_connection()
    
    try:
        # Load all VM data
        vinfo = pd.read_sql_query("""
            SELECT VM, Powerstate, CPUs, Memory, "Total disk capacity MiB" as DiskMiB,
                   Host, Cluster, Datacenter, Source, "OS according to the configuration file" as OS
            FROM vInfo
        """, conn)
        
        # Load host capacity data
        vhost = pd.read_sql_query("""
            SELECT Host, Datacenter, Cluster, "# CPU" as CPUs, "# Cores" as Cores,
                   "# Memory" as MemoryMB, "CPU usage %" as CPUUsage, "Memory usage %" as MemUsage,
                   Source
            FROM vHost
        """, conn)
        
        # Clean numeric columns
        for col in ['CPUs', 'Memory', 'DiskMiB']:
            vinfo[col] = pd.to_numeric(vinfo[col], errors='coerce').fillna(0)
        
        for col in ['CPUs', 'Cores', 'MemoryMB', 'CPUUsage', 'MemUsage']:
            vhost[col] = pd.to_numeric(vhost[col], errors='coerce').fillna(0)
        
        # Identify production and replica VMs
        production_vms = vinfo[vinfo['Powerstate'] == 'poweredOn'].copy()
        replica_candidates = vinfo[vinfo['Powerstate'] == 'poweredOff'].copy()
        
        # Match replicas
        matched_pairs, unmatched_replicas = match_replicas(production_vms, replica_candidates)
        
        # Calculate flows and capacity
        dc_flows = calculate_dc_flows(matched_pairs)
        dr_sites = calculate_dr_site_capacity(matched_pairs, vhost)
        
        # Calculate overall stats
        total_replicated = len(matched_pairs)
        total_production = len(production_vms)
        replication_coverage = round(total_replicated / total_production * 100, 1) if total_production > 0 else 0
        
        # Identify unprotected VMs
        replicated_prod_names = set(p['production_vm'] for p in matched_pairs)
        unprotected_vms = production_vms[~production_vms['VM'].isin(replicated_prod_names)]
        
        # Sort by resource usage
        unprotected_vms = unprotected_vms.copy()
        unprotected_vms['ResourceScore'] = (
            unprotected_vms['CPUs'] * 2 + 
            unprotected_vms['Memory'] / 1024 + 
            unprotected_vms['DiskMiB'] / 1024
        )
        unprotected_critical = unprotected_vms.nlargest(20, 'ResourceScore')[
            ['VM', 'Datacenter', 'Cluster', 'CPUs', 'Memory', 'DiskMiB', 'OS', 'Source']
        ].to_dict('records')
        
        # Format output
        for item in unprotected_critical:
            item['memory_gb'] = round(item['Memory'] / 1024, 2)
            item['disk_gb'] = round(item['DiskMiB'] / 1024, 2)
            item['vcpu'] = int(item['CPUs'])
            del item['Memory']
            del item['DiskMiB']
            del item['CPUs']
        
        return jsonify({
            'summary': {
                'total_production_vms': total_production,
                'total_replicated_vms': total_replicated,
                'replication_coverage_pct': replication_coverage,
                'unprotected_vm_count': len(unprotected_vms),
                'dc_flow_count': len(dc_flows),
                'dr_site_count': len(dr_sites)
            },
            'dc_flows': list(dc_flows.values()),
            'dr_sites': list(dr_sites.values()),
            'matched_pairs': matched_pairs[:100],
            'unmatched_replicas': unmatched_replicas[:50],
            'unprotected_critical': unprotected_critical
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
