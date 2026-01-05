"""
PDF Generator Module for RVTools Reports
Generates professional PDF reports with Turkish character support
"""

import os
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image


def turkish_to_ascii(text):
    """Convert Turkish characters to ASCII for PDF compatibility"""
    if not text:
        return ''
    char_map = {
        'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
    }
    result = str(text)
    for tr_char, en_char in char_map.items():
        result = result.replace(tr_char, en_char)
    return result


def generate_optimization_pdf(rightsizing_data, report_type, logo_path=None):
    """
    Generate optimization report PDF
    
    Args:
        rightsizing_data: List of recommendation dictionaries
        report_type: Type of report (all, rightsizing, EOL_OS, etc.)
        logo_path: Optional path to logo image
    
    Returns:
        BytesIO buffer containing PDF data
    """
    
    # Type names mapping
    type_names = {
        'all': 'Tum Optimizasyon Onerileri',
        'rightsizing': 'Right-Sizing Onerileri',
        'POWERED_OFF_DISK': 'Kapali VM - Disk Kullanimi',
        'CPU_UNDERUTILIZED': 'Dusuk CPU Kullanimi',
        'EOL_OS': 'EOL Isletim Sistemleri',
        'OLD_HW_VERSION': 'Eski Hardware Versiyonlari',
        'VM_TOOLS': 'VMware Tools Sorunlari',
        'CPU_LIMIT': 'CPU Limiti Tanimli VMler',
        'OLD_SNAPSHOT': 'Eski Snapshotlar (>7 gun)',
        'LEGACY_NIC': 'Eski Ag Kartlari (E1000)',
        'CONSOLIDATE_SNAPSHOTS': 'Snapshot Birlestirme'
    }
    
    # Detailed explanations for each optimization type (for PDF first page)
    type_explanations = {
        'POWERED_OFF_DISK': {
            'title': 'Kapali VM - Disk Kullanimi',
            'problem': 'Bu VMler kapali durumda ancak disk alani hala kullaniliyor. Kapali VMler CPU ve RAM tuketmez ancak depolama maliyetine devam eder.',
            'risk': 'Gereksiz depolama maliyeti, datastore alaninin israfi, yedekleme surelerinin uzamasi.',
            'action': '1. VM artik gerekli degilse tamamen silin. 2. Yedek/DR amacliysa template\'e donusturun. 3. Arsiv gerekiyorsa export edip datatore\'dan kaldirin.'
        },
        'CPU_UNDERUTILIZED': {
            'title': 'Dusuk CPU Kullanimi',
            'problem': 'VM\'e atanan vCPU sayisi, uygulama ihtiyacindan fazla. vCPU kullanimi surekli %50\'nin altinda kaliyor.',
            'risk': 'Fazla vCPU, ESXi scheduler overhead\'i arttirir ve performansi dusurur. Diger VM\'lerin kaynak erisimini engeller.',
            'action': '1. vCPU sayisini azaltin (genellikle yarisina indirin). 2. NUMA uyumu icin: Cores per Socket sayisini host NUMA node core sayisina bolunebilir yapin (ornek: 8 vCPU = 1x8 veya 2x4). 3. Degisiklik sonrasi 1 hafta izleyin.'
        },
        'EOL_OS': {
            'title': 'EOL (End-of-Life) Isletim Sistemi',
            'problem': 'Bu VMler artik uretici tarafindan desteklenmeyen isletim sistemleri kullaniyor (ornegin: Windows Server 2008, CentOS 6).',
            'risk': 'KRITIK GUVENLIK RISKI! Yeni guvenlik yamalari alinmiyor. Uyumluluk ve compliance sorunlari. Yapay Risk skoru nagatifolarak etkileniyor.',
            'action': '1. ACIL olarak guncel isletim sistemine migrate edin. 2. Mumkun degilse network izolasyonu uygulayin. 3. Ozel risk degerlendirmesi ve dokumantasyon hazirlatin.'
        },
        'OLD_HW_VERSION': {
            'title': 'Eski VM Hardware Versiyonu',
            'problem': 'VM\'in hardware versiyonu, ESXi host\'un destekledigi maksimum versiyonun altinda.',
            'risk': 'Yeni ozellikler (USB 3.0, NVMe, vPMEM) kullanilamaz. Performans iyilestirmelerinden yararlanilamaz. vMotion uyumluluk sorunlari.',
            'action': '1. VM\'i kapatin. 2. vCenter/ESXi uzerinden hardware upgrade yapin. 3. VMware Tools\'u guncelleyin. 4. VM\'i tekrar baslatip test edin.'
        },
        'VM_TOOLS': {
            'title': 'VMware Tools Sorunu',
            'problem': 'VMware Tools kurulu degil, guncel degil veya calismiyor.',
            'risk': 'Zaman senkronizasyonu bozuk, quiesced snapshot alinmaz, vMotion sirasinda sorun, performans metrikleri eksik.',
            'action': '1. VMware Tools\'un son surumunu kurun. 2. Otomatik upgrade politikasi aktifleyin. 3. Guest OS saat senkronizasyonunu kontrol edin.'
        },
        'CPU_LIMIT': {
            'title': 'CPU Limiti Tanimli',
            'problem': 'VM\'e CPU limiti tanimlanmis. Host\'ta kaynak olsa bile VM bu kaynagi kullanamaz.',
            'risk': 'PERFORMANS SORUNU! Uygulama yavaslar, kullanici sikayetleri artar. Limit genellikle yanlis cozumdur.',
            'action': '1. CPU limitini kaldirin (Unlimited yapin). 2. Kaynak onceliklendirme gerekiyorsa Shares veya Reservation kullanin. 3. Degisiklik sonrasi performansi izleyin.'
        },
        'RAM_LIMIT': {
            'title': 'RAM Limiti Tanimli',
            'problem': 'VM\'e memory limiti tanimlanmis. Bu, ballooning ve swapping\'e neden olur.',
            'risk': 'CIDDI PERFORMANS SORUNU! Memory limiti neredeyse hicbir zaman dogru cozum degildir. Uygulamalar yavaslar veya coker.',
            'action': '1. Memory limitini hemen kaldirin. 2. Eger host memory yetersizse, VM\'leri baska host\'lara dagitin veya RAM ekleyin.'
        },
        'OLD_SNAPSHOT': {
            'title': 'Eski Snapshot (>7 Gun)',
            'problem': 'Bu snapshot 7 gunden uzak suredir mevcut. Snapshotlar gecici olmali, kalici yedek degil.',
            'risk': 'I/O performansi duser (her yazma isleminde delta disk buyur). Datastore dolar. Yedekleme uzar.',
            'action': '1. Snapshot artik gereksizse hemen silin (Delete). 2. Gecerli bir nedeniniz varsa belgeleyin. 3. Snapshot = yedek degildir, dogru yedekleme cozumu kullanin.'
        },
        'LEGACY_NIC': {
            'title': 'Eski Ag Karti (E1000/E1000E)',
            'problem': 'VM, emule edilen eski E1000 ag kartini kullaniyor. Bu, VMXNET3\'e gore cok yavas.',
            'risk': '10 kata kadar dusuk ag performansi. Yuksek CPU kullanimi. Bazi ozellikler (TSO, LRO) desteklenmez.',
            'action': '1. NIC tipini VMXNET3 olarak degistirin. 2. Guest OS\'te driver otomatik yuklenecektir. 3. IP konfigurasyonunu kontrol edin (MAC adresi degisir).'
        },
        'CONSOLIDATE_SNAPSHOTS': {
            'title': 'Snapshot Birlestirme Gerekli',
            'problem': 'Birden fazla snapshot zinciri var. Her ek snapshot I/O performansini dusurur.',
            'risk': 'Yigin halinde I/O gecikmesi. Storage alani asiri tuketilir. Snapshot silme islemleri uzar veya basarisiz olabilir.',
            'action': '1. Gereksiz snapshotlari silin (en eskisinden baslayin). 2. vCenter\'da Consolidate secenegini kullanin. 3. Islem sirasinda I/O yuku olacagini bilerek plankayarak yapin.'
        },
        'MEMORY_BALLOON': {
            'title': 'Memory Ballooning Aktif',
            'problem': 'ESXi host, bu VM\'den memory geri aliyor cunku host\'ta yeterli fiziksel RAM yok.',
            'risk': 'KRITIK PERFORMANS SORUNU! VM\'deki uygulamalar yavaslar veya out-of-memory hatalari verir. Kullanici deneyimi bozulur.',
            'action': '1. Host\'a fiziksel RAM ekleyin. 2. Bazi VM\'leri baska host\'lara migrate edin. 3. Gereksiz VM\'lerin memory\'sini azaltin. ACIL MUDAHALE GEREKLI!'
        },
        'MEMORY_SWAP': {
            'title': 'Memory Swapping Aktif',
            'problem': 'VM memory\'si diske swap ediliyor. Bu, ballooning\'den de kotu bir durumdur.',
            'risk': 'KRITIK! Disk I/O, RAM\'e gore 1000x yavas. Uygulamalar cok yavas calisir veya zaman asimina ugrar.',
            'action': '1. ACIL: Host\'a RAM ekleyin veya VM\'leri baska host\'lara tasiyin. 2. Swap 0\'a dusene kadar izleyin. 3. Kapasite planlamasini gozden gecirin.'
        },
        'HOST_CPU_OVERCOMMIT': {
            'title': 'Host CPU Overcommit',
            'problem': 'Bu host\'ta toplam vCPU sayisi, fiziksel core sayisina gore yuksek oranda. CPU contention riski var.',
            'risk': 'VM\'ler CPU beklerken %READY suresi artar. Uygulamalar yavaslar. Gizli performans sorunlari olusur.',
            'action': '1. VM\'leri daha az yuklu host\'lara dagitin. 2. Dusuk kullanilan VM\'lerin vCPU\'larini azaltin. 3. Intel icin <6:1, AMD icin <8:1 oran hedefleyin.'
        },
        'DATASTORE_LOW_SPACE': {
            'title': 'Datastore Dusuk Alan',
            'problem': 'Datastore\'da bos alan kritik seviyenin altinda (%15\'in altinda).',
            'risk': 'YUKSEK RISK! VM\'ler dururabilir, snapshot alinamaz, vMotion calismaz. Sistemler tamamen durabilir.',
            'action': '1. ACIL temizlik yapin: eski snapshot, orphan disk, template. 2. Kapali VM\'leri farkli datastore\'a tasiyin. 3. Kapasite eklemeplanlayinin.'
        },
        'DATASTORE_OVERCOMMIT': {
            'title': 'Datastore Overcommit',
            'problem': 'Thin provisioned diskler toplam kapasitenin uzerinde provision edilmis.',
            'risk': 'Thin diskler buyudukce datastore tamamen dolabilir. Ani kapasite sorunu yasanabilir.',
            'action': '1. Datastore kullanimini yakindan izleyin. 2. Alarmlari dogru ayarlayin. 3. Kritik VM\'leri thick provision veya ayri datastore\'a tasiyin.'
        },
        'ZOMBIE_RESOURCE': {
            'title': 'Unutulmus Kaynak (Bagli CD/ISO)',
            'problem': 'VM\'e CD/ISO mount edilmis durumda. Bu genellikle kurulum sonrasi unutulur.',
            'risk': 'vMotion sirasinda sorun cikarabilir. Datastore\'a bagli ISO erisimi olmadisinda VM baslatmas basarisiz olabilir. Guvenlik riski.',
            'action': '1. CD/ISO\'yu disconnect edin. 2. Eger gerekli degilse tamamen kaldirin. 3. DRS ve vMotion uyumlulugunu kontrol edin.'
        },
        'NUMA_ALIGNMENT': {
            'title': 'NUMA Hizalama Sorunu',
            'problem': 'VM\'e tek sayida vCPU atanmis. Modern islemcilerde her NUMA node cift sayida core icerir. Tek sayida vCPU bu yapiyi bozar.',
            'risk': 'Cross-NUMA memory erisimi performansi %30\'a kadar dusurur. CPU cache verimli kullanilamaz. Scheduler ek yuk getirir.',
            'action': '1. vCPU sayisini cift sayiya yuvarlayuin (5->6 veya 5->4). 2. VM Settings > CPU > Cores per Socket ayarini fiziksel NUMA node core sayisina bolunebilir yapin. Ornek: 8 vCPU icin 2 socket x 4 core veya 1 socket x 8 core kullanin. 3. Host\'un NUMA topolojisini esxtop veya vscsiStats ile kontrol edin.'
        },
        'FLOPPY_CONNECTED': {
            'title': 'Floppy Surucu Bagli',
            'problem': 'VM\'de floppy surucu bagli. Bu eski bir cihaz ve modern ortamlarda gereksiz.',
            'risk': 'Potansiyel guvenlik riski. Migration sorunlari. Gereksiz konfigurasyon karmasikligi.',
            'action': '1. Floppy surucuyu disconnect edin. 2. Gerekli degilse VM konfigurasyonundan kaldirin.'
        },
        'STORAGE_OVERPROVISIONED': {
            'title': 'Fazla Provision Edilmis Storage',
            'problem': 'VM\'e provision edilen disk alani, gercekte kullanilan alandan cok yuksek (3x veya daha fazla).',
            'risk': 'Datastore alani israf ediliyor. Kapasite planlamasi yaniltici oluyor.',
            'action': '1. Disk boyutunu kucultunemez ama temizlik yapin. 2. Yeni VM\'ler icin dogru boyutlandirma yapin. 3. Storage vMotion ile thin provisioning kullanin.'
        }
    }
    
    # Type labels for table
    type_labels = {
        'POWERED_OFF_DISK': 'Kapali VM',
        'CPU_UNDERUTILIZED': 'Dusuk CPU',
        'EOL_OS': 'EOL OS',
        'OLD_HW_VERSION': 'Eski HW',
        'VM_TOOLS': 'VM Tools',
        'CPU_LIMIT': 'CPU Limit',
        'RAM_LIMIT': 'RAM Limit',
        'OLD_SNAPSHOT': 'Eski Snapshot',
        'LEGACY_NIC': 'Eski NIC',
        'CONSOLIDATE_SNAPSHOTS': 'Snapshot',
        'MEMORY_BALLOON': 'Ballooning',
        'MEMORY_SWAP': 'Swapping',
        'HOST_CPU_OVERCOMMIT': 'CPU Overcommit',
        'DATASTORE_LOW_SPACE': 'Dusuk Alan',
        'DATASTORE_OVERCOMMIT': 'DS Overcommit',
        'ZOMBIE_RESOURCE': 'Bagli ISO',
        'NUMA_ALIGNMENT': 'NUMA',
        'FLOPPY_CONNECTED': 'Floppy',
        'STORAGE_OVERPROVISIONED': 'Fazla Storage'
    }
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=5,
        textColor=colors.HexColor('#1e293b')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=15
    )
    
    # Explanation styles
    explanation_title_style = ParagraphStyle(
        'ExplanationTitle',
        parent=styles['Heading2'],
        fontSize=11,
        spaceAfter=3,
        spaceBefore=8,
        textColor=colors.HexColor('#1e40af')
    )
    
    explanation_body_style = ParagraphStyle(
        'ExplanationBody',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        spaceAfter=2,
        leftIndent=10
    )
    
    elements = []
    
    # Header with logo
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=40*mm, height=11*mm)
            logo.hAlign = 'LEFT'
            elements.append(logo)
            elements.append(Spacer(1, 5))
        except Exception:
            pass
    
    # Title
    report_title = type_names.get(report_type, f'{report_type} Raporu')
    elements.append(Paragraph(f"RVTools - {report_title}", title_style))
    elements.append(Paragraph(
        f"Olusturulma Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        subtitle_style
    ))
    
    # === ADD EXPLANATIONS PAGE ===
    if rightsizing_data:
        # Find unique types in the data
        types_in_report = set(item.get('type', '') for item in rightsizing_data)
        types_with_explanations = [t for t in types_in_report if t in type_explanations]
        
        if types_with_explanations:
            elements.append(Paragraph("Optimizasyon Turleri ve Onerilen Aksiyonlar", title_style))
            elements.append(Spacer(1, 5))
            
            # Sort by criticality
            severity_order = {'MEMORY_BALLOON': 0, 'MEMORY_SWAP': 1, 'DATASTORE_LOW_SPACE': 2, 'EOL_OS': 3}
            types_with_explanations.sort(key=lambda x: severity_order.get(x, 99))
            
            for opt_type in types_with_explanations[:10]:  # Limit to 10 types per page
                exp = type_explanations.get(opt_type, {})
                if not exp:
                    continue
                    
                # Count items of this type
                count = sum(1 for item in rightsizing_data if item.get('type') == opt_type)
                
                elements.append(Paragraph(
                    f"{turkish_to_ascii(exp.get('title', opt_type))} ({count} adet)",
                    explanation_title_style
                ))
                elements.append(Paragraph(
                    f"<b>Sorun:</b> {turkish_to_ascii(exp.get('problem', ''))}",
                    explanation_body_style
                ))
                elements.append(Paragraph(
                    f"<b>Risk:</b> {turkish_to_ascii(exp.get('risk', ''))}",
                    explanation_body_style
                ))
                elements.append(Paragraph(
                    f"<b>Aksiyon:</b> {turkish_to_ascii(exp.get('action', ''))}",
                    explanation_body_style
                ))
            
            elements.append(Spacer(1, 15))
            elements.append(Paragraph("Detayli Liste", title_style))
            elements.append(Spacer(1, 5))
    
    if rightsizing_data:
        # Cell style for text wrapping
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=7,
            leading=9
        )
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.white,
            leading=10
        )
        
        # Table header with Paragraph for wrapping
        table_data = [[
            Paragraph('VM Adi', header_style),
            Paragraph('Onem', header_style),
            Paragraph('Tip', header_style),
            Paragraph('Neden', header_style),
            Paragraph('Mevcut', header_style),
            Paragraph('Onerilen', header_style),
            Paragraph('Kazanim', header_style)
        ]]
        
        # Add rows with Paragraph wrapping
        for item in rightsizing_data[:150]:  # Limit to 150 rows
            table_data.append([
                Paragraph(turkish_to_ascii(str(item.get('vm', ''))), cell_style),
                Paragraph(str(item.get('severity', '')), cell_style),
                Paragraph(type_labels.get(item.get('type', ''), item.get('type', '')), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('reason', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('current_value', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('recommended_value', ''))), cell_style),
                Paragraph(str(item.get('potential_savings', '')), cell_style)
            ])
        
        # Dynamic column widths for A4 landscape
        # Total usable width: ~760pt (A4 landscape - margins)
        TOTAL_WIDTH = 760
        
        # Fixed widths for short/numeric columns
        FIXED_COLS = {
            1: 45,   # Onem (severity) - always short: HIGH/MEDIUM/LOW
            4: 55,   # Mevcut (current) - numbers like "8 vCPU" or "200 GB"
            5: 70,   # Onerilen (recommended) - numbers
            6: 45,   # Kazanim (savings) - numbers
        }
        fixed_total = sum(FIXED_COLS.values())  # 215
        
        # Remaining width for text columns
        remaining = TOTAL_WIDTH - fixed_total  # ~545
        
        # Text columns: VM Adi (0), Tip (2), Neden (3)
        # VM: 25%, Tip: 15%, Neden: 60%
        col_widths = [
            int(remaining * 0.25),  # 0: VM Adi
            FIXED_COLS[1],          # 1: Onem
            int(remaining * 0.15),  # 2: Tip
            int(remaining * 0.60),  # 3: Neden
            FIXED_COLS[4],          # 4: Mevcut
            FIXED_COLS[5],          # 5: Onerilen
            FIXED_COLS[6],          # 6: Kazanim
        ]
        
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Body
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            
            # All cells
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            f"Toplam: {len(rightsizing_data)} oneri",
            styles['Normal']
        ))
    else:
        elements.append(Paragraph(
            "Bu kategoride oneri bulunamadi.",
            styles['Normal']
        ))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer
