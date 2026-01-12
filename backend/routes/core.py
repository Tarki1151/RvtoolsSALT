"""
Core API Routes - Sources, Stats, Notes, Reload
"""
from flask import Blueprint, jsonify, request, send_from_directory
from datetime import datetime, timedelta
import pandas as pd

from utils.db import get_all_sources, load_excel_data, clear_cache, init_db, get_db_connection
import config as cfg

core_bp = Blueprint('core', __name__)


@core_bp.route('/')
def serve_frontend():
    """Serve the frontend application"""
    from flask import current_app
    return send_from_directory(current_app.static_folder, 'index.html')


@core_bp.route('/api/sources')
def api_sources():
    """Get list of data sources (Excel files)"""
    return jsonify(get_all_sources())


@core_bp.route('/api/stats')
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
        total_memory = vinfo['Memory'].sum() / 1024
        total_cpu = vinfo['CPUs'].sum()
        total_disk = vinfo['Total disk capacity MiB'].sum() / 1024
        
        # Count old snapshots
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


@core_bp.route('/api/reload', methods=['POST'])
def api_reload():
    """Clear cached Excel data and optionally rebuild SQLite DB."""
    try:
        payload = request.get_json(silent=True) or {}
        rebuild_db = bool(payload.get('rebuild_db', False))

        clear_cache()

        if rebuild_db:
            init_db()

        return jsonify({'status': 'success', 'rebuild_db': rebuild_db})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@core_bp.route('/api/notes', methods=['GET', 'POST'])
def api_notes():
    """Get or Save notes"""
    conn = get_db_connection()
    
    if request.method == 'POST':
        try:
            data = request.json
            target_type = data.get('target_type')
            target_name = data.get('target_name')
            note_content = data.get('note_content')
            updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
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
            
    else:  # GET request
        target_type = request.args.get('target_type')
        target_name = request.args.get('target_name')
        
        if not target_type or not target_name:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
            
        cursor = conn.execute(
            'SELECT note_content, updated_at FROM custom_notes WHERE target_type=? AND target_name=?',
            (target_type, target_name)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({'note_content': row['note_content'], 'updated_at': row['updated_at']})
        else:
            return jsonify({'note_content': '', 'updated_at': None})
