"""
Hosts and Clusters API Routes
"""
from flask import Blueprint, jsonify, request, Response
import pandas as pd
import os
from datetime import datetime

from utils.db import get_combined_data, get_db_connection

hosts_bp = Blueprint('hosts', __name__, url_prefix='/api')


def clean_numeric_columns(df, columns):
    """Clean numeric columns in dataframe"""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


def get_host_metrics(vhost):
    """Build host metrics dictionary from vHost data"""
    host_metrics = {}
    
    for _, host in vhost.iterrows():
        host_name = host.get('Host', 'Unknown')
        physical_cores = int(host['# Cores']) if host['# Cores'] > 0 else int(host['# CPU'] * host['Cores per CPU'])
        physical_ram_gb = round(host['# Memory'] / 1024, 2)
        
        vcpu_pcore_ratio = round(host['# vCPUs'] / physical_cores, 2) if physical_cores > 0 else 0
        vram_gb = round(host['vRAM'] / 1024, 2)
        vram_pram_ratio = round(vram_gb / physical_ram_gb, 2) if physical_ram_gb > 0 else 0
        
        # Handle NaN values
        dc_name = host.get('Datacenter', '')
        cl_name = host.get('Cluster', '')
        cpu_model = host.get('CPU Model', '')
        esxi_ver = host.get('ESX Version', '')
        src_name = host.get('Source', '')
        
        if pd.isna(dc_name): dc_name = ''
        if pd.isna(cl_name): cl_name = ''
        if pd.isna(cpu_model): cpu_model = ''
        if pd.isna(esxi_ver): esxi_ver = ''
        if pd.isna(src_name): src_name = ''
        
        host_metrics[host_name] = {
            'physical_cores': physical_cores,
            'physical_ram_gb': physical_ram_gb,
            'cpu_sockets': int(host['# CPU']),
            'cores_per_socket': int(host['Cores per CPU']),
            'cpu_model': cpu_model,
            'esxi_version': esxi_ver,
            'datacenter': dc_name,
            'cluster': cl_name,
            'source': src_name,
            'cpu_usage_pct': round(host['CPU usage %'], 1),
            'ram_usage_pct': round(host['Memory usage %'], 1),
            'vcpu_count': int(host['# vCPUs']),
            'vram_gb': vram_gb,
            'vcpu_pcore_ratio': vcpu_pcore_ratio,
            'vram_pram_ratio': vram_pram_ratio
        }
    
    return host_metrics


def build_hierarchy(vhost, vinfo, host_metrics):
    """Build hierarchical datacenter/cluster/host structure"""
    hierarchy = {}
    
    # Initialize from vHost
    for _, host in vhost.iterrows():
        host_name = host.get('Host', 'Unknown')
        source = host.get('Source', 'Unknown')
        datacenter = host.get('Datacenter', 'Unknown Datacenter')
        cluster = host.get('Cluster', '')
        
        if pd.isna(cluster) or cluster == '' or cluster == 'nan':
            cluster = 'Standalone Hosts'
        
        if source not in hierarchy:
            hierarchy[source] = {'datacenters': {}}
        
        if datacenter not in hierarchy[source]['datacenters']:
            hierarchy[source]['datacenters'][datacenter] = {
                'clusters': {},
                'total_vms': 0,
                'powered_on': 0,
                'total_vcpu': 0,
                'total_ram_gb': 0
            }
        
        dc = hierarchy[source]['datacenters'][datacenter]
        
        if cluster not in dc['clusters']:
            dc['clusters'][cluster] = {
                'hosts': {},
                'total_vms': 0,
                'powered_on': 0,
                'total_vcpu': 0,
                'total_ram_gb': 0,
                'total_physical_cores': 0,
                'total_physical_ram_gb': 0,
                'avg_cpu_usage_pct': 0,
                'avg_ram_usage_pct': 0
            }
        
        cl = dc['clusters'][cluster]
        
        if host_name not in cl['hosts']:
            hm = host_metrics.get(host_name, {
                'physical_cores': 0, 'physical_ram_gb': 0,
                'cpu_sockets': 0, 'cores_per_socket': 0,
                'cpu_model': '', 'esxi_version': '', 'source': source,
                'cpu_usage_pct': 0, 'ram_usage_pct': 0,
                'vcpu_count': 0, 'vram_gb': 0,
                'vcpu_pcore_ratio': 0, 'vram_pram_ratio': 0
            })
            cl['hosts'][host_name] = {
                'vms': [],
                'total_vms': 0,
                'powered_on': 0,
                'total_vcpu': 0,
                'total_ram_gb': 0,
                **hm
            }
            cl['total_physical_cores'] += hm['physical_cores']
            cl['total_physical_ram_gb'] += hm['physical_ram_gb']
    
    # Add VMs
    for _, row in vinfo.iterrows():
        source = row.get('Source', 'Unknown')
        datacenter = row.get('Datacenter', 'Unknown Datacenter')
        cluster = row.get('Cluster', 'Unknown Cluster')
        host = row.get('Host', 'Unknown Host')
        vm_name = row.get('VM', '')
        powerstate = row.get('Powerstate', 'poweredOff')
        
        if pd.isna(cluster) or cluster == 'nan':
            cluster = 'Standalone Hosts'
        
        # Ensure hierarchy exists
        if source not in hierarchy:
            hierarchy[source] = {'datacenters': {}}
        if datacenter not in hierarchy[source]['datacenters']:
            hierarchy[source]['datacenters'][datacenter] = {
                'clusters': {}, 'total_vms': 0, 'powered_on': 0,
                'total_vcpu': 0, 'total_ram_gb': 0
            }
        
        dc = hierarchy[source]['datacenters'][datacenter]
        
        if cluster not in dc['clusters']:
            dc['clusters'][cluster] = {
                'hosts': {}, 'total_vms': 0, 'powered_on': 0,
                'total_vcpu': 0, 'total_ram_gb': 0,
                'total_physical_cores': 0, 'total_physical_ram_gb': 0,
                'avg_cpu_usage_pct': 0, 'avg_ram_usage_pct': 0
            }
        
        cl = dc['clusters'][cluster]
        
        if host not in cl['hosts']:
            hm = host_metrics.get(host, {
                'physical_cores': 0, 'physical_ram_gb': 0,
                'cpu_sockets': 0, 'cores_per_socket': 0,
                'cpu_model': '', 'esxi_version': '', 'source': source,
                'cpu_usage_pct': 0, 'ram_usage_pct': 0,
                'vcpu_count': 0, 'vram_gb': 0,
                'vcpu_pcore_ratio': 0, 'vram_pram_ratio': 0
            })
            cl['hosts'][host] = {
                'vms': [], 'total_vms': 0, 'powered_on': 0,
                'total_vcpu': 0, 'total_ram_gb': 0, **hm
            }
            cl['total_physical_cores'] += hm['physical_cores']
            cl['total_physical_ram_gb'] += hm['physical_ram_gb']
        
        h = cl['hosts'][host]
        
        # Add VM
        vm_data = {
            'name': vm_name,
            'powerstate': powerstate,
            'vcpu': int(row['CPUs']),
            'ram_gb': round(row['Memory'] / 1024, 2),
            'disk_gb': round(row['Total disk capacity MiB'] / 1024, 2),
            'os': row.get('OS according to the configuration file', '')
        }
        h['vms'].append(vm_data)
        
        # Update metrics
        h['total_vms'] += 1
        h['total_vcpu'] += int(row['CPUs'])
        h['total_ram_gb'] += round(row['Memory'] / 1024, 2)
        if powerstate == 'poweredOn':
            h['powered_on'] += 1
        
        cl['total_vms'] += 1
        cl['total_vcpu'] += int(row['CPUs'])
        cl['total_ram_gb'] += round(row['Memory'] / 1024, 2)
        if powerstate == 'poweredOn':
            cl['powered_on'] += 1
        
        dc['total_vms'] += 1
        dc['total_vcpu'] += int(row['CPUs'])
        dc['total_ram_gb'] += round(row['Memory'] / 1024, 2)
        if powerstate == 'poweredOn':
            dc['powered_on'] += 1
    
    return hierarchy


