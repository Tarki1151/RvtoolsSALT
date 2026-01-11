"""
RVTools Visualization Backend
Flask API server for serving RVTools data
"""

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
import pandas as pd
import os
from datetime import datetime, timedelta
import json
import sqlite3
import re
import glob
from io import BytesIO

import config as cfg
import ai_utils as ai

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def init_db():
    """Initialize SQLite database from Excel files"""
    print("Initializing Database...")
    conn = sqlite3.connect('rvtools.db')
    cursor = conn.cursor()
    
    # Clear existing data but keep custom_notes
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('custom_notes', 'sqlite_sequence');").fetchall()
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS \"{table[0]}\"")
    conn.commit()

    excel_files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    
    for file_path in excel_files:
        filename = os.path.basename(file_path)
        source_name = os.path.splitext(filename)[0]
        try:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name)
                    df['Source'] = source_name
                    
                    # Robust type conversion
                    for col in df.columns:
                        if pd.api.types.is_timedelta64_dtype(df[col]):
                            df[col] = df[col].astype(str)
                        elif pd.api.types.is_datetime64_any_dtype(df[col]):
                            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            # Catch complex objects like python timedeltas or mixed types
                            df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (timedelta, pd.Timedelta)) else x)

                    # Dynamic Schema Evolution
                    cursor.execute(f"PRAGMA table_info(\"{sheet_name}\")")
                    existing_cols = [row[1] for row in cursor.fetchall()]
                    
                    if existing_cols:
                        for col in df.columns:
                            if col not in existing_cols:
                                print(f"Adding column {col} to {sheet_name}")
                                cursor.execute(f"ALTER TABLE \"{sheet_name}\" ADD COLUMN \"{col}\" TEXT")
                        conn.commit()

                    # Write data
                    df.to_sql(sheet_name, conn, if_exists='append', index=False)
                except Exception as sheet_err:
                    print(f"Error importing sheet {sheet_name} from {filename}: {sheet_err}")
                
            print(f"Finished processing {filename}")
        except Exception as e:
            print(f"Error opening {filename}: {e}")
            import traceback
            traceback.print_exc()
            
    # Create custom_notes table if not exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS custom_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_name TEXT NOT NULL,
            note_content TEXT,
            updated_at TEXT,
            UNIQUE(target_type, target_name)
        )
    ''')
    conn.commit()
    conn.close()
    print("Database Initialized Successfully.")

@app.route('/api/notes', methods=['GET', 'POST'])
def api_notes():
    """Get or Save notes"""
    conn = sqlite3.connect('rvtools.db')
    conn.row_factory = sqlite3.Row
    
    if request.method == 'POST':
        try:
            data = request.json
            target_type = data.get('target_type')
            target_name = data.get('target_name')
            note_content = data.get('note_content')
            updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Upsert note
            conn.execute('''
                INSERT INTO custom_notes (target_type, target_name, note_content, updated_at) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(target_type, target_name) 
                DO UPDATE SET note_content=excluded.note_content, updated_at=excluded.updated_at
            ''', (target_type, target_name, note_content, updated_at))
            
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Note saved', 'updated_at': updated_at})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            conn.close()
            
    else: # GET request
        target_type = request.args.get('target_type')
        target_name = request.args.get('target_name')
        
        if not target_type or not target_name:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
            
        cursor = conn.execute('SELECT note_content, updated_at FROM custom_notes WHERE target_type=? AND target_name=?', (target_type, target_name))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({'note_content': row['note_content'], 'updated_at': row['updated_at']})
        else:
            return jsonify({'note_content': '', 'updated_at': None})

# Cache for Excel data
data_cache = {}

def load_excel_data(filename, sheet_name):
    """Load data from Excel file with caching"""
    cache_key = f"{filename}_{sheet_name}"
    filepath = os.path.join(DATA_DIR, filename)
    mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else None

    cached = data_cache.get(cache_key)
    if cached and cached.get('mtime') == mtime:
        return cached['df']

    df = pd.read_excel(filepath, sheet_name=sheet_name)
    # Convert datetime columns to string for JSON serialization
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]':
            df[col] = df[col].astype(str)

    data_cache[cache_key] = {'mtime': mtime, 'df': df}
    return df

def get_all_sources():
    """Get list of all Excel files in data directory"""
    sources = []
    for f in os.listdir(DATA_DIR):
        if f.endswith('.xlsx'):
            name = os.path.splitext(f)[0]
            sources.append({'filename': f, 'name': name})
    return sources

def get_combined_data(sheet_name):
    """Get combined data from all sources"""
    all_data = []
    for source in get_all_sources():
        df = load_excel_data(source['filename'], sheet_name).copy()
        df['Source'] = source['name']
        all_data.append(df)
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

@app.route('/api/reload', methods=['POST'])
def api_reload():
    """Clear cached Excel data and optionally rebuild SQLite DB."""
    try:
        payload = request.get_json(silent=True) or {}
        rebuild_db = bool(payload.get('rebuild_db', False))

        data_cache.clear()

        if rebuild_db:
            init_db()

        return jsonify({'status': 'success', 'rebuild_db': rebuild_db})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/sources')
def api_sources():
    """Get list of data sources (Excel files)"""
    return jsonify(get_all_sources())

@app.route('/api/stats')
def api_stats():
    """Get overall statistics"""
    sources = get_all_sources()
    stats = {
        'sources': [],
        'total': {
            'vms': 0,
            'powered_on': 0,
            'powered_off': 0,
            'templates': 0,
            'total_memory_gb': 0,
            'total_cpu': 0,
            'total_disk_gb': 0,
            'snapshots': 0,
            'old_snapshots': 0
        }
    }
    
    for source in sources:
        vinfo = load_excel_data(source['filename'], 'vInfo')
        vsnapshot = load_excel_data(source['filename'], 'vSnapshot')
        
        powered_on = len(vinfo[vinfo['Powerstate'] == 'poweredOn'])
        powered_off = len(vinfo[vinfo['Powerstate'] == 'poweredOff'])
        templates = len(vinfo[vinfo['Template'] == True])
        total_memory = vinfo['Memory'].sum() / 1024  # Convert to GB
        total_cpu = vinfo['CPUs'].sum()
        total_disk = vinfo['Total disk capacity MiB'].sum() / 1024  # Convert to GB
        
        # Count old snapshots (older than 7 days)
        old_snapshots = 0
        if len(vsnapshot) > 0:
            vsnapshot_copy = vsnapshot.copy()
            vsnapshot_copy['Date / time'] = pd.to_datetime(vsnapshot_copy['Date / time'], errors='coerce')
            seven_days_ago = datetime.now() - timedelta(days=cfg.SNAPSHOT_OLD_DAYS)
            old_snapshots = len(vsnapshot_copy[vsnapshot_copy['Date / time'] < seven_days_ago])
        
        source_stats = {
            'name': source['name'],
            'vms': len(vinfo),
            'powered_on': powered_on,
            'powered_off': powered_off,
            'templates': templates,
            'total_memory_gb': round(total_memory, 2),
            'total_cpu': int(total_cpu),
            'total_disk_gb': round(total_disk, 2),
            'snapshots': len(vsnapshot),
            'old_snapshots': old_snapshots
        }
        
        stats['sources'].append(source_stats)
        stats['total']['vms'] += len(vinfo)
        stats['total']['powered_on'] += powered_on
        stats['total']['powered_off'] += powered_off
        stats['total']['templates'] += templates
        stats['total']['total_memory_gb'] += round(total_memory, 2)
        stats['total']['total_cpu'] += int(total_cpu)
        stats['total']['total_disk_gb'] += round(total_disk, 2)
        stats['total']['snapshots'] += len(vsnapshot)
        stats['total']['old_snapshots'] += old_snapshots
    
    return jsonify(stats)

@app.route('/api/vms')
def api_vms():
    """Get list of all VMs with advanced filtering and summary"""
    source = request.args.get('source', None)
    search = request.args.get('search', '').lower()
    powerstate = request.args.get('powerstate', None)
    cluster = request.args.get('cluster', None)
    host = request.args.get('host', None)
    os_name = request.args.get('os', None)
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
            'filter_options': {'clusters': [], 'hosts': [], 'os': []}
        })

    # Prepare Filter Options (from FULL dataset before filtering, or after? 
    # Usually better to show options valid for current context, but let's show all valid options for the source)
    # Actually, dynamic filtering (faceted search) is better. Let's calculate options based on current filtered set 
    # OR provide global options. Let's provide global options for the selected source to avoid confusion.
    
    unique_clusters = sorted(vinfo['Cluster'].dropna().unique().tolist())
    unique_hosts = sorted(vinfo['Host'].dropna().unique().tolist())
    unique_os = sorted(vinfo['OS according to the configuration file'].dropna().unique().tolist())

    # Apply Filters
    if search:
        vinfo = vinfo[vinfo['VM'].str.lower().str.contains(search, na=False)]
    
    if powerstate:
        vinfo = vinfo[vinfo['Powerstate'] == powerstate]
        
    if cluster:
        vinfo = vinfo[vinfo['Cluster'] == cluster]
        
    if host:
        vinfo = vinfo[vinfo['Host'] == host]
        
    if os_name:
        vinfo = vinfo[vinfo['OS according to the configuration file'] == os_name]

    if pool:
        vinfo = vinfo[vinfo['Resource pool'].str.contains(pool, na=False)]

    if pool_path:
        vinfo = vinfo[vinfo['Resource pool'] == pool_path]
    
    # Calculate Summary
    total_cpu = int(vinfo['CPUs'].sum())
    total_memory_gb = round(vinfo['Memory'].sum() / 1024, 2)
    total_disk_gb = round(vinfo['Total disk capacity MiB'].sum() / 1024, 2)
    
    summary = {
        'count': len(vinfo),
        'cpu': total_cpu,
        'memory_gb': total_memory_gb,
        'disk_gb': total_disk_gb
    }
    
    # Select Columns
    columns = ['VM', 'Powerstate', 'CPUs', 'Memory', 'Total disk capacity MiB', 
               'OS according to the configuration file', 'Host', 'Cluster', 'Datacenter', 
               'Primary IP Address', 'DNS Name', 'Annotation', 'Source', 'VM ID']
    
    available_cols = [c for c in columns if c in vinfo.columns]
    data = vinfo[available_cols].fillna('').to_dict('records')
    
    return jsonify({
        'data': data,
        'summary': summary,
        'filter_options': {
            'clusters': unique_clusters,
            'hosts': unique_hosts,
            'os': unique_os
        }
    })

@app.route('/api/vm/<vm_name>')
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
    
    # Get disks
    vm_disks = vdisk[vdisk['VM'] == vm_name].fillna('').to_dict('records')
    
    # Get networks
    vm_networks = vnetwork[vnetwork['VM'] == vm_name].fillna('').to_dict('records')
    
    # Get snapshots
    vm_snapshots = vsnapshot[vsnapshot['VM'] == vm_name].fillna('').to_dict('records')
    
    # Get CPU info
    vm_cpu = vcpu[vcpu['VM'] == vm_name].fillna('').to_dict('records')
    
    # Get Memory info
    vm_memory = vmemory[vmemory['VM'] == vm_name].fillna('').to_dict('records')
    
    return jsonify({
        'info': vm_info,
        'disks': vm_disks,
        'networks': vm_networks,
        'snapshots': vm_snapshots,
        'cpu': vm_cpu,
        'memory': vm_memory
    })

@app.route('/api/reports/zombie-disks')
def api_zombie_disks():
    """Get zombie disks with database analysis"""
    conn = sqlite3.connect('rvtools.db')
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vHealth'")
        if not cursor.fetchone():
             return jsonify({'disk_count': 0, 'total_wasted_gb': 0, 'vm_count': 0, 'disks': []})

        zombies_df = pd.read_sql_query("SELECT * FROM vHealth WHERE Message LIKE '%Zombie%' OR Message LIKE '%zombie%'", conn)
        
        if zombies_df.empty:
            return jsonify({'disk_count': 0, 'total_wasted_gb': 0, 'vm_count': 0, 'disks': []})

        # Load vDatastore for cluster info
        try:
            vdatastore = pd.read_sql_query("SELECT Name, \"Cluster name\" FROM vDatastore", conn)
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
            
            # Parse from Name field first
            if name_field and name_field != '':
                import re
                match = re.search(r'\[(.*?)\]\s+(.*?)\/(.*?\.vmdk)', name_field, re.IGNORECASE)
                if match:
                    datastore = match.group(1).strip()
                    folder = match.group(2).strip()
                    filename = match.group(3).strip()
                    full_path = name_field
            
            # If not found in Name, try Message
            if datastore == 'Unknown':
                import re
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
            
            # Get cluster from vDatastore
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

@app.route('/api/reports/resource-usage')
def api_resource_usage():
    """Get resource usage by cluster/host separated by power state"""
    vinfo = get_combined_data('vInfo').copy()
    
    # Pre-calculate separate columns for On/Off states
    is_on = vinfo['Powerstate'] == 'poweredOn'
    is_off = vinfo['Powerstate'] == 'poweredOff'
    
    # Helper to clean numeric columns
    def clean_numeric(col):
        return pd.to_numeric(vinfo[col], errors='coerce').fillna(0)

    vinfo['CPUs'] = clean_numeric('CPUs')
    vinfo['Memory'] = clean_numeric('Memory')
    vinfo['Total disk capacity MiB'] = clean_numeric('Total disk capacity MiB')

    vinfo['vm_on'] = is_on.astype(int)
    vinfo['vm_off'] = is_off.astype(int)
    
    vinfo['cpu_on'] = vinfo['CPUs'] * vinfo['vm_on']
    vinfo['cpu_off'] = vinfo['CPUs'] * vinfo['vm_off']
    
    vinfo['ram_on'] = vinfo['Memory'] * vinfo['vm_on']
    vinfo['ram_off'] = vinfo['Memory'] * vinfo['vm_off']
    
    vinfo['disk_on'] = vinfo['Total disk capacity MiB'] * vinfo['vm_on']
    vinfo['disk_off'] = vinfo['Total disk capacity MiB'] * vinfo['vm_off']
    
    # Aggregation dictionary
    agg_dict = {
        'vm_on': 'sum', 'vm_off': 'sum',
        'cpu_on': 'sum', 'cpu_off': 'sum',
        'ram_on': 'sum', 'ram_off': 'sum',
        'disk_on': 'sum', 'disk_off': 'sum'
    }
    
    # Group by Cluster
    cluster_usage = vinfo.groupby(['Source', 'Cluster']).agg(agg_dict).reset_index()
    
    # Convert units to GB for RAM and Disk
    for col in ['ram_on', 'ram_off']:
        cluster_usage[col] = round(cluster_usage[col] / 1024, 2)
    for col in ['disk_on', 'disk_off']:
        cluster_usage[col] = round(cluster_usage[col] / 1024, 2)
        
    # Group by Host
    host_usage = vinfo.groupby(['Source', 'Cluster', 'Host']).agg(agg_dict).reset_index()
    
    # Convert units to GB for Host
    for col in ['ram_on', 'ram_off']:
        host_usage[col] = round(host_usage[col] / 1024, 2)
    for col in ['disk_on', 'disk_off']:
        host_usage[col] = round(host_usage[col] / 1024, 2)
    
    return jsonify({
        'by_cluster': cluster_usage.fillna(0).to_dict('records'),
        'by_host': host_usage.fillna(0).to_dict('records')
    })

@app.route('/api/reports/os-distribution')
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

@app.route('/api/reports/reserved')
def api_reserved_resources():
    """Get list of VMs with CPU or Memory reservations"""
    vinfo = get_combined_data('vInfo')[['VM', 'Powerstate', 'Cluster', 'Host', 'Source', 'VM ID']]
    vcpu = get_combined_data('vCPU')
    vmemory = get_combined_data('vMemory')
    
    # Check if Reservation columns exist
    cpu_res_col = next((c for c in vcpu.columns if 'Reservation' in c and 'Limit' not in c), None) # 'Reservation' or 'Reservation MHz'
    mem_res_col = next((c for c in vmemory.columns if 'Reservation' in c and 'Limit' not in c), None) # 'Reservation' or 'Reservation MB'
    
    reserved_vms = {}
    
    # Process CPU Reservations
    if cpu_res_col:
        vcpu['ReservationVal'] = pd.to_numeric(vcpu[cpu_res_col], errors='coerce').fillna(0)
        cpu_reserved = vcpu[vcpu['ReservationVal'] > 0]
        
        for _, row in cpu_reserved.iterrows():
            key = f"{row['VM']}_{row.get('VM ID', '')}"
            if key not in reserved_vms:
                reserved_vms[key] = {'VM': row['VM'], 'VM ID': row.get('VM ID', ''), 'Source': row.get('Source', '')}
            reserved_vms[key]['cpu_reserved_mhz'] = row['ReservationVal']
            reserved_vms[key]['cpu_limit'] = row.get('Limit', 'Unlimited')

    # Process Memory Reservations
    if mem_res_col:
        vmemory['ReservationVal'] = pd.to_numeric(vmemory[mem_res_col], errors='coerce').fillna(0)
        mem_reserved = vmemory[vmemory['ReservationVal'] > 0]
        
        for _, row in mem_reserved.iterrows():
            key = f"{row['VM']}_{row.get('VM ID', '')}"
            if key not in reserved_vms:
                reserved_vms[key] = {'VM': row['VM'], 'VM ID': row.get('VM ID', ''), 'Source': row.get('Source', '')}
            reserved_vms[key]['mem_reserved_mb'] = row['ReservationVal']
            reserved_vms[key]['mem_limit'] = row.get('Limit', 'Unlimited')
            
    # Merge with vInfo for context
    result = []
    for key, val in reserved_vms.items():
        # Find matching info
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

@app.route('/api/reports/rightsizing')
def api_rightsizing():
    """Get right-sizing recommendations and health checks for VMs"""
    vinfo = get_combined_data('vInfo').copy()
    vsnapshot = get_combined_data('vSnapshot')
    
    # Try to load additional tables for health checks
    try: vtools = get_combined_data('vTools')
    except: vtools = pd.DataFrame()
    
    try: vnetwork = get_combined_data('vNetwork')
    except: vnetwork = pd.DataFrame()
    
    try: vcd = get_combined_data('vCD')
    except: vcd = pd.DataFrame()

    try: vcpu = get_combined_data('vCPU')
    except: vcpu = pd.DataFrame()

    try: vmemory = get_combined_data('vMemory')
    except: vmemory = pd.DataFrame()

    try: vhost = get_combined_data('vHost')
    except: vhost = pd.DataFrame()

    recommendations = []
    
    # Create VM -> Cluster map for efficient lookup
    vm_cluster_map = {}
    if not vinfo.empty and 'Cluster' in vinfo.columns:
        for _, row in vinfo.iterrows():
            vm_name = row['VM']
            cluster = row.get('Cluster', '')
            if pd.notna(cluster) and cluster != '' and cluster != '-':
                vm_cluster_map[vm_name] = cluster
    
    # Clean numeric columns
    vinfo['CPUs'] = pd.to_numeric(vinfo['CPUs'], errors='coerce').fillna(0)
    vinfo['Memory'] = pd.to_numeric(vinfo['Memory'], errors='coerce').fillna(0)
    vinfo['Total disk capacity MiB'] = pd.to_numeric(vinfo['Total disk capacity MiB'], errors='coerce').fillna(0)
    
    # --- 1. RESOURCE OPTIMIZATION ---
    # 1.1 Powered Off VMs - Disk Waste (CPU/RAM zaten kullanılmıyor)
    powered_off = vinfo[vinfo['Powerstate'] == 'poweredOff']
    for _, vm in powered_off.iterrows():
        disk_gb = round(vm['Total disk capacity MiB'] / 1024, 2)
        if disk_gb > cfg.POWERED_OFF_DISK_MIN_GB:  # Only report if significant disk
            recommendations.append({
                'vm': vm['VM'], 'type': 'POWERED_OFF_DISK', 'severity': 'MEDIUM',
                'reason': f"Kapalı VM {disk_gb} GB disk kullanıyor. Silinebilir veya arşivlenebilir.",
                'current_value': f'{disk_gb} GB', 'recommended_value': '0 GB (Sil/Arşivle)',
                'potential_savings': disk_gb, 'resource_type': 'DISK_GB', 'source': vm['Source']
            })
    
    # 1.2 Powered On VMs - CPU Underutilization (Gerçek kullanım + Host CPU hızı)
    if not vcpu.empty and 'Overall' in vcpu.columns:
        vcpu['Overall'] = pd.to_numeric(vcpu['Overall'], errors='coerce').fillna(0)
        vcpu['CPUs'] = pd.to_numeric(vcpu['CPUs'], errors='coerce').fillna(1)
        if 'Max' in vcpu.columns:
            vcpu['Max'] = pd.to_numeric(vcpu['Max'], errors='coerce').fillna(0)
        
        # Load host CPU info
        try:
            vhost = get_combined_data('vHost')
            host_cpu_info = {}

            for _, host in vhost.iterrows():
                host_name = host.get('Host', '')
                cpu_model = str(host.get('CPU Model', '')).upper()
                cpu_speed = pd.to_numeric(host.get('Speed', 2000), errors='coerce')
                if pd.isna(cpu_speed) or cpu_speed == 0:
                    cpu_speed = 2000

                if 'AMD' in cpu_model or 'EPYC' in cpu_model:
                    vendor = 'AMD'
                    efficiency_factor = 1.15
                else:
                    vendor = 'Intel'
                    efficiency_factor = 1.0

                if host_name:
                    host_cpu_info[host_name] = {
                        'speed': cpu_speed,
                        'vendor': vendor,
                        'efficiency': efficiency_factor,
                    }
        except Exception as e:
            print(f"Host CPU info load error: {e}")
            host_cpu_info = {}

        vcpu_with_power = vcpu.merge(
            vinfo[['VM', 'Powerstate', 'Host', 'Source']],
            on='VM',
            how='left',
            suffixes=('', '_info'),
        )

        powered_on_vcpu = vcpu_with_power[
            (vcpu_with_power['Powerstate'] == 'poweredOn') &
            (vcpu_with_power['CPUs'] > cfg.CPU_UNDERUTIL_MIN_VCPU_CHECK)
        ]

        for _, vm in powered_on_vcpu.iterrows():
            current_cpu = int(vm.get('CPUs', 0) or 0)
            if current_cpu <= 0:
                continue

            usage_mhz = float(vm.get('Overall', 0) or 0)
            vm_host = vm.get('Host', '')

            max_capacity_mhz = float(vm.get('Max', 0) or 0)

            host_info = host_cpu_info.get(vm_host, {'speed': 2000, 'vendor': 'Intel', 'efficiency': 1.0})
            cpu_speed_per_core = float(host_info['speed'])
            efficiency = float(host_info['efficiency'])
            vendor = str(host_info['vendor'])

            if max_capacity_mhz <= 0:
                max_capacity_mhz = current_cpu * cpu_speed_per_core * efficiency
            usage_percent = (usage_mhz / max_capacity_mhz * 100) if max_capacity_mhz > 0 else 0

            if usage_percent < cfg.CPU_UNDERUTIL_MAX_USAGE_PCT and current_cpu >= cfg.CPU_UNDERUTIL_MIN_VCPU_RECOMMEND:
                effective_speed = cpu_speed_per_core * efficiency
                usage_based_cpus = max(2, int((usage_mhz / effective_speed) + 1))

                min_recommended = max(2, int(current_cpu * cfg.CPU_UNDERUTIL_MIN_REDUCTION_FRACTION))
                needed_cpus = max(usage_based_cpus, min_recommended)

                if needed_cpus < current_cpu:
                    savings = current_cpu - needed_cpus
                    recommendations.append({
                        'vm': vm['VM'], 'type': 'CPU_UNDERUTILIZED', 'severity': 'LOW',
                        'reason': f"CPU kullanımı düşük (%{usage_percent:.0f}). Muhafazakar öneri: {current_cpu} -> {needed_cpus} vCPU. {vendor}.",
                        'current_value': current_cpu, 'recommended_value': needed_cpus,
                        'potential_savings': savings, 'resource_type': 'vCPU', 'source': vm.get('Source', '')
                    })

    # 1.3 Snapshot heavy VMs & OLD SNAPSHOTS (NEW)
    if not vsnapshot.empty:
        # 1.3.1 Size Check
        snapshot_summary = vsnapshot.groupby('VM').agg({'Size MiB (total)': 'sum', 'Name': 'count'}).reset_index()
        snapshot_summary.columns = ['VM', 'Total_Snapshot_MiB', 'Snapshot_Count']
        vinfo_with_snapshots = vinfo.merge(snapshot_summary, on='VM', how='left')
        vinfo_with_snapshots['Total_Snapshot_MiB'] = vinfo_with_snapshots['Total_Snapshot_MiB'].fillna(0)
        vinfo_with_snapshots['Snapshot_Count'] = vinfo_with_snapshots['Snapshot_Count'].fillna(0)
        
        heavy_snapshots = vinfo_with_snapshots[
            (vinfo_with_snapshots['Total_Snapshot_MiB'] > vinfo_with_snapshots['Total disk capacity MiB'] * cfg.SNAPSHOT_HEAVY_DISK_RATIO) &
            (vinfo_with_snapshots['Total_Snapshot_MiB'] > 0)
        ]
        for _, vm in heavy_snapshots.iterrows():
            snapshot_gb = round(vm['Total_Snapshot_MiB'] / 1024, 2)
            recommendations.append({
                'vm': vm['VM'], 'type': 'CONSOLIDATE_SNAPSHOTS', 'severity': 'HIGH',
                'reason': f'{snapshot_gb} GB snapshots ({int(vm["Snapshot_Count"])} snapshots) exceeds disk size',
                'current_value': snapshot_gb, 'recommended_value': 0,
                'potential_savings': snapshot_gb, 'resource_type': 'DISK_GB', 'source': vm['Source']
            })

        # 1.3.2 Age Check (NEW)
        # Check if Date / time exists
        date_col = 'Date / time' if 'Date / time' in vsnapshot.columns else 'Date'
        if date_col in vsnapshot.columns:
            # Parse dates
            try:
                vsnapshot[date_col] = pd.to_datetime(vsnapshot[date_col], errors='coerce')
                old_threshold = datetime.now() - timedelta(days=cfg.SNAPSHOT_OLD_DAYS)
                old_snapshots = vsnapshot[vsnapshot[date_col] < old_threshold]
                
                for _, snap in old_snapshots.iterrows():
                    snap_date = snap[date_col].strftime('%Y-%m-%d')
                    recommendations.append({
                        'vm': snap['VM'], 'type': 'OLD_SNAPSHOT', 'severity': 'HIGH',
                        'reason': f"Snapshot 7 günden eski ({snap_date}). Performansı etkiler.",
                        'current_value': 'Old', 'recommended_value': 'Delete/Consolidate',
                        'potential_savings': 0, 'resource_type': 'Performance', 'source': snap.get('Source', '')
                    })
            except Exception as e:
                print(f"Snapshot date parse error: {e}")

    # 1.4 Application Aware: Redis
    redis_vms = vinfo[vinfo['VM'].str.contains('redis', case=False, na=False)]
    for _, vm in redis_vms.iterrows():
        current_cpu = int(vm['CPUs'])
        if current_cpu > 2:
            recommendations.append({
                'vm': vm['VM'], 'type': 'APP_OPTIMIZATION', 'severity': 'MEDIUM',
                'reason': 'Redis single-threaded çalışır. 2 vCPU\'dan fazlası genelde israftır.',
                'current_value': current_cpu, 'recommended_value': 2,
                'potential_savings': current_cpu - 2, 'resource_type': 'vCPU', 'source': vm['Source']
            })

    # 1.5 Application Aware: Domain Controllers
    dc_vms = vinfo[vinfo['VM'].str.contains(r'(-dc-|dc\d+|domain)', case=False, regex=True, na=False)]
    for _, vm in dc_vms.iterrows():
        current_cpu = int(vm['CPUs'])
        if current_cpu > 4:
            recommendations.append({
                'vm': vm['VM'], 'type': 'APP_OPTIMIZATION', 'severity': 'MEDIUM',
                'reason': 'Domain Controller için yüksek vCPU (AD genelde hafiftir).',
                'current_value': current_cpu, 'recommended_value': 4,
                'potential_savings': current_cpu - 4, 'resource_type': 'vCPU', 'source': vm['Source']
            })

    # --- 2. HEALTH & BEST PRACTICES ---

    # 2.1 VMware Tools Status
    if not vtools.empty:
        status_col = 'Status' if 'Status' in vtools.columns else 'Tools status'
        if status_col in vtools.columns:
            bad_tools = vtools[~vtools[status_col].astype(str).str.contains('toolsOk|guestToolsRunning', case=False, na=False)]
            for _, vm in bad_tools.iterrows():
                if vm['VM'] in vinfo[vinfo['Powerstate'] == 'poweredOn']['VM'].values: # Only check if powered on
                    recommendations.append({
                        'vm': vm['VM'], 'type': 'VM_TOOLS', 'severity': 'HIGH',
                        'reason': f"VMware Tools (PoweredOn): {vm[status_col]}",
                        'current_value': 'Not OK', 'recommended_value': 'Running',
                        'potential_savings': 0, 'resource_type': 'Health', 'source': vm.get('Source', '')
                    })

    # 2.2 Connected ISOs/Floppies
    if not vcd.empty:
        # Check 'Connected' column
        connected_cd = vcd[vcd['Connected'].astype(str).str.lower() == 'true']
        for _, vm in connected_cd.iterrows():
            recommendations.append({
                'vm': vm['VM'], 'type': 'ZOMBIE_RESOURCE', 'severity': 'MEDIUM',
                'reason': f"CD-ROM takılı: {vm.get('ISO Path', 'Unknown ISO')}",
                'current_value': 'Connected', 'recommended_value': 'Disconnected',
                'potential_savings': 0, 'resource_type': 'Health', 'source': vm.get('Source', '')
            })

    # 2.3 NUMA Alignment (Odd vCPU count)
    odd_cpu_vms = vinfo[(vinfo['CPUs'] % 2 != 0) & (vinfo['CPUs'] > 1)]
    for _, vm in odd_cpu_vms.iterrows():
        recommendations.append({
            'vm': vm['VM'], 'type': 'NUMA_ALIGNMENT', 'severity': 'LOW',
            'reason': f"Tek sayılı vCPU ({vm['CPUs']}) NUMA performansını etkileyebilir.",
            'current_value': vm['CPUs'], 'recommended_value': vm['CPUs'] + 1,
            'potential_savings': 0, 'resource_type': 'Performance', 'source': vm['Source']
        })

    # 2.4 Legacy Network Adapter (E1000)
    if not vnetwork.empty:
        adapter_col = 'Adapter' if 'Adapter' in vnetwork.columns else 'Adapter Type'
        if adapter_col in vnetwork.columns:
            legacy_nics = vnetwork[vnetwork[adapter_col].astype(str).str.contains('E1000|Vlance|Flexible', case=False, na=False)]
            for _, vm in legacy_nics.iterrows():
                recommendations.append({
                    'vm': vm['VM'], 'type': 'LEGACY_NIC', 'severity': 'LOW',
                    'reason': f"Eski ağ kartı ({vm[adapter_col]}) yüksek CPU kullanır.",
                    'current_value': vm[adapter_col], 'recommended_value': 'VMXNET3',
                    'potential_savings': 0, 'resource_type': 'Performance', 'source': vm.get('Source', '')
                })

    # 2.5 End-of-Life OS
    eol_regex = r'(2003|2008|2012|XP|Vista|7|CentOS 6|CentOS 5|Ubuntu 14|Ubuntu 16|Debian 8)'
    os_col = 'OS according to the configuration file'
    eol_vms = vinfo[vinfo[os_col].astype(str).str.contains(eol_regex, case=False, na=False)]
    for _, vm in eol_vms.iterrows():
        recommendations.append({
            'vm': vm['VM'], 'type': 'EOL_OS', 'severity': 'HIGH',
            'reason': f"EOL İşletim Sistemi: {vm[os_col]}",
            'current_value': 'EOL', 'recommended_value': 'Upgrade',
            'potential_savings': 0, 'resource_type': 'Security', 'source': vm['Source']
        })

    # 2.6 CPU LIMITS Check (NEW)
    if not vcpu.empty:
        limit_col = 'Limit'
        if limit_col in vcpu.columns:
            # Check for non-default values (Default usually -1 or 'Unlimited')
            limited_cpu = vcpu[
                (vcpu[limit_col].astype(str) != '-1') & 
                (vcpu[limit_col].astype(str).str.lower() != 'unlimited')
            ]
            for _, vm in limited_cpu.iterrows():
                recommendations.append({
                    'vm': vm['VM'], 'type': 'CPU_LIMIT', 'severity': 'HIGH',
                    'reason': f"CPU Limiti ayarlanmış ({vm[limit_col]} MHz). Performansı düşürebilir.",
                    'current_value': vm[limit_col], 'recommended_value': 'Unlimited',
                    'potential_savings': 0, 'resource_type': 'Performance', 'source': vm.get('Source', '')
                })

    # 2.7 MEMORY LIMITS Check (NEW)
    if not vmemory.empty:
        limit_col = 'Limit'
        if limit_col in vmemory.columns:
            limited_mem = vmemory[
                (vmemory[limit_col].astype(str) != '-1') & 
                (vmemory[limit_col].astype(str).str.lower() != 'unlimited')
            ]
            for _, vm in limited_mem.iterrows():
                recommendations.append({
                    'vm': vm['VM'], 'type': 'RAM_LIMIT', 'severity': 'HIGH',
                    'reason': f"RAM Limiti ayarlanmış ({vm[limit_col]} MB). Swap'e neden olabilir.",
                    'current_value': vm[limit_col], 'recommended_value': 'Unlimited',
                    'potential_savings': 0, 'resource_type': 'Performance', 'source': vm.get('Source', '')
                })

    # 2.8 OLD HARDWARE VERSION Check (DYNAMIC based on ESXi version)
    ver_col = 'HW version'
    if ver_col in vinfo.columns:
        # ESXi Version to Max HW Version mapping (more granular with Update levels)
        # Format: (major, minor, update) -> max_hw_version
        esxi_hw_map = [
            # ESXi 8.0.x
            ((8, 0, 1), 21),  # ESXi 8.0 U1/U2/U3
            ((8, 0, 0), 20),  # ESXi 8.0 GA
            # ESXi 7.0.x
            ((7, 0, 2), 19),  # ESXi 7.0 U2+
            ((7, 0, 1), 18),  # ESXi 7.0 U1
            ((7, 0, 0), 17),  # ESXi 7.0 GA
            # ESXi 6.7.x
            ((6, 7, 2), 15),  # ESXi 6.7 U2+
            ((6, 7, 0), 14),  # ESXi 6.7 GA
            # ESXi 6.5.x
            ((6, 5, 0), 13),  # ESXi 6.5
            # ESXi 6.0.x
            ((6, 0, 0), 11),  # ESXi 6.0
            # ESXi 5.x
            ((5, 5, 0), 10),  # ESXi 5.5
            ((5, 1, 0), 9),   # ESXi 5.1
            ((5, 0, 0), 8),   # ESXi 5.0
        ]
        # Load vHost data for ESXi versions
        try:
            vhost = get_combined_data('vHost')
            host_esxi = {}
            
            def get_max_hw_for_esxi(version_str):
                """Parse ESXi version and return max supported HW version"""
                # Extract version like "8.0.3" from "VMware ESXi 8.0.3 build-xxx"
                match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', version_str)
                if not match:
                    return 13, 'Unknown'  # Fallback
                
                major = int(match.group(1))
                minor = int(match.group(2))
                update = int(match.group(3)) if match.group(3) else 0
                
                version_display = f"{major}.{minor}.{update}" if update else f"{major}.{minor}"
                
                # Find best matching HW version
                max_hw = 13  # Default fallback
                for (req_major, req_minor, req_update), hw_ver in esxi_hw_map:
                    if major > req_major:
                        max_hw = max(max_hw, hw_ver)
                    elif major == req_major and minor > req_minor:
                        max_hw = max(max_hw, hw_ver)
                    elif major == req_major and minor == req_minor and update >= req_update:
                        max_hw = max(max_hw, hw_ver)
                
                return max_hw, version_display
            
            for _, host in vhost.iterrows():
                esxi_ver = str(host.get('ESX Version', ''))
                max_hw, ver_display = get_max_hw_for_esxi(esxi_ver)
                host_esxi[host['Host']] = {'esxi': ver_display, 'max_hw': max_hw}
            
            # Check each VM
            for _, vm in vinfo.iterrows():
                vm_hw_str = str(vm.get(ver_col, ''))
                vm_host = vm.get('Host', '')
                
                # Parse VM HW version
                hw_match = re.search(r'(\d+)', vm_hw_str)
                if not hw_match:
                    continue
                vm_hw = int(hw_match.group(1))
                
                # Get host's max supported HW
                host_info = host_esxi.get(vm_host, {'esxi': 'Unknown', 'max_hw': 13})
                max_supported = host_info['max_hw']
                
                # If VM HW < Host's max supported, it can be upgraded
                if vm_hw < max_supported:
                    recommendations.append({
                        'vm': vm['VM'], 'type': 'OLD_HW_VERSION', 'severity': 'LOW',
                        'reason': f"HW v{vm_hw} -> v{max_supported} yükseltilebilir (ESXi {host_info['esxi']})",
                        'current_value': f'vmx-{vm_hw}', 'recommended_value': f'vmx-{max_supported}',
                        'potential_savings': 0, 'resource_type': 'Performance', 'source': vm['Source']
                    })
        except Exception as e:
            print(f"HW Version check error: {e}")

    # --- 3. NEW CHECKS ---

    # 3.1 Memory Ballooning/Swapping Detection (Critical Performance Issue)
    vmemory = get_combined_data('vMemory')
    if not vmemory.empty:
        balloon_col = 'Ballooned MB' if 'Ballooned MB' in vmemory.columns else 'Ballooned'
        swap_col = 'Swapped MB' if 'Swapped MB' in vmemory.columns else 'Swapped'
        
        if balloon_col in vmemory.columns:
            vmemory[balloon_col] = pd.to_numeric(vmemory[balloon_col], errors='coerce').fillna(0)
            ballooned = vmemory[vmemory[balloon_col] > 0]
            for _, vm in ballooned.iterrows():
                if vm['VM'] in vinfo[vinfo['Powerstate'] == 'poweredOn']['VM'].values:
                    recommendations.append({
                        'vm': vm['VM'], 'type': 'MEMORY_BALLOON', 'severity': 'CRITICAL',
                        'reason': f"Memory Ballooning aktif ({vm[balloon_col]:.0f} MB). Host RAM baskısı var!",
                        'current_value': f"{vm[balloon_col]:.0f} MB", 'recommended_value': '0 MB',
                        'potential_savings': 0, 'resource_type': 'Performance',
                        'source': vm.get('Source', ''), 'cluster': vm_cluster_map.get(vm['VM'], '-')
                    })
        
        if swap_col in vmemory.columns:
            vmemory[swap_col] = pd.to_numeric(vmemory[swap_col], errors='coerce').fillna(0)
            swapped = vmemory[vmemory[swap_col] > 0]
            for _, vm in swapped.iterrows():
                if vm['VM'] in vinfo[vinfo['Powerstate'] == 'poweredOn']['VM'].values:
                    recommendations.append({
                        'vm': vm['VM'], 'type': 'MEMORY_SWAP', 'severity': 'CRITICAL',
                        'reason': f"Memory Swapping aktif ({vm[swap_col]:.0f} MB). Ciddi performans sorunu!",
                        'current_value': f"{vm[swap_col]:.0f} MB", 'recommended_value': '0 MB',
                        'potential_savings': 0, 'resource_type': 'Performance',
                        'source': vm.get('Source', ''), 'cluster': vm_cluster_map.get(vm['VM'], '-')
                    })

    # 3.2 Host vCPU:pCore Ratio (AMD/Intel aware)
    if not vhost.empty and not vcpu.empty:
        try:
            # Get total vCPUs per host
            vcpu_per_host = vcpu.groupby('Host')['CPUs'].sum().to_dict()
            
            for _, host in vhost.iterrows():
                host_name = host['Host']
                cpu_model = str(host.get('CPU Model', '')).upper()
                
                # Get physical cores
                cores_col = '# Cores' if '# Cores' in host.index else 'Cores'
                pCores = pd.to_numeric(host.get(cores_col, host.get('# CPU', 1)), errors='coerce') or 1
                
                # Get total vCPUs on this host
                total_vCPUs = vcpu_per_host.get(host_name, 0)
                
                if pCores > 0 and total_vCPUs > 0:
                    ratio = total_vCPUs / pCores
                    
                    # AMD vs Intel thresholds
                    if 'AMD' in cpu_model or 'EPYC' in cpu_model:
                        warn_threshold, critical_threshold = 8, 10
                        vendor = 'AMD'
                    else:
                        warn_threshold, critical_threshold = 6, 8
                        vendor = 'Intel'
                    
                    if ratio > critical_threshold:
                        severity = 'CRITICAL'
                        msg = f"vCPU:pCore oranı {ratio:.1f}:1 (>{critical_threshold}:1). Ciddi overcommitment!"
                    elif ratio > warn_threshold:
                        severity = 'HIGH'
                        msg = f"vCPU:pCore oranı {ratio:.1f}:1 (>{warn_threshold}:1). Overcommitment riski."
                    else:
                        continue  # Ratio is OK
                    
                    recommendations.append({
                        'vm': host_name, 'type': 'HOST_CPU_OVERCOMMIT', 'severity': severity,
                        'reason': f"{msg} ({vendor}, {pCores} pCore, {total_vCPUs} vCPU)",
                        'current_value': f"{ratio:.1f}:1", 'recommended_value': f"<{warn_threshold}:1",
                        'potential_savings': 0, 'resource_type': 'Capacity',
                        'source': host.get('Source', ''), 'cluster': host.get('Cluster', '-')
                    })
        except Exception as e:
            print(f"vCPU:pCore ratio error: {e}")

    # 3.3 Datastore Low Free Space Warning
    vdatastore = get_combined_data('vDatastore')
    if not vdatastore.empty:
        try:
            cap_col = 'Capacity MiB' if 'Capacity MiB' in vdatastore.columns else 'Capacity MB'
            free_col = 'Free MiB' if 'Free MiB' in vdatastore.columns else 'Free MB'
            prov_col = 'Provisioned MiB' if 'Provisioned MiB' in vdatastore.columns else 'Provisioned MB'
            
            if cap_col in vdatastore.columns and free_col in vdatastore.columns:
                vdatastore[cap_col] = pd.to_numeric(vdatastore[cap_col], errors='coerce').fillna(0)
                vdatastore[free_col] = pd.to_numeric(vdatastore[free_col], errors='coerce').fillna(0)
                
                for _, ds in vdatastore.iterrows():
                    capacity = ds[cap_col]
                    free = ds[free_col]
                    
                    if capacity > 0:
                        free_pct = (free / capacity) * 100
                        
                        if free_pct < cfg.DATASTORE_FREE_CRITICAL_PCT:
                            severity = 'CRITICAL'
                            msg = f"Datastore %{free_pct:.1f} boş. Kritik seviye!"
                        elif free_pct < cfg.DATASTORE_FREE_HIGH_PCT:
                            severity = 'HIGH'
                            msg = f"Datastore %{free_pct:.1f} boş. Düşük alan uyarısı."
                        elif free_pct < cfg.DATASTORE_FREE_WARN_PCT:
                            severity = 'MEDIUM'
                            msg = f"Datastore %{free_pct:.1f} boş. İzlenmeli."
                        else:
                            continue
                        
                        recommendations.append({
                            'vm': ds['Name'], 'type': 'DATASTORE_LOW_SPACE', 'severity': severity,
                            'reason': msg,
                            'current_value': f"{free_pct:.1f}%", 'recommended_value': '>15%',
                            'potential_savings': 0, 'resource_type': 'Storage',
                            'source': ds.get('Source', ''), 'cluster': ds.get('Cluster name', '-')
                        })
                
                # 3.4 Datastore Overcommitment
                if prov_col in vdatastore.columns:
                    vdatastore[prov_col] = pd.to_numeric(vdatastore[prov_col], errors='coerce').fillna(0)
                    
                    for _, ds in vdatastore.iterrows():
                        capacity = ds[cap_col]
                        provisioned = ds[prov_col]
                        
                        if capacity > 0 and provisioned > capacity:
                            overcommit_pct = ((provisioned - capacity) / capacity) * 100
                            
                            if overcommit_pct > cfg.DATASTORE_OVERCOMMIT_CRITICAL_PCT:
                                severity = 'CRITICAL'
                            elif overcommit_pct > cfg.DATASTORE_OVERCOMMIT_HIGH_PCT:
                                severity = 'HIGH'
                            else:
                                severity = 'MEDIUM'
                            
                            recommendations.append({
                                'vm': ds['Name'], 'type': 'DATASTORE_OVERCOMMIT', 'severity': severity,
                                'reason': f"Provisioned ({provisioned/1024:.0f} GB) > Capacity ({capacity/1024:.0f} GB). %{overcommit_pct:.0f} overcommit.",
                                'current_value': f"{provisioned/1024:.0f} GB prov", 'recommended_value': f"<{capacity/1024:.0f} GB",
                                'potential_savings': 0, 'resource_type': 'Storage',
                                'source': ds.get('Source', ''), 'cluster': ds.get('Cluster name', '-')
                            })
        except Exception as e:
            print(f"Datastore check error: {e}")

    # 3.5 Connected Floppy (Security Risk)
    try:
        vfloppy = get_combined_data('vFloppy')
        if not vfloppy.empty and 'Connected' in vfloppy.columns:
            connected_floppy = vfloppy[vfloppy['Connected'].astype(str).str.lower() == 'true']
            for _, vm in connected_floppy.iterrows():
                recommendations.append({
                    'vm': vm['VM'], 'type': 'FLOPPY_CONNECTED', 'severity': 'LOW',
                    'reason': "Floppy sürücü bağlı. Güvenlik riski ve migration engelleyebilir.",
                    'current_value': 'Connected', 'recommended_value': 'Disconnected',
                    'potential_savings': 0, 'resource_type': 'Security',
                    'source': vm.get('Source', ''), 'cluster': vm_cluster_map.get(vm['VM'], '-')
                })
    except Exception as e:
        print(f"Floppy check skipped: {e}")

    # 3.6 Thin Provisioning Analysis (High Provisioned:Used Ratio)
    vpartition = get_combined_data('vPartition')
    if not vpartition.empty and not vinfo.empty:
        try:
            consumed_col = 'Consumed MB' if 'Consumed MB' in vpartition.columns else 'Consumed MiB'
            if consumed_col in vpartition.columns:
                # Aggregate consumed per VM
                consumed_per_vm = vpartition.groupby('VM')[consumed_col].sum().to_dict()
                
                for _, vm in vinfo.iterrows():
                    provisioned = pd.to_numeric(vm.get('Provisioned MiB', vm.get('Provisioned MB', 0)), errors='coerce') or 0
                    consumed = consumed_per_vm.get(vm['VM'], 0)
                    
                    if consumed > 0 and provisioned > 0:
                        ratio = provisioned / consumed
 
                        min_provisioned_mib = int(cfg.STORAGE_OVERPROVISION_MIN_PROVISIONED_GB * 1024)
                        if ratio > cfg.STORAGE_OVERPROVISION_RATIO and provisioned > min_provisioned_mib:
                            waste_gb = (provisioned - consumed) / 1024
                            recommendations.append({
                                'vm': vm['VM'], 'type': 'STORAGE_OVERPROVISIONED', 'severity': 'LOW',
                                'reason': f"Provisioned/Used oranı {ratio:.1f}x. {waste_gb:.0f} GB potansiyel israf.",
                                'current_value': f"{provisioned/1024:.0f} GB prov", 'recommended_value': f"{consumed/1024:.0f} GB used",
                                'potential_savings': waste_gb, 'resource_type': 'DISK_GB',
                                'source': vm['Source'], 'cluster': vm_cluster_map.get(vm['VM'], '-')
                            })
        except Exception as e:
            print(f"Thin provisioning check error: {e}")

    # --- FILTER AND SORT ---
    # Show items with savings > 0 OR compliance/health types
    compliance_types = [
        'EOL_OS', 'OLD_HW_VERSION', 'VM_TOOLS', 'OLD_SNAPSHOT', 
        'LEGACY_NIC', 'CONSOLIDATE_SNAPSHOTS', 'CPU_LIMIT', 'RAM_LIMIT',
        'ZOMBIE_RESOURCE', 'NUMA_ALIGNMENT', 'MEMORY_BALLOON', 'MEMORY_SWAP',
        'HOST_CPU_OVERCOMMIT', 'DATASTORE_LOW_SPACE', 'DATASTORE_OVERCOMMIT',
        'FLOPPY_CONNECTED', 'STORAGE_OVERPROVISIONED'
    ]
    
    filtered_recommendations = [
        r for r in recommendations 
        if float(r.get('potential_savings', 0)) > 0 or r.get('type') in compliance_types
    ]
    
    filtered_recommendations.sort(key=lambda x: (
        {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}.get(x.get('severity', 'LOW'), 4),
        -float(x.get('potential_savings', 0))
    ))

    # Clean NaN values for valid JSON output
    def clean_nan(obj):
        if isinstance(obj, float) and (obj != obj):  # NaN check
            return None
        if isinstance(obj, dict):
            return {k: clean_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_nan(v) for v in obj]
        return obj
    
    cleaned_recommendations = clean_nan(filtered_recommendations)
    
    # Also replace None with empty string for string fields
    for rec in cleaned_recommendations:
        vm_name = rec.get('vm')
        # Find VM info for host/cluster
        vm_row = vinfo[vinfo['VM'] == vm_name]
        if not vm_row.empty:
            vm_data = vm_row.iloc[0]
            if not rec.get('host') or rec.get('host') == '-':
                rec['host'] = vm_data.get('Host', '-')
            if not rec.get('cluster') or rec.get('cluster') == '-':
                rec['cluster'] = vm_data.get('Cluster', '-')
            if not rec.get('datacenter') or rec.get('datacenter') == '-':
                rec['datacenter'] = vm_data.get('Datacenter', '-')

        for key in ['vm', 'type', 'severity', 'reason', 'current_value', 'recommended_value', 'resource_type', 'source', 'cluster', 'host', 'datacenter']:
            if rec.get(key) is None:
                rec[key] = '-'
        if rec.get('potential_savings') is None:
            rec['potential_savings'] = 0

    return jsonify({
        'total_recommendations': len(cleaned_recommendations),
        'recommendations': cleaned_recommendations
    })

@app.route('/api/reports/disk-waste')
def api_disk_waste():
    """Detailed disk waste analysis"""
    try:
        vdisk = get_combined_data('vDisk').copy()
        vinfo = get_combined_data('vInfo')
        
        # Clean numeric
        vdisk['Capacity MiB'] = pd.to_numeric(vdisk['Capacity MiB'], errors='coerce').fillna(0)
        
        # Merge with VM info to get power state
        waste_analysis = vdisk.merge(vinfo[['VM', 'Powerstate', 'Source']], on='VM', how='left', suffixes=('', '_info'))
        
        # Identify waste scenarios
        waste_disks = []
        
        # 1. Thick provisioned large disks on powered off VMs
        thick_off = waste_analysis[
            (waste_analysis['Thin'] == False) & 
            (waste_analysis['Powerstate'] == 'poweredOff') &
            (waste_analysis['Capacity MiB'] > 10240)  # > 10GB
        ]
        
        for _, disk in thick_off.iterrows():
            capacity_gb = round(disk['Capacity MiB'] / 1024, 2)
            waste_disks.append({
                'vm': disk['VM'],
                'disk_name': disk['Disk'],
                'waste_type': 'THICK_POWERED_OFF',
                'capacity_gb': capacity_gb,
                'estimated_waste_gb': capacity_gb * 0.7,  # Assume 70% waste on powered off
                'thin': disk['Thin'],
                'source': disk.get('Source_info') or disk.get('Source', '')
            })
        
        # 2. Very large thick disks (potential for thin conversion)
        large_thick = waste_analysis[
            (waste_analysis['Thin'] == False) &
            (waste_analysis['Capacity MiB'] > 102400)  # > 100GB
        ]
        
        for _, disk in large_thick.iterrows():
            capacity_gb = round(disk['Capacity MiB'] / 1024, 2)
            waste_disks.append({
                'vm': disk['VM'],
                'disk_name': disk['Disk'],
                'waste_type': 'THICK_LARGE',
                'capacity_gb': capacity_gb,
                'estimated_waste_gb': capacity_gb * 0.3,  # Assume 30% savings with thin
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

@app.route('/api/capacity-planning')
def api_capacity_planning():
    """Capacity planning metrics"""
    try:
        vinfo = get_combined_data('vInfo').copy()
        vhost = get_combined_data('vHost').copy()
        
        # Clean numeric columns
        vinfo['CPUs'] = pd.to_numeric(vinfo['CPUs'], errors='coerce').fillna(0)
        vinfo['Memory'] = pd.to_numeric(vinfo['Memory'], errors='coerce').fillna(0)
        vhost['# CPU'] = pd.to_numeric(vhost['# CPU'], errors='coerce').fillna(0)
        vhost['Cores per CPU'] = pd.to_numeric(vhost['Cores per CPU'], errors='coerce').fillna(0)
        vhost['Memory'] = pd.to_numeric(vhost['Memory'], errors='coerce').fillna(0)
        
        # Calculate totals
        total_vcpu = int(vinfo['CPUs'].sum())
        total_allocated_ram_mb = vinfo['Memory'].sum()
        total_allocated_ram_gb = round(total_allocated_ram_mb / 1024, 2)
        
        # Physical resources
        total_physical_cores = int((vhost['# CPU'] * vhost['Cores per CPU']).sum())
        total_physical_ram_mb = vhost['Memory'].sum()
        total_physical_ram_gb = round(total_physical_ram_mb / 1024, 2)
        
        # Overcommitment ratios
        cpu_overcommit = round(total_vcpu / total_physical_cores, 2) if total_physical_cores > 0 else 0
        mem_overcommit = round(total_allocated_ram_gb / total_physical_ram_gb, 2) if total_physical_ram_gb > 0 else 0
        
        # Host-level analysis
        host_pressure = []
        for _, host in vhost.iterrows():
            host_name = host['Host']
            host_physical_cores = host['# CPU'] * host['Cores per CPU']
            host_physical_ram_gb = round(host['Memory'] / 1024, 2)
            
            # Get VMs on this host
            host_vms = vinfo[vinfo['Host'] == host_name]
            host_vcpu = int(host_vms['CPUs'].sum())
            host_vram_gb = round(host_vms['Memory'].sum() / 1024, 2)
            
            if host_physical_cores > 0:
                cpu_usage_pct = round((host_vcpu / host_physical_cores) * 100, 1)
                ram_usage_pct = round((host_vram_gb / host_physical_ram_gb) * 100, 1) if host_physical_ram_gb > 0 else 0
                
                host_pressure.append({
                    'host': host_name,
                    'cluster': host.get('Cluster', ''),
                    'cpu_usage_pct': cpu_usage_pct,
                    'ram_usage_pct': ram_usage_pct,
                    'vcpu_allocated': host_vcpu,
                    'physical_cores': int(host_physical_cores),
                    'ram_allocated_gb': host_vram_gb,
                    'physical_ram_gb': host_physical_ram_gb
                })
        
        return jsonify({
            'cpu_overcommit': cpu_overcommit,
            'mem_overcommit': mem_overcommit,
            'total_vcpu': total_vcpu,
            'total_physical_cores': total_physical_cores,
            'total_allocated_ram_gb': total_allocated_ram_gb,
            'total_physical_ram_gb': total_physical_ram_gb,
            'host_pressure': sorted(host_pressure, key=lambda x: x['cpu_usage_pct'], reverse=True)[:10]  # Top 10
        })
    except Exception as e:
        print(f"Error in capacity planning: {e}")
        return jsonify({'cpu_overcommit': 0, 'mem_overcommit': 0, 'total_vcpu': 0, 'total_physical_cores': 0, 'total_allocated_ram_gb': 0, 'total_physical_ram_gb': 0, 'host_pressure': []})

@app.route('/api/efficiency-score')
def api_efficiency_score():
    """Calculate resource efficiency score (0-100)"""
    try:
        vinfo = get_combined_data('vInfo').copy()
        vsnapshot = get_combined_data('vSnapshot')
        
        score = 100
        breakdown = {}
        
        # 1. Powered On Ratio (max 30 points)
        total_vms = len(vinfo)
        powered_on = len(vinfo[vinfo['Powerstate'] == 'poweredOn'])
        on_ratio = (powered_on / total_vms * 100) if total_vms > 0 else 0
        
        if on_ratio >= 80:
            power_score = 30
        elif on_ratio >= 60:
            power_score = 20
        elif on_ratio >= 40:
            power_score = 10
        else:
            power_score = 0
        
        breakdown['power_on_ratio'] = {'score': power_score, 'max': 30, 'value': round(on_ratio, 1)}
        
        # 2. Snapshot Hygiene (max 25 points)
        vms_with_old_snapshots = 0
        if len(vsnapshot) > 0:
            vsnapshot['Date / time'] = pd.to_datetime(vsnapshot['Date / time'], errors='coerce')
            old_snapshots = vsnapshot[vsnapshot['Date / time'] < (datetime.now() - timedelta(days=7))]
            vms_with_old_snapshots = old_snapshots['VM'].nunique()
        
        old_snapshot_ratio = (vms_with_old_snapshots / total_vms * 100) if total_vms > 0 else 0
        snapshot_score = max(0, 25 - (old_snapshot_ratio * 0.5))
        breakdown['snapshot_hygiene'] = {'score': int(snapshot_score), 'max': 25, 'vms_with_old': vms_with_old_snapshots}
        
        # 3. Disk Provisioning (max 20 points) - Prefer thin
        try:
            vdisk = get_combined_data('vDisk')
            thin_disks = len(vdisk[vdisk['Thin'] == True])
            total_disks = len(vdisk)
            thin_ratio = (thin_disks / total_disks * 100) if total_disks > 0 else 0
            disk_score = int(thin_ratio * 0.2)
            breakdown['disk_efficiency'] = {'score': disk_score, 'max': 20, 'thin_ratio': round(thin_ratio, 1)}
        except:
            disk_score = 10  # Default
            breakdown['disk_efficiency'] = {'score': disk_score, 'max': 20, 'thin_ratio': 50}
        
        # 4. Resource Reservation (max 15 points) - Penalize reservations
        try:
            vcpu = get_combined_data('vCPU')
            cpu_res_col = next((c for c in vcpu.columns if 'Reservation' in c and 'Limit' not in c), None)
            reserved_count = 0
            if cpu_res_col:
                vcpu['ReservationVal'] = pd.to_numeric(vcpu[cpu_res_col], errors='coerce').fillna(0)
                reserved_count = len(vcpu[vcpu['ReservationVal'] > 0])
            
            reservation_ratio = (reserved_count / total_vms * 100) if total_vms > 0 else 0
            reservation_score = max(0, 15 - (reservation_ratio * 0.3))
            breakdown['reservation_efficiency'] = {'score': int(reservation_score), 'max': 15, 'reserved_vms': reserved_count}
        except:
            reservation_score = 10
            breakdown['reservation_efficiency'] = {'score': int(reservation_score), 'max': 15, 'reserved_vms': 0}
        
        # 5. VM Density (max 10 points) - More VMs per host is better
        avg_vms_per_host = total_vms / len(vinfo['Host'].unique()) if len(vinfo['Host'].unique()) > 0 else 0
        if avg_vms_per_host >= 15:
            density_score = 10
        elif avg_vms_per_host >= 10:
            density_score = 7
        elif avg_vms_per_host >= 5:
            density_score = 5
        else:
            density_score = 2
        
        breakdown['vm_density'] = {'score': density_score, 'max': 10, 'avg_per_host': round(avg_vms_per_host, 1)}
        
        # Total score
        total_score = power_score + snapshot_score + disk_score + reservation_score + density_score
        
        # Grade
        if total_score >= 90:
            grade = 'Excellent'
        elif total_score >= 75:
            grade = 'Good'
        elif total_score >= 60:
            grade = 'Fair'
        else:
            grade = 'Needs Improvement'
        
        return jsonify({
            'score': int(total_score),
            'grade': grade,
            'breakdown': breakdown
        })
    except Exception as e:
        print(f"Error calculating efficiency score: {e}")
        return jsonify({'score': 50, 'grade': 'Unknown', 'breakdown': {}})

@app.route('/api/cost-estimation')
def api_cost_estimation():
    """Estimate costs based on resource allocation"""
    # Cost constants (USD per month)
    COST_PER_VCPU = 10
    COST_PER_GB_RAM = 5
    COST_PER_GB_DISK = 0.1
    
    try:
        vinfo = get_combined_data('vInfo').copy()
        
        # Clean numeric
        vinfo['CPUs'] = pd.to_numeric(vinfo['CPUs'], errors='coerce').fillna(0)
        vinfo['Memory'] = pd.to_numeric(vinfo['Memory'], errors='coerce').fillna(0)
        vinfo['Total disk capacity MiB'] = pd.to_numeric(vinfo['Total disk capacity MiB'], errors='coerce').fillna(0)
        
        # Calculate individual VM costs
        vinfo['cpu_cost'] = vinfo['CPUs'] * COST_PER_VCPU
        vinfo['ram_cost'] = (vinfo['Memory'] / 1024) * COST_PER_GB_RAM
        vinfo['disk_cost'] = (vinfo['Total disk capacity MiB'] / 1024) * COST_PER_GB_DISK
        vinfo['total_cost'] = vinfo['cpu_cost'] + vinfo['ram_cost'] + vinfo['disk_cost']
        
        # Total costs
        total_cpu_cost = vinfo['cpu_cost'].sum()
        total_ram_cost = vinfo['ram_cost'].sum()
        total_disk_cost = vinfo['disk_cost'].sum()
        total_cost = vinfo['total_cost'].sum()
        
        # Powered off waste
        powered_off = vinfo[vinfo['Powerstate'] == 'poweredOff']
        wasted_cost = powered_off['total_cost'].sum()
        
        # Top 10 most expensive VMs
        top_vms = vinfo.nlargest(10, 'total_cost')[['VM', 'Powerstate', 'CPUs', 'Memory', 'total_cost', 'Source']].to_dict('records')
        
        return jsonify({
            'total_monthly_cost': round(total_cost, 2),
            'cpu_cost': round(total_cpu_cost, 2),
            'ram_cost': round(total_ram_cost, 2),
            'disk_cost': round(total_disk_cost, 2),
            'wasted_on_powered_off': round(wasted_cost, 2),
            'top_expensive_vms': top_vms,
            'rates': {
                'vcpu': COST_PER_VCPU,
                'ram_gb': COST_PER_GB_RAM,
                'disk_gb': COST_PER_GB_DISK
            }
        })
    except Exception as e:
        print(f"Error in cost estimation: {e}")
        return jsonify({'cpu_overcommit': 0, 'mem_overcommit': 0, 'total_vcpu': 0, 'total_physical_cores': 0, 'total_allocated_ram_gb': 0, 'total_physical_ram_gb': 0, 'host_pressure': []})


@app.route('/api/datastores')
def api_datastores():
    """Get list of all datastores with physical storage info"""
    source = request.args.get('source', None)
    conn = sqlite3.connect('rvtools.db')
    conn.row_factory = sqlite3.Row
    
    try:
        if source:
            df_ds = pd.read_sql_query("SELECT * FROM vDatastore WHERE Source=?", conn, params=(source,))
            df_mp = pd.read_sql_query("SELECT Datastore, Vendor, Model, \"Serial #\" FROM vMultiPath WHERE Source=?", conn, params=(source,))
        else:
            df_ds = pd.read_sql_query("SELECT * FROM vDatastore", conn)
            df_mp = pd.read_sql_query("SELECT Datastore, Vendor, Model, \"Serial #\" FROM vMultiPath", conn)

        # Merge with multipath to get Vendor/Model
        # One datastore can have multiple paths, we just need the first unique storage info
        df_mp_unique = df_mp.drop_duplicates(subset=['Datastore'])
        
        df_combined = df_ds.merge(df_mp_unique, left_on='Name', right_on='Datastore', how='left')
        
        # Clean numeric columns
        cols_to_fix = ['Capacity MiB', 'Free MiB', 'Provisioned MiB', 'In Use MiB', '# VMs', '# Hosts']
        for col in cols_to_fix:
            if col in df_combined.columns:
                df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)

        return jsonify(df_combined.fillna('').to_dict('records'))
    except Exception as e:
        print(f"Error in api_datastores: {e}")
        return jsonify([])
    finally:
        conn.close()






@app.route('/api/hosts-clusters')
def api_hosts_clusters():
    """Get hierarchical datacenter/cluster/host structure with metrics (vCenter-style)"""
    try:
        vinfo = get_combined_data('vInfo').copy()
        vhost = get_combined_data('vHost').copy()
        
        # Clean numeric columns for vInfo
        vinfo['CPUs'] = pd.to_numeric(vinfo['CPUs'], errors='coerce').fillna(0)
        vinfo['Memory'] = pd.to_numeric(vinfo['Memory'], errors='coerce').fillna(0)
        vinfo['Total disk capacity MiB'] = pd.to_numeric(vinfo['Total disk capacity MiB'], errors='coerce').fillna(0)
        
        # Clean numeric columns for vHost - including REAL usage metrics
        vhost['# CPU'] = pd.to_numeric(vhost['# CPU'], errors='coerce').fillna(0)
        vhost['Cores per CPU'] = pd.to_numeric(vhost['Cores per CPU'], errors='coerce').fillna(0)
        vhost['# Cores'] = pd.to_numeric(vhost['# Cores'], errors='coerce').fillna(0)
        vhost['# Memory'] = pd.to_numeric(vhost['# Memory'], errors='coerce').fillna(0)
        vhost['CPU usage %'] = pd.to_numeric(vhost['CPU usage %'], errors='coerce').fillna(0)
        vhost['Memory usage %'] = pd.to_numeric(vhost['Memory usage %'], errors='coerce').fillna(0)
        vhost['# vCPUs'] = pd.to_numeric(vhost['# vCPUs'], errors='coerce').fillna(0)
        vhost['vRAM'] = pd.to_numeric(vhost['vRAM'], errors='coerce').fillna(0)
        
        # Build hierarchical structure
        hierarchy = {}
        
        # Process hosts first for physical metrics (from vHost)
        host_metrics = {}
        for _, host in vhost.iterrows():
            host_name = host.get('Host', 'Unknown')
            physical_cores = int(host['# Cores']) if host['# Cores'] > 0 else int(host['# CPU'] * host['Cores per CPU'])
            physical_ram_gb = round(host['# Memory'] / 1024, 2)
            
            # vCPU:pCore ratio
            vcpu_pcore_ratio = round(host['# vCPUs'] / physical_cores, 2) if physical_cores > 0 else 0
            
            # vRAM:pRAM ratio
            vram_gb = round(host['vRAM'] / 1024, 2)
            vram_pram_ratio = round(vram_gb / physical_ram_gb, 2) if physical_ram_gb > 0 else 0
            
            # Handle NaN values for string fields
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
                # REAL usage from vHost (ESXi reported)
                'cpu_usage_pct': round(host['CPU usage %'], 1),
                'ram_usage_pct': round(host['Memory usage %'], 1),
                # Overcommit ratios
                'vcpu_count': int(host['# vCPUs']),
                'vram_gb': vram_gb,
                'vcpu_pcore_ratio': vcpu_pcore_ratio,
                'vram_pram_ratio': vram_pram_ratio
            }
        
        # First, build hierarchy from vHost (ensures all hosts are included even without VMs)
        for _, host in vhost.iterrows():
            host_name = host.get('Host', 'Unknown')
            source = host.get('Source', 'Unknown')
            datacenter = host.get('Datacenter', 'Unknown Datacenter')
            cluster = host.get('Cluster', '')
            
            # Skip if cluster is NaN
            if pd.isna(cluster) or cluster == '' or cluster == 'nan':
                cluster = 'Standalone Hosts'
            
            # Initialize hierarchy
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
                    'physical_cores': 0,
                    'physical_ram_gb': 0,
                    'cpu_sockets': 0,
                    'cores_per_socket': 0,
                    'cpu_model': '',
                    'esxi_version': '',
                    'source': source,
                    'cpu_usage_pct': 0,
                    'ram_usage_pct': 0,
                    'vcpu_count': 0,
                    'vram_gb': 0,
                    'vcpu_pcore_ratio': 0,
                    'vram_pram_ratio': 0
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
        
        # Now process VMs to add them to existing hosts
        for _, row in vinfo.iterrows():
            source = row.get('Source', 'Unknown')
            datacenter = row.get('Datacenter', 'Unknown Datacenter')
            cluster = row.get('Cluster', 'Unknown Cluster')
            host = row.get('Host', 'Unknown Host')
            vm_name = row.get('VM', '')
            powerstate = row.get('Powerstate', 'poweredOff')
            
            # Skip if cluster is NaN
            if pd.isna(cluster) or cluster == 'nan':
                cluster = 'Standalone Hosts'
            
            # Initialize hierarchy if needed (for VMs on hosts not in vHost)
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
                    # Aggregated real usage
                    'avg_cpu_usage_pct': 0,
                    'avg_ram_usage_pct': 0
                }
            
            cl = dc['clusters'][cluster]
            
            if host not in cl['hosts']:
                hm = host_metrics.get(host, {
                    'physical_cores': 0,
                    'physical_ram_gb': 0,
                    'cpu_sockets': 0,
                    'cores_per_socket': 0,
                    'cpu_model': '',
                    'esxi_version': '',
                    'source': source,
                    'cpu_usage_pct': 0,
                    'ram_usage_pct': 0,
                    'vcpu_count': 0,
                    'vram_gb': 0,
                    'vcpu_pcore_ratio': 0,
                    'vram_pram_ratio': 0
                })
                cl['hosts'][host] = {
                    'vms': [],
                    'total_vms': 0,
                    'powered_on': 0,
                    'total_vcpu': 0,
                    'total_ram_gb': 0,
                    **hm
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
            
            # Update host VM metrics
            h['total_vms'] += 1
            h['total_vcpu'] += int(row['CPUs'])
            h['total_ram_gb'] += round(row['Memory'] / 1024, 2)
            if powerstate == 'poweredOn':
                h['powered_on'] += 1
            
            # Update cluster metrics
            cl['total_vms'] += 1
            cl['total_vcpu'] += int(row['CPUs'])
            cl['total_ram_gb'] += round(row['Memory'] / 1024, 2)
            if powerstate == 'poweredOn':
                cl['powered_on'] += 1
            
            # Update datacenter metrics
            dc['total_vms'] += 1
            dc['total_vcpu'] += int(row['CPUs'])
            dc['total_ram_gb'] += round(row['Memory'] / 1024, 2)
            if powerstate == 'poweredOn':
                dc['powered_on'] += 1
        
        # Calculate aggregated metrics for clusters and datacenters
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
                        # Calculate cluster averages from real host data
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
                        
                        # vCPU:pCore ratio for cluster
                        if cl_data['total_physical_cores'] > 0:
                            cl_data['vcpu_pcore_ratio'] = round(total_vcpu_from_hosts / cl_data['total_physical_cores'], 2)
                        else:
                            cl_data['vcpu_pcore_ratio'] = 0
                        
                        # vRAM:pRAM ratio for cluster
                        if cl_data['total_physical_ram_gb'] > 0:
                            cl_data['vram_pram_ratio'] = round(total_vram_from_hosts / cl_data['total_physical_ram_gb'], 2)
                        else:
                            cl_data['vram_pram_ratio'] = 0
                        
                        # Sum for datacenter averages
                        dc_cpu_sum += cpu_usage_sum
                        dc_ram_sum += ram_usage_sum
                        dc_host_count += host_count
                    
                    # Aggregate to datacenter
                    dc_data['total_physical_cores'] += cl_data['total_physical_cores']
                    dc_data['total_physical_ram_gb'] += cl_data['total_physical_ram_gb']
                
                dc_data['cluster_count'] = len(dc_data['clusters'])
                dc_data['host_count'] = dc_host_count
                
                # Datacenter average usage
                if dc_host_count > 0:
                    dc_data['avg_cpu_usage_pct'] = round(dc_cpu_sum / dc_host_count, 1)
                    dc_data['avg_ram_usage_pct'] = round(dc_ram_sum / dc_host_count, 1)
        
        return jsonify(hierarchy)
        
    except Exception as e:
        print(f"Error in hosts-clusters: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory')
def api_inventory():
    """Get inventory tree structure"""
    vinfo = get_combined_data('vInfo')
    
    # Tree stucture: Datacenter -> Cluster -> Host -> VM
    tree = {}
    
    for _, row in vinfo.iterrows():
        source = row['Source']
        datacenter = row.get('Datacenter', 'Unknown Datacenter')
        cluster = row.get('Cluster', 'Unknown Cluster')
        host = row.get('Host', 'Unknown Host')
        vm_name = row['VM']
        vm_id = row.get('VM ID', '')
        power_state = row.get('Powerstate', 'poweredOff')
        
        # Initialize hierarchy
        if source not in tree:
            tree[source] = {}
        if datacenter not in tree[source]:
            tree[source][datacenter] = {}
        if cluster not in tree[source][datacenter]:
            tree[source][datacenter][cluster] = {}
        if host not in tree[source][datacenter][cluster]:
            tree[source][datacenter][cluster][host] = []
            
        # Add VM
        tree[source][datacenter][cluster][host].append({
            'name': vm_name,
            'id': vm_id,
            'power_state': power_state
        })
        
    return jsonify(tree)

# ============================================
# PDF Export Endpoint
# ============================================
@app.route('/api/reports/pdf/<report_type>')
def api_export_pdf(report_type):
    """Generate PDF report with Turkish character support"""
    from pdf_generator import generate_optimization_pdf
    from flask import Response
    
    try:
        # Get rightsizing data using Flask test client
        with app.test_request_context():
            rightsizing_response = api_rightsizing()
            response_data = rightsizing_response.get_json()
        
        # Extract recommendations list from response
        if isinstance(response_data, dict) and 'recommendations' in response_data:
            rightsizing_data = response_data['recommendations']
        elif isinstance(response_data, list):
            rightsizing_data = response_data
        else:
            rightsizing_data = []
        
        # Filter based on report type (not for 'all' or 'rightsizing')
        if report_type not in ['all', 'rightsizing']:
            rightsizing_data = [r for r in rightsizing_data if isinstance(r, dict) and r.get('type') == report_type]
        
        # Logo path (dikdortgen logo)
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'images', 'logo.png')
        
        # Generate PDF
        pdf_buffer = generate_optimization_pdf(rightsizing_data, report_type, logo_path)
        
        # Return PDF
        filename = f"RVTools_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{filename}"',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/host_hardware/<host_name>')
def api_host_hardware(host_name):
    """Get detailed hardware info and additional health/config for a specific host"""
    conn = sqlite3.connect('rvtools.db')
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. Get Physical Info from vHost
        cursor = conn.execute("SELECT * FROM vHost WHERE Host=?", (host_name,))
        host_info = cursor.fetchone()
        if not host_info:
            return jsonify({'error': 'Host not found'}), 404
        
        host_dict = dict(host_info)
        
        # 2. Get HBAs
        cursor = conn.execute("SELECT * FROM vHBA WHERE Host=?", (host_name,))
        hbas = [dict(row) for row in cursor.fetchall()]
        
        # 3. Get NICs
        cursor = conn.execute("SELECT * FROM vNIC WHERE Host=?", (host_name,))
        nics = [dict(row) for row in cursor.fetchall()]
        
        # 4. Get VMKs
        try:
            cursor = conn.execute("SELECT * FROM vSC_VMK WHERE Host=?", (host_name,))
            vmks = [dict(row) for row in cursor.fetchall()]
        except:
            vmks = []

        # 5. Get Storage Disks from vMultiPath
        try:
            cursor = conn.execute("SELECT * FROM vMultiPath WHERE Host=?", (host_name,))
            paths = [dict(row) for row in cursor.fetchall()]
        except:
            paths = []

        # 6. Get Health Issues (Filter by Host name or VM names on this host)
        try:
            # First get VM list on this host
            cursor = conn.execute("SELECT VM FROM vInfo WHERE Host=?", (host_name,))
            vm_names = [row[0] for row in cursor.fetchall()]
            
            # Search vHealth for host or its VMs
            placeholders = ','.join(['?'] * (len(vm_names) + 1))
            query = f"SELECT * FROM vHealth WHERE Name IN ({placeholders}) OR Message LIKE ?"
            params = vm_names + [host_name, f"%{host_name}%"]
            cursor = conn.execute(query, params)
            health = [dict(row) for row in cursor.fetchall()]
        except:
            health = []

        # 7. Get Critical Partitions for VMs on this host
        try:
            placeholders = ','.join(['?'] * len(vm_names))
            cursor = conn.execute(f"SELECT * FROM vPartition WHERE VM IN ({placeholders}) AND \"Free %\" < 10", vm_names)
            partitions = [dict(row) for row in cursor.fetchall()]
        except:
            partitions = []

        # 8. Get Snapshots for VMs on this host
        try:
            placeholders = ','.join(['?'] * len(vm_names))
            cursor = conn.execute(f"SELECT * FROM vSnapshot WHERE VM IN ({placeholders})", vm_names)
            snapshots = [dict(row) for row in cursor.fetchall()]
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


@app.route('/api/risks')
def api_risks():
    """Analyze infrastructure for various risks (OS EOL, BIOS Age, HW Versions, etc.)"""
    conn = sqlite3.connect('rvtools.db')
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. Fetch Data
        vinfo = pd.read_sql_query("SELECT VM, Powerstate, \"OS according to the configuration file\" as OS, \"HW version\", Host, Source FROM vInfo", conn)
        vhost = pd.read_sql_query("SELECT Host, Vendor, Model, \"BIOS Version\", \"BIOS Date\", \"ESX Version\", Source FROM vHost", conn)
        vhealth = pd.read_sql_query("SELECT * FROM vHealth", conn)
        
        risks = []
        
        # --- OS Risks ---
        eol_os_patterns = [
            r'Windows Server 2003', r'Windows Server 2008', r'Windows Server 2012',
            r'CentOS 7', r'CentOS 6', r'CentOS 5',
            r'Red Hat Enterprise Linux [456]',
            r'Ubuntu 1[0246]\.', r'Debian [6789]'
        ]
        
        unique_os = vinfo['OS'].dropna().unique()
        os_risk_map = {}
        for os_name in unique_os:
            is_eol = False
            for pattern in eol_os_patterns:
                if re.search(pattern, str(os_name), re.I):
                    is_eol = True
                    break
            if is_eol:
                os_risk_map[os_name] = "End of Life (EOL) İşletim Sistemi. Güvenlik ve destek riskleri mevcut."

        for _, vm in vinfo.iterrows():
            if vm['OS'] in os_risk_map:
                risks.append({
                    'target': vm['VM'],
                    'type': 'OS_EOL',
                    'severity': 'Critical',
                    'category': 'Software',
                    'description': f"VM '{vm['VM']}' üzerinde eski bir OS ({vm['OS']}) çalışıyor.",
                    'recommendation': "İşletim sistemini desteklenen bir sürüme yükseltin.",
                    'source': vm['Source']
                })

        # --- Hardware / ESXi Risks ---
        for _, host in vhost.iterrows():
            # ESXi Version Check
            esx_ver = str(host['ESX Version'])
            if '6.' in esx_ver or '5.' in esx_ver:
                risks.append({
                    'target': host['Host'],
                    'type': 'ESXI_OUTDATED',
                    'severity': 'High',
                    'category': 'Hypervisor',
                    'description': f"Host '{host['Host']}' üzerinde eski ESXi sürümü ({esx_ver}) yüklü.",
                    'recommendation': "ESXi 7.0 veya 8.0 sürümüne yükseltme planlayın.",
                    'source': host['Source']
                })
            
            # BIOS Age Check
            try:
                bios_date_str = str(host['BIOS Date'])
                # RVTools usually formats it like '2020-05-12' or '05/12/2020'
                # Simplistic check: find the year
                year_match = re.search(r'(19|20)\d{2}', bios_date_str)
                if year_match:
                    year = int(year_match.group(0))
                    if year < 2021:
                        risks.append({
                            'target': host['Host'],
                            'type': 'BIOS_OUTDATED',
                            'severity': 'Medium',
                            'category': 'Hardware',
                            'description': f"BIOS tarihi ({bios_date_str}) 3 yıldan eski. Güvenlik açıkları (Spectre/Meltdown vb.) ve stabilite riskleri olabilir.",
                            'recommendation': "En güncel BIOS/Firmware sürümünü vendor sitesinden kontrol edip uygulayın.",
                            'source': host['Source']
                        })
            except:
                pass

        # --- vHealth Integration ---
        for _, h in vhealth.iterrows():
            severity = 'High' if str(h.get('Message type', '')).lower() == 'critical' else 'Medium'
            risks.append({
                'target': h.get('Name', 'Global'),
                'type': 'RV_HEALTH',
                'severity': severity,
                'category': 'Operation',
                'description': h.get('Message', ''),
                'recommendation': "RVTools Health tablosundaki detayları inceleyin.",
                'source': h.get('Source', '')
            })

        # --- AI Powered Insights (Experimental) ---
        # Generate a prompt for Grok if there are significant findings
        if len(risks) > 0:
            os_list = ", ".join(list(os_risk_map.keys())[:10])
            host_models = ", ".join(vhost['Model'].unique().tolist()[:5])
            
            ai_prompt = f"""
            Aşağıdaki sanallaştırma altyapısı verilerine dayanarak en kritik 3 riski ve çözüm önerisini Türkçe olarak kısa maddeler halinde belirt:
            - Eski OS'lar: {os_list}
            - Sunucu Modelleri: {host_models}
            - ESXi Sürümleri: {vhost['ESX Version'].unique().tolist()}
            """
            
            ai_insight = ai.call_grok(ai_prompt, system_prompt="Sen bir sanallaştırma ve siber güvenlik uzmanısın. Riskleri teknik ama yönetici özeti şeklinde sun.")
        else:
            ai_insight = "Şu an için altyapıda kritik bir konfigürasyonel risk tespit edilmedi."

        return jsonify({
            'risks': risks,
            'ai_insight': ai_insight,
            'stats': {
                'critical_count': len([r for r in risks if r['severity'] == 'Critical']),
                'high_count': len([r for r in risks if r['severity'] == 'High']),
                'medium_count': len([r for r in risks if r['severity'] == 'Medium']),
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    print("Starting RVTools Visualization Server...")
    print(f"Data directory: {DATA_DIR}")
    init_db() # Initialize DB
    app.run(host='0.0.0.0', port=5050, debug=True)
