"""
VM (Virtual Machines) API Routes
"""
from flask import Blueprint, jsonify, request
import pandas as pd

from utils.db import load_excel_data, get_combined_data

vms_bp = Blueprint('vms', __name__, url_prefix='/api')


# OS Type classification patterns
DESKTOP_PATTERNS = ['windows 7', 'windows 8', 'windows 10', 'windows 11', 
                   'windows xp', 'windows vista', 'macos', 'mac os', 'ubuntu desktop']
SERVER_PATTERNS = ['server', 'centos', 'rhel', 'red hat', 'debian', 'suse', 
                  'oracle linux', 'freebsd', 'vmware', 'esxi', 'photon']


def classify_os_type(os_str):
    """Classify OS as Desktop (Dsk) or Server (Srv)"""
    if pd.isna(os_str) or not os_str:
        return 'Unknown'
    os_lower = str(os_str).lower()
    
    for pattern in DESKTOP_PATTERNS:
        if pattern in os_lower:
            return 'Dsk'
    for pattern in SERVER_PATTERNS:
        if pattern in os_lower:
            return 'Srv'
    if 'linux' in os_lower:
        return 'Srv'
    return 'Unknown'


@vms_bp.route('/vms')
def api_vms():
    """Get list of all VMs with advanced filtering and summary"""
    source = request.args.get('source', None)
    search = request.args.get('search', '').lower()
    powerstate = request.args.get('powerstate', None)
    cluster = request.args.get('cluster', None)
    host = request.args.get('host', None)
    os_name = request.args.get('os', None)
    os_type = request.args.get('os_type', None)
    pool = request.args.get('pool', None)
    pool_path = request.args.get('pool_path', None)
    
    # Load Initial Data
    if source:
        vinfo = load_excel_data(f"{source}.xlsx", 'vInfo').copy()
        vinfo['Source'] = source
    else:
        vinfo = get_combined_data('vInfo')
        
    if len(vinfo) == 0:
        return jsonify({
            'data': [], 
            'summary': {'count': 0, 'cpu': 0, 'memory_gb': 0, 'disk_gb': 0},
            'filter_options': {'clusters': [], 'hosts': [], 'os': [], 'sources': [], 'os_types': []}
        })

    # Add OS Type column
    vinfo['OS_Type'] = vinfo['OS according to the configuration file'].apply(classify_os_type)

    # Get all unique sources first
    all_sources = sorted(get_combined_data('vInfo')['Source'].dropna().unique().tolist()) if not source else [source]

    # Apply Filters progressively
    filtered = vinfo.copy()
    
    if search:
        filtered = filtered[filtered['VM'].str.lower().str.contains(search, na=False)]
    
    if powerstate:
        filtered = filtered[filtered['Powerstate'] == powerstate]
    
    # Calculate available options AFTER powerstate filter
    available_clusters = sorted(filtered['Cluster'].dropna().unique().tolist())
    available_hosts = sorted(filtered['Host'].dropna().unique().tolist())
    available_os = sorted(filtered['OS according to the configuration file'].dropna().unique().tolist())
    available_os_types = sorted(filtered['OS_Type'].dropna().unique().tolist())
    
    if cluster:
        filtered = filtered[filtered['Cluster'] == cluster]
        available_hosts = sorted(filtered['Host'].dropna().unique().tolist())
        available_os = sorted(filtered['OS according to the configuration file'].dropna().unique().tolist())
        available_os_types = sorted(filtered['OS_Type'].dropna().unique().tolist())
        
    if host:
        filtered = filtered[filtered['Host'] == host]
        available_os = sorted(filtered['OS according to the configuration file'].dropna().unique().tolist())
        available_os_types = sorted(filtered['OS_Type'].dropna().unique().tolist())
        
    if os_type:
        filtered = filtered[filtered['OS_Type'] == os_type]
        available_os = sorted(filtered['OS according to the configuration file'].dropna().unique().tolist())
        
    if os_name:
        filtered = filtered[filtered['OS according to the configuration file'] == os_name]

    if pool:
        filtered = filtered[filtered['Resource pool'].str.contains(pool, na=False)]

    if pool_path:
        filtered = filtered[filtered['Resource pool'] == pool_path]
    
    # Calculate Summary
    total_cpu = int(filtered['CPUs'].sum())
    total_memory_gb = round(filtered['Memory'].sum() / 1024, 2)
    total_disk_gb = round(filtered['Total disk capacity MiB'].sum() / 1024, 2)
    
    summary = {
        'count': len(filtered),
        'cpu': total_cpu,
        'memory_gb': total_memory_gb,
        'disk_gb': total_disk_gb
    }
    
    # Select Columns
    columns = ['VM', 'Powerstate', 'CPUs', 'Memory', 'Total disk capacity MiB', 
               'OS according to the configuration file', 'Host', 'Cluster', 'Datacenter', 
               'Primary IP Address', 'DNS Name', 'Annotation', 'Source', 'VM ID', 'OS_Type']
    
    available_cols = [c for c in columns if c in filtered.columns]
    data = filtered[available_cols].fillna('').to_dict('records')
    
    return jsonify({
        'data': data,
        'summary': summary,
        'filter_options': {
            'clusters': available_clusters,
            'hosts': available_hosts,
            'os': available_os,
            'os_types': available_os_types,
            'sources': all_sources
        }
    })


@vms_bp.route('/vm/<vm_name>')
def api_vm_detail(vm_name):
    """Get detailed info for a specific VM"""
    source = request.args.get('source', None)
    
    if source:
        vinfo = load_excel_data(f"{source}.xlsx", 'vInfo')
        vdisk = load_excel_data(f"{source}.xlsx", 'vDisk')
        vnetwork = load_excel_data(f"{source}.xlsx", 'vNetwork')
        vsnapshot = load_excel_data(f"{source}.xlsx", 'vSnapshot')
        vcpu = load_excel_data(f"{source}.xlsx", 'vCPU')
        vmemory = load_excel_data(f"{source}.xlsx", 'vMemory')
    else:
        vinfo = get_combined_data('vInfo')
        vdisk = get_combined_data('vDisk')
        vnetwork = get_combined_data('vNetwork')
        vsnapshot = get_combined_data('vSnapshot')
        vcpu = get_combined_data('vCPU')
        vmemory = get_combined_data('vMemory')
    
    # Get VM info
    vm_info = vinfo[vinfo['VM'] == vm_name]
    if len(vm_info) == 0:
        return jsonify({'error': 'VM not found'}), 404
    
    vm_info = vm_info.iloc[0].fillna('').to_dict()
    
    # Get related data
    vm_disks = vdisk[vdisk['VM'] == vm_name].fillna('').to_dict('records')
    vm_networks = vnetwork[vnetwork['VM'] == vm_name].fillna('').to_dict('records')
    vm_snapshots = vsnapshot[vsnapshot['VM'] == vm_name].fillna('').to_dict('records')
    vm_cpu = vcpu[vcpu['VM'] == vm_name].fillna('').to_dict('records')
    vm_memory = vmemory[vmemory['VM'] == vm_name].fillna('').to_dict('records')
    
    return jsonify({
        'info': vm_info,
        'disks': vm_disks,
        'networks': vm_networks,
        'snapshots': vm_snapshots,
        'cpu': vm_cpu,
        'memory': vm_memory
    })