def calculate_aggregated_metrics(hierarchy):
    """Calculate aggregated metrics for clusters and datacenters"""
    for source_name, source_data in hierarchy.items():
        for dc_name, dc_data in source_data['datacenters'].items():
            dc_data['total_physical_cores'] = 0
            dc_data['total_physical_ram_gb'] = 0
            dc_data['avg_cpu_usage_pct'] = 0
            dc_data['avg_ram_usage_pct'] = 0
            dc_cpu_sum = 0
            dc_ram_sum = 0
            dc_host_count = 0
            
            for cl_name, cl_data in dc_data['clusters'].items():
                host_count = len(cl_data['hosts'])
                cl_data['host_count'] = host_count
                
                if host_count > 0:
                    cpu_usage_sum = 0
                    ram_usage_sum = 0
                    total_vcpu_from_hosts = 0
                    total_vram_from_hosts = 0
                    
                    for host_name, host_data in cl_data['hosts'].items():
                        cpu_usage_sum += host_data.get('cpu_usage_pct', 0)
                        ram_usage_sum += host_data.get('ram_usage_pct', 0)
                        total_vcpu_from_hosts += host_data.get('vcpu_count', 0)
                        total_vram_from_hosts += host_data.get('vram_gb', 0)
                    
                    cl_data['avg_cpu_usage_pct'] = round(cpu_usage_sum / host_count, 1)
                    cl_data['avg_ram_usage_pct'] = round(ram_usage_sum / host_count, 1)
                    
                    if cl_data['total_physical_cores'] > 0:
                        cl_data['vcpu_pcore_ratio'] = round(total_vcpu_from_hosts / cl_data['total_physical_cores'], 2)
                    else:
                        cl_data['vcpu_pcore_ratio'] = 0
                    
                    if cl_data['total_physical_ram_gb'] > 0:
                        cl_data['vram_pram_ratio'] = round(total_vram_from_hosts / cl_data['total_physical_ram_gb'], 2)
                    else:
                        cl_data['vram_pram_ratio'] = 0
                    
                    dc_cpu_sum += cpu_usage_sum
                    dc_ram_sum += ram_usage_sum
                    dc_host_count += host_count
                
                dc_data['total_physical_cores'] += cl_data['total_physical_cores']
                dc_data['total_physical_ram_gb'] += cl_data['total_physical_ram_gb']
            
            dc_data['cluster_count'] = len(dc_data['clusters'])
            dc_data['host_count'] = dc_host_count
            
            if dc_host_count > 0:
                dc_data['avg_cpu_usage_pct'] = round(dc_cpu_sum / dc_host_count, 1)
                dc_data['avg_ram_usage_pct'] = round(dc_ram_sum / dc_host_count, 1)
    
    return hierarchy


@hosts_bp.route('/hosts-clusters')
def api_hosts_clusters():
    """Get hierarchical datacenter/cluster/host structure with metrics"""
    try:
        vinfo = get_combined_data('vInfo').copy()
        vhost = get_combined_data('vHost').copy()
        
        # Clean numeric columns
        vinfo = clean_numeric_columns(vinfo, ['CPUs', 'Memory', 'Total disk capacity MiB'])
        vhost = clean_numeric_columns(vhost, [
            '# CPU', 'Cores per CPU', '# Cores', '# Memory',
            'CPU usage %', 'Memory usage %', '# vCPUs', 'vRAM'
        ])
        
        # Build hierarchy
        host_metrics = get_host_metrics(vhost)
        hierarchy = build_hierarchy(vhost, vinfo, host_metrics)
        hierarchy = calculate_aggregated_metrics(hierarchy)
        
        return jsonify(hierarchy)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@hosts_bp.route('/inventory')
