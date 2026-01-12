#!/usr/bin/env python3
"""
DR Tespit Test Scripti
Replika VM'leri ve eşleştirmeleri analiz eder
"""

import sqlite3
import pandas as pd
from collections import defaultdict

# Veritabanına bağlan
conn = sqlite3.connect('rvtools.db')

# VM verilerini yükle
print("=" * 80)
print("DR TESPİT ANALİZİ")
print("=" * 80)

# 1. Tüm VM'leri yükle
df_vms = pd.read_sql_query("""
    SELECT VM, Powerstate, CPUs, Memory, "Total disk capacity MiB" as DiskMiB,
           Host, Cluster, Datacenter, Source
    FROM vInfo
""", conn)

# Sayısal kolonları düzelt
df_vms['CPUs'] = pd.to_numeric(df_vms['CPUs'], errors='coerce').fillna(0)
df_vms['Memory'] = pd.to_numeric(df_vms['Memory'], errors='coerce').fillna(0)
df_vms['DiskMiB'] = pd.to_numeric(df_vms['DiskMiB'], errors='coerce').fillna(0)

print(f"\n📊 GENEL İSTATİSTİKLER:")
print(f"   Toplam VM: {len(df_vms)}")
print(f"   Powered On: {len(df_vms[df_vms['Powerstate'] == 'poweredOn'])}")
print(f"   Powered Off: {len(df_vms[df_vms['Powerstate'] == 'poweredOff'])}")

# 2. Datacenter dağılımı
print(f"\n📍 DATACENTER DAĞILIMI:")
dc_dist = df_vms.groupby(['Datacenter', 'Powerstate']).size().unstack(fill_value=0)
print(dc_dist.to_string())

# 3. Replika pattern'lerini kontrol et
replica_patterns = ['_dr', '_replica', '_rep', '-dr', '-replica', '-rep', '_backup', '-backup']

def has_replica_pattern(vm_name):
    name_lower = str(vm_name).lower()
    for pattern in replica_patterns:
        if pattern in name_lower:
            return pattern
    return None

def get_base_name(vm_name):
    name = str(vm_name).lower()
    for pattern in replica_patterns:
        if pattern in name:
            return name.replace(pattern, ''), pattern
    return name, None

# Pattern içeren VM'leri bul
df_vms['HasReplicaPattern'] = df_vms['VM'].apply(has_replica_pattern)
pattern_vms = df_vms[df_vms['HasReplicaPattern'].notna()]

print(f"\n🔍 REPLİKA PATTERN'İ İÇEREN VM'LER ({len(pattern_vms)} adet):")
if len(pattern_vms) > 0:
    for _, vm in pattern_vms.head(30).iterrows():
        status = "🔴 Off" if vm['Powerstate'] == 'poweredOff' else "🟢 On"
        print(f"   {status} {vm['VM']} (Pattern: {vm['HasReplicaPattern']}) - DC: {vm['Datacenter']}")
else:
    print("   ❌ Replika pattern'i içeren VM bulunamadı")

# 4. Aynı isimli VM'leri farklı DC'lerde ara
print(f"\n🔄 AYNI İSİMLİ VM'LER (Farklı Datacenter'larda):")
vm_by_name = defaultdict(list)
for _, vm in df_vms.iterrows():
    vm_by_name[vm['VM'].lower()].append({
        'name': vm['VM'],
        'dc': vm['Datacenter'],
        'cluster': vm['Cluster'],
        'state': vm['Powerstate'],
        'source': vm['Source']
    })

duplicates_found = 0
for name, vms in vm_by_name.items():
    if len(vms) > 1:
        # Farklı DC'lerde mi kontrol et
        dcs = set(v['dc'] for v in vms)
        if len(dcs) > 1:
            duplicates_found += 1
            if duplicates_found <= 20:
                print(f"\n   📍 '{name}':")
                for v in vms:
                    status = "🔴" if v['state'] == 'poweredOff' else "🟢"
                    print(f"      {status} DC: {v['dc']}, Cluster: {v['cluster']}, State: {v['state']}")

if duplicates_found == 0:
    print("   ❌ Farklı DC'lerde aynı isimli VM bulunamadı")
else:
    print(f"\n   📊 Toplam {duplicates_found} VM farklı DC'lerde bulunuyor")

# 5. Potential DR çiftlerini manuel eşleştir
print(f"\n🔗 POTANSİYEL DR EŞLEŞTİRMELERİ:")

production = df_vms[df_vms['Powerstate'] == 'poweredOn'].copy()
offline = df_vms[df_vms['Powerstate'] == 'poweredOff'].copy()

# Base name ile eşleştir
production['BaseName'] = production['VM'].apply(lambda x: get_base_name(x)[0])
offline['BaseName'] = offline['VM'].apply(lambda x: get_base_name(x)[0])

matches = []
for _, off_vm in offline.iterrows():
    base = off_vm['BaseName']
    
    # Aynı base name ile production VM ara
    prod_matches = production[production['BaseName'] == base]
    
    for _, prod_vm in prod_matches.iterrows():
        # Farklı DC olmalı
        if prod_vm['Datacenter'] != off_vm['Datacenter']:
            matches.append({
                'prod_vm': prod_vm['VM'],
                'prod_dc': prod_vm['Datacenter'],
                'prod_cluster': prod_vm['Cluster'],
                'replica_vm': off_vm['VM'],
                'replica_dc': off_vm['Datacenter'],
                'replica_cluster': off_vm['Cluster'],
                'vcpu': int(prod_vm['CPUs']),
                'ram_gb': round(prod_vm['Memory'] / 1024, 2)
            })

if len(matches) > 0:
    print(f"   ✅ {len(matches)} eşleştirme bulundu:\n")
    for m in matches[:30]:
        print(f"   🟢 {m['prod_vm']} ({m['prod_dc']}/{m['prod_cluster']})")
        print(f"      ↓ replika ↓")
        print(f"   🔴 {m['replica_vm']} ({m['replica_dc']}/{m['replica_cluster']})")
        print(f"      Kaynak: {m['vcpu']} vCPU, {m['ram_gb']} GB RAM")
        print()
else:
    print("   ❌ Otomatik eşleştirme bulunamadı")

# 6. DC akışları özeti
if len(matches) > 0:
    print(f"\n📈 DC REPLIKASYON AKIŞLARI:")
    flows = defaultdict(lambda: {'count': 0, 'vcpu': 0, 'ram': 0})
    for m in matches:
        key = f"{m['prod_dc']} → {m['replica_dc']}"
        flows[key]['count'] += 1
        flows[key]['vcpu'] += m['vcpu']
        flows[key]['ram'] += m['ram_gb']
    
    for flow, stats in flows.items():
        print(f"   {flow}: {stats['count']} VM, {stats['vcpu']} vCPU, {stats['ram']:.1f} GB RAM")

# 7. Öneriler
print(f"\n💡 ÖNERİLER:")
print(f"   - Veritabanında {len(offline)} kapalı VM var")
print(f"   - Bunların {len(pattern_vms[pattern_vms['Powerstate'] == 'poweredOff'])} tanesi replika pattern'i içeriyor")
print(f"   - Eşleştirme mantığını iyileştirmek için VM isimlendirme kurallarınızı kontrol edin")

conn.close()
print("\n" + "=" * 80)
