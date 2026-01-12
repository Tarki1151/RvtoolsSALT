"""
Risks API Routes - Infrastructure risk analysis
"""
from flask import Blueprint, jsonify, request
import pandas as pd
import re

from utils.db import get_db_connection
import ai_utils as ai

risks_bp = Blueprint('risks', __name__, url_prefix='/api')


# EOL OS patterns
EOL_OS_PATTERNS = [
    r'Windows Server 2003', r'Windows Server 2008', r'Windows Server 2012',
    r'CentOS 7', r'CentOS 6', r'CentOS 5',
    r'Red Hat Enterprise Linux [456]',
    r'Ubuntu 1[0246]\.', r'Debian [6789]'
]


def check_os_risks(vinfo):
    """Check for end-of-life operating systems"""
    risks = []
    unique_os = vinfo['OS'].dropna().unique()
    os_risk_map = {}
    
    for os_name in unique_os:
        for pattern in EOL_OS_PATTERNS:
            if re.search(pattern, str(os_name), re.I):
                os_risk_map[os_name] = "End of Life (EOL) İşletim Sistemi"
                break

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
    
    return risks, os_risk_map


def check_host_risks(vhost):
    """Check for outdated ESXi and BIOS"""
    risks = []
    
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
            year_match = re.search(r'(19|20)\d{2}', bios_date_str)
            if year_match:
                year = int(year_match.group(0))
                if year < 2021:
                    risks.append({
                        'target': host['Host'],
                        'type': 'BIOS_OUTDATED',
                        'severity': 'Medium',
                        'category': 'Hardware',
                        'description': f"BIOS tarihi ({bios_date_str}) 3 yıldan eski.",
                        'recommendation': "En güncel BIOS/Firmware sürümünü vendor sitesinden kontrol edip uygulayın.",
                        'source': host['Source']
                    })
        except:
            pass
    
    return risks


def check_vhealth_risks(vhealth):
    """Check vHealth for reported issues"""
    risks = []
    
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
    
    return risks


@risks_bp.route('/ai/remediation')
def api_remediation():
    """Get AI-powered remediation advice"""
    message = request.args.get('message')
    if not message:
        return jsonify({'error': 'Message required'}), 400
    
    from ai_utils import get_remediation_advice
    advice = get_remediation_advice(message)
    
    return jsonify({
        'message': message,
        'remediation': advice
    })


@risks_bp.route('/risks')
def api_risks():
    """Analyze infrastructure for various risks"""
    conn = get_db_connection()
    
    try:
        # Fetch Data
        vinfo = pd.read_sql_query(
            'SELECT VM, Powerstate, "OS according to the configuration file" as OS, "HW version", Host, Source FROM vInfo',
            conn
        )
        vhost = pd.read_sql_query(
            'SELECT Host, Vendor, Model, "BIOS Version", "BIOS Date", "ESX Version", Source FROM vHost',
            conn
        )
        vhealth = pd.read_sql_query("SELECT * FROM vHealth", conn)
        
        risks = []
        
        # Check all risk categories
        os_risks, os_risk_map = check_os_risks(vinfo)
        risks.extend(os_risks)
        
        host_risks = check_host_risks(vhost)
        risks.extend(host_risks)
        
        vhealth_risks = check_vhealth_risks(vhealth)
        risks.extend(vhealth_risks)

        # AI Powered Insights
        ai_insight = "Şu an için altyapıda kritik bir konfigürasyonel risk tespit edilmedi."
        if len(risks) > 0:
            os_list = ", ".join(list(os_risk_map.keys())[:10])
            host_models = ", ".join(vhost['Model'].unique().tolist()[:5])
            
            ai_prompt = f"""
            Aşağıdaki sanallaştırma altyapısı verilerine dayanarak en kritik 3 riski ve çözüm önerisini Türkçe olarak kısa maddeler halinde belirt:
            - Eski OS'lar: {os_list}
            - Sunucu Modelleri: {host_models}
            - ESXi Sürümleri: {vhost['ESX Version'].unique().tolist()}
            """
            
            ai_insight = ai.call_grok(
                ai_prompt, 
                system_prompt="Sen bir sanallaştırma ve siber güvenlik uzmanısın. Riskleri teknik ama yönetici özeti şeklinde sun."
            )

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