def api_inventory():
    """Get inventory tree structure"""
    vinfo = get_combined_data('vInfo')
    tree = {}
    
    for _, row in vinfo.iterrows():
        source = row['Source']
        datacenter = row.get('Datacenter', 'Unknown Datacenter')
        cluster = row.get('Cluster', 'Unknown Cluster')
        host = row.get('Host', 'Unknown Host')
        vm_name = row['VM']
        vm_id = row.get('VM ID', '')
        power_state = row.get('Powerstate', 'poweredOff')
        
        if source not in tree:
            tree[source] = {}
        if datacenter not in tree[source]:
            tree[source][datacenter] = {}
        if cluster not in tree[source][datacenter]:
            tree[source][datacenter][cluster] = {}
        if host not in tree[source][datacenter][cluster]:
            tree[source][datacenter][cluster][host] = []
            
        tree[source][datacenter][cluster][host].append({
            'name': vm_name,
            'id': vm_id,
            'power_state': power_state
        })
        
    return jsonify(tree)


@hosts_bp.route('/host_hardware/<host_name>')
def api_host_hardware(host_name):
    """Get detailed hardware info for a specific host"""
    conn = get_db_connection()
    
    try:
        cursor = conn.execute("SELECT * FROM vHost WHERE Host=?", (host_name,))
        host_info = cursor.fetchone()
        if not host_info:
            return jsonify({'error': 'Host not found'}), 404
        
        host_dict = dict(host_info)
        
        # Get related data
        cursor = conn.execute("SELECT * FROM vHBA WHERE Host=?", (host_name,))
        hbas = [dict(row) for row in cursor.fetchall()]
        
        cursor = conn.execute("SELECT * FROM vNIC WHERE Host=?", (host_name,))
        nics = [dict(row) for row in cursor.fetchall()]
        
        try:
            cursor = conn.execute("SELECT * FROM vSC_VMK WHERE Host=?", (host_name,))
            vmks = [dict(row) for row in cursor.fetchall()]
        except:
            vmks = []

        try:
            cursor = conn.execute("SELECT * FROM vMultiPath WHERE Host=?", (host_name,))
            paths = [dict(row) for row in cursor.fetchall()]
        except:
            paths = []

        try:
            cursor = conn.execute("SELECT VM FROM vInfo WHERE Host=?", (host_name,))
            vm_names = [row[0] for row in cursor.fetchall()]
            
            if vm_names:
                placeholders = ','.join(['?'] * (len(vm_names) + 1))
                query = f"SELECT * FROM vHealth WHERE Name IN ({placeholders}) OR Message LIKE ?"
                params = vm_names + [host_name, f"%{host_name}%"]
                cursor = conn.execute(query, params)
                health = [dict(row) for row in cursor.fetchall()]
            else:
                health = []
        except:
            health = []
            vm_names = []

        try:
            if vm_names:
                placeholders = ','.join(['?'] * len(vm_names))
                cursor = conn.execute(f'SELECT * FROM vPartition WHERE VM IN ({placeholders}) AND "Free %" < 10', vm_names)
                partitions = [dict(row) for row in cursor.fetchall()]
            else:
                partitions = []
        except:
            partitions = []

        try:
            if vm_names:
                placeholders = ','.join(['?'] * len(vm_names))
                cursor = conn.execute(f"SELECT * FROM vSnapshot WHERE VM IN ({placeholders})", vm_names)
                snapshots = [dict(row) for row in cursor.fetchall()]
            else:
                snapshots = []
        except:
            snapshots = []

        return jsonify({
            'hardware': host_dict,
            'hbas': hbas,
            'nics': nics,
            'vmks': vmks,
            'storage_paths': paths,
            'health': health,
            'partitions': partitions,
            'snapshots': snapshots
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
