"""
Reports API Routes - Zombie disks, resource usage, OS distribution, etc.
"""
from flask import Blueprint, jsonify, request, Response
import pandas as pd
import re
import os
from datetime import datetime, timedelta

from utils.db import get_combined_data, get_db_connection
import config as cfg

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@reports_bp.route('/zombie-disks')
def api_zombie_disks():
    """Get zombie disks with database analysis"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vHealth'")
        if not cursor.fetchone():
            return jsonify({'disk_count': 0, 'total_wasted_gb': 0, 'vm_count': 0, 'disks': []})

        zombies_df = pd.read_sql_query(
            "SELECT * FROM vHealth WHERE Message LIKE '%Zombie%' OR Message LIKE '%zombie%'", conn
        )
        
        if zombies_df.empty:
            return jsonify({'disk_count': 0, 'total_wasted_gb': 0, 'vm_count': 0, 'disks': []})

        try:
            vdatastore = pd.read_sql_query('SELECT Name, "Cluster name" FROM vDatastore', conn)
        except:
            vdatastore = pd.DataFrame(columns=['Name', 'Cluster name'])

        results = []
        
        for _, row in zombies_df.iterrows():
            message = str(row['Message'])
            name_field = str(row.get('Name', ''))
            
            datastore = 'Unknown'
            folder = 'Unknown'
            filename = ''
            full_path = message
            
            if name_field and name_field != '':
                match = re.search(r'\[(.*?)\]\s+(.*?)\/(.*?\.vmdk)', name_field, re.IGNORECASE)
                if match:
                    datastore = match.group(1).strip()
                    folder = match.group(2).strip()
                    filename = match.group(3).strip()
                    full_path = name_field
            
            if datastore == 'Unknown':
                match = re.search(r'\[(.*?)\]\s+(.*?)\/(.*?\.vmdk)', message, re.IGNORECASE)
                if match:
                    datastore = match.group(1).strip()
                    folder = match.group(2).strip()
                    filename = match.group(3).strip()
                    full_path = f"[{datastore}] {folder}/{filename}"
                else:
                    match = re.search(r'(.*?\.vmdk)', message, re.IGNORECASE)
                    if match:
                        filename = match.group(1).strip()
                        full_path = filename
            
            cluster = '-'
            if datastore != 'Unknown' and len(vdatastore) > 0:
                ds_match = vdatastore[vdatastore['Name'] == datastore]
                if not ds_match.empty:
                    cluster_val = ds_match.iloc[0]['Cluster name']
                    if pd.notna(cluster_val) and str(cluster_val).strip() != '':
                        cluster = str(cluster_val).strip()
            
            zombie_reason = "Disk dosyası datastore'da bulundu ancak artık hiçbir VM'e bağlı değil"
            if 'not attached' in message.lower():
                zombie_reason = "Disk hiçbir VM'e bağlı değil (orphaned)"
            elif folder != 'Unknown':
                zombie_reason = f"VM klasörü '{folder}' - VM silinmiş disk kalmış"
                
            results.append({
                'VM': folder,
                'Datastore': datastore,
                'Cluster': cluster,
                'Filename': filename if filename else 'Bilinmiyor',
                'Full_Path': full_path,
                'Reason': zombie_reason,
                'Source': row.get('Source', '')
            })

        return jsonify({
            'disk_count': len(results),
            'total_wasted_gb': 0,
            'vm_count': len(set(r['VM'] for r in results if r['VM'] != 'Unknown')),
            'disks': results
        })
        
    except Exception as e:
        print(f"Zombie Disk Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'disk_count': 0, 'total_wasted_gb': 0, 'vm_count': 0, 'disks': []})
    finally:
        conn.close()


@reports_bp.route('/resource-usage')
def api_resource_usage():
    """Get resource usage by cluster/host"""
    vinfo = get_combined_data('vInfo').copy()
    
    is_on = vinfo['Powerstate'] == 'poweredOn'
    is_off = vinfo['Powerstate'] == 'poweredOff'
    
    for col in ['CPUs', 'Memory', 'Total disk capacity MiB']:
        vinfo[col] = pd.to_numeric(vinfo[col], errors='coerce').fillna(0)

    vinfo['vm_on'] = is_on.astype(int)
    vinfo['vm_off'] = is_off.astype(int)
    vinfo['cpu_on'] = vinfo['CPUs'] * vinfo['vm_on']
    vinfo['cpu_off'] = vinfo['CPUs'] * vinfo['vm_off']
    vinfo['ram_on'] = vinfo['Memory'] * vinfo['vm_on']
    vinfo['ram_off'] = vinfo['Memory'] * vinfo['vm_off']
    vinfo['disk_on'] = vinfo['Total disk capacity MiB'] * vinfo['vm_on']
    vinfo['disk_off'] = vinfo['Total disk capacity MiB'] * vinfo['vm_off']
    
    agg_dict = {
        'vm_on': 'sum', 'vm_off': 'sum',
        'cpu_on': 'sum', 'cpu_off': 'sum',
        'ram_on': 'sum', 'ram_off': 'sum',
        'disk_on': 'sum', 'disk_off': 'sum'
    }
    
    cluster_usage = vinfo.groupby(['Source', 'Cluster']).agg(agg_dict).reset_index()
    for col in ['ram_on', 'ram_off', 'disk_on', 'disk_off']:
        cluster_usage[col] = round(cluster_usage[col] / 1024, 2)
        
    host_usage = vinfo.groupby(['Source', 'Cluster', 'Host']).agg(agg_dict).reset_index()
    for col in ['ram_on', 'ram_off', 'disk_on', 'disk_off']:
        host_usage[col] = round(host_usage[col] / 1024, 2)
    
    return jsonify({
        'by_cluster': cluster_usage.fillna(0).to_dict('records'),
        'by_host': host_usage.fillna(0).to_dict('records')
    })


@reports_bp.route('/os-distribution')
def api_os_distribution():
    """Get OS distribution"""
    vinfo = get_combined_data('vInfo')
    
    os_dist = vinfo.groupby('OS according to the configuration file').agg({
        'VM': 'count',
        'CPUs': 'sum',
        'Memory': 'sum'
    }).reset_index()
    
    os_dist.columns = ['OS', 'VM Count', 'Total CPUs', 'Total Memory (MiB)']
    os_dist = os_dist.sort_values('VM Count', ascending=False)
    
    return jsonify(os_dist.fillna('').to_dict('records'))


@reports_bp.route('/reserved')
def api_reserved_resources():
    """Get list of VMs with CPU or Memory reservations"""
    vinfo = get_combined_data('vInfo')[['VM', 'Powerstate', 'Cluster', 'Host', 'Source', 'VM ID']]
    vcpu = get_combined_data('vCPU')
    vmemory = get_combined_data('vMemory')
    
    cpu_res_col = next((c for c in vcpu.columns if 'Reservation' in c and 'Limit' not in c), None)
    mem_res_col = next((c for c in vmemory.columns if 'Reservation' in c and 'Limit' not in c), None)
    
    reserved_vms = {}
    
    if cpu_res_col:
        vcpu['ReservationVal'] = pd.to_numeric(vcpu[cpu_res_col], errors='coerce').fillna(0)
        cpu_reserved = vcpu[vcpu['ReservationVal'] > 0]
        
        for _, row in cpu_reserved.iterrows():
            key = f"{row['VM']}_{row.get('VM ID', '')}"
            if key not in reserved_vms:
                reserved_vms[key] = {'VM': row['VM'], 'VM ID': row.get('VM ID', ''), 'Source': row.get('Source', '')}
            reserved_vms[key]['cpu_reserved_mhz'] = row['ReservationVal']
            reserved_vms[key]['cpu_limit'] = row.get('Limit', 'Unlimited')

    if mem_res_col:
        vmemory['ReservationVal'] = pd.to_numeric(vmemory[mem_res_col], errors='coerce').fillna(0)
        mem_reserved = vmemory[vmemory['ReservationVal'] > 0]
        
        for _, row in mem_reserved.iterrows():
            key = f"{row['VM']}_{row.get('VM ID', '')}"
            if key not in reserved_vms:
                reserved_vms[key] = {'VM': row['VM'], 'VM ID': row.get('VM ID', ''), 'Source': row.get('Source', '')}
            reserved_vms[key]['mem_reserved_mb'] = row['ReservationVal']
            reserved_vms[key]['mem_limit'] = row.get('Limit', 'Unlimited')
            
    result = []
    for key, val in reserved_vms.items():
        info = vinfo[(vinfo['VM'] == val['VM']) & (vinfo['Source'] == val['Source'])]
        if not info.empty:
            vm_info = info.iloc[0].to_dict()
            val.update({
                'Powerstate': vm_info.get('Powerstate', ''),
                'Cluster': vm_info.get('Cluster', ''),
                'Host': vm_info.get('Host', '')
            })
        else:
            val.update({'Powerstate': 'Unknown', 'Cluster': '-', 'Host': '-'})
        result.append(val)
        
    return jsonify(result)


@reports_bp.route('/disk-waste')
def api_disk_waste():
    """Detailed disk waste analysis"""
    try:
        vdisk = get_combined_data('vDisk').copy()
        vinfo = get_combined_data('vInfo')
        
        vdisk['Capacity MiB'] = pd.to_numeric(vdisk['Capacity MiB'], errors='coerce').fillna(0)
        
        waste_analysis = vdisk.merge(vinfo[['VM', 'Powerstate', 'Source']], on='VM', how='left', suffixes=('', '_info'))
        
        waste_disks = []
        
        # Thick provisioned large disks on powered off VMs
        thick_off = waste_analysis[
            (waste_analysis['Thin'] == False) & 
            (waste_analysis['Powerstate'] == 'poweredOff') &
            (waste_analysis['Capacity MiB'] > 10240)
        ]
        
        for _, disk in thick_off.iterrows():
            capacity_gb = round(disk['Capacity MiB'] / 1024, 2)
            waste_disks.append({
                'vm': disk['VM'],
                'disk_name': disk['Disk'],
                'waste_type': 'THICK_POWERED_OFF',
                'capacity_gb': capacity_gb,
                'estimated_waste_gb': capacity_gb * 0.7,
                'thin': disk['Thin'],
                'source': disk.get('Source_info') or disk.get('Source', '')
            })
        
        # Very large thick disks
        large_thick = waste_analysis[
            (waste_analysis['Thin'] == False) &
            (waste_analysis['Capacity MiB'] > 102400)
        ]
        
        for _, disk in large_thick.iterrows():
            capacity_gb = round(disk['Capacity MiB'] / 1024, 2)
            waste_disks.append({
                'vm': disk['VM'],
                'disk_name': disk['Disk'],
                'waste_type': 'THICK_LARGE',
                'capacity_gb': capacity_gb,
                'estimated_waste_gb': capacity_gb * 0.3,
                'thin': disk['Thin'],
                'source': disk.get('Source_info') or disk.get('Source', '')
            })
        
        total_waste_gb = sum([d['estimated_waste_gb'] for d in waste_disks])
        
        return jsonify({
            'total_wasted_gb': round(total_waste_gb, 2),
            'disk_count': len(waste_disks),
            'disks': waste_disks
        })
    except Exception as e:
        print(f"Error in disk waste analysis: {e}")
        return jsonify({'total_wasted_gb': 0, 'disk_count': 0, 'disks': []})


@reports_bp.route('/pdf/<report_type>')
def api_export_pdf(report_type):
    """Generate PDF report with actual optimization data"""
    from pdf_generator import generate_optimization_pdf
    from routes.optimization import (
        check_cpu_underutilization, check_eol_os, check_old_hw, 
        check_vm_tools, check_old_snapshots, check_legacy_nics, 
        get_zombie_vms, safe_merge_vinfo
    )
    
    try:
        # Load necessary data for all checks
        vinfo = get_combined_data('vInfo').copy()
        vcpu = get_combined_data('vCPU').copy()
        vtools = get_combined_data('vTools').copy()
        vsnapshot = get_combined_data('vSnapshot').copy()
        vnetwork = get_combined_data('vNetwork').copy()
        vhost = get_combined_data('vHost').copy()

        # Helper data
        vhost_info = {row['Host']: {'speed': row.get('Speed', 2400)} for _, row in vhost.iterrows()}
        vhost_versions = {
            row['Host']: 13 if '6.5' in str(row.get('ESX Version', '')) 
            else 14 if '6.7' in str(row.get('ESX Version', '')) 
            else 19 if '7.0' in str(row.get('ESX Version', '')) or '8.0' in str(row.get('ESX Version', ''))
            else 17 for _, row in vhost.iterrows()
        }

        # Core merged data
        vcpu = safe_merge_vinfo(vcpu, vinfo)
        vtools = safe_merge_vinfo(vtools, vinfo)
        vsnapshot = safe_merge_vinfo(vsnapshot, vinfo)
        vnetwork = safe_merge_vinfo(vnetwork, vinfo)

        # Run all checks
        all_recs = []
        all_recs.extend(check_cpu_underutilization(vcpu, vhost_info))
        all_recs.extend(check_eol_os(vinfo))
        all_recs.extend(check_old_hw(vinfo, vhost_versions))
        all_recs.extend(check_vm_tools(vtools, vinfo))
        all_recs.extend(check_old_snapshots(vsnapshot))
        all_recs.extend(check_legacy_nics(vnetwork))
        all_recs.extend(get_zombie_vms())

        # Filter by report_type if needed
        if report_type != 'all' and report_type != 'rightsizing':
            # Map frontend types to backend types if they differ
            type_map = {
                'diskwaste': 'ZOMBIE_DISK',
                'zombies': 'ZOMBIE_DISK'
            }
            target_type = type_map.get(report_type, report_type)
            filtered_data = [r for r in all_recs if r['type'] == target_type]
        else:
            filtered_data = all_recs

        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend', 'images', 'logo.png')
        if not os.path.exists(logo_path):
             logo_path = None # Fallback if logo missing
        
        pdf_buffer = generate_optimization_pdf(filtered_data, report_type, logo_path)
        
        filename = f"RVTools_Optimization_{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{filename}"',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"PDF Export Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
