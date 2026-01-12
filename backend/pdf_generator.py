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
    
    # Type names mapping (Used ASCII as requested)
    type_names = {
        'all': 'Tum Optimizasyon Onerileri',
        'rightsizing': 'Right-Sizing Onerileri',
        'LOW_CPU_USAGE': 'Dusuk CPU Kullanimi',
        'EOL_OS': 'EOL Isletim Sistemleri',
        'OLD_HW_VERSION': 'Eski Hardware Versiyonlari',
        'VM_TOOLS': 'VMware Tools Sorunlari',
        'OLD_SNAPSHOT': 'Eski Snapshotlar (>7 gun)',
        'LEGACY_NIC': 'Eski Ag Kartlari (E1000)',
        'ZOMBIE_DISK': 'Zombie (Orphan) Diskler',
        'ZOMBIE_RESOURCE': 'Zombie Kaynaklar'
    }
    
    # Detailed explanations for each optimization type (for PDF first page)
    type_explanations = {
        'LOW_CPU_USAGE': {
            'title': 'Dusuk CPU Kullanimi (Right-Sizing)',
            'problem': 'VM\'e atanan vCPU sayisi, uygulama ihtiyacindan fazla. vCPU kullanimi surekli %10\'un altinda kaliyor.',
            'risk': 'Fazla vCPU, ESXi scheduler overhead\'i arttirir ve performansi dusurur (CPU Ready/Costop). Kaynak israfi.',
            'action': 'vCPU sayisini kademeli olarak azaltin ve performansi 48 saat izleyin.'
        },
        'EOL_OS': {
            'title': 'EOL (End-of-Life) Isletim Sistemi',
            'problem': 'Bu VMler artik uretici tarafindan desteklenmeyen isletim sistemleri kullaniyor.',
            'risk': 'KRITIK GUVENLIK RISKI! Yeni guvenlik yamalari alinmiyor. Uyumluluk ve compliance sorunlari.',
            'action': 'ACIL olarak guncel isletim sistemine migrate edin veya network izolasyonu uygulayin.'
        },
        'OLD_HW_VERSION': {
            'title': 'Eski VM Hardware Versiyonu',
            'problem': 'VM hardware versiyonu, ESXi hostun destekledigi maksimum versiyonun altinda.',
            'risk': 'Yeni ozellikler kullanilamaz. Performans iyilestirmelerinden yararlanilamaz. vMotion uyumluluk sorunlari.',
            'action': 'VM\'i kapatip hardware upgrade yapın ve VMware Tools\'u guncelleyin.'
        },
        'VM_TOOLS': {
            'title': 'VMware Tools Sorunu',
            'problem': 'VMware Tools kurulu degil, guncel degil veya calismiyor.',
            'risk': 'Zaman senkronizasyonu bozuk, quiesced snapshot alinmaz, vMotion sirasinda sorun, performans metrikleri eksik.',
            'action': 'VMware Tools\'un son surumunu kurun ve otomatik upgrade politikasini aktifleyin.'
        },
        'OLD_SNAPSHOT': {
            'title': 'Eski Snapshot (>7 Gun)',
            'problem': 'Snapshot 7 gunden uzun suredir mevcut. Snapshotlar gecici olmali, kalici yedek degil.',
            'risk': 'I/O performansi duser (delta disk buyur). Datastore dolar. Yedekleme sureleri uzar.',
            'action': 'Snapshot artik gereksizse hemen silin (Consolidate/Delete).'
        },
        'LEGACY_NIC': {
            'title': 'Eski Ag Karti (E1000/E1000E)',
            'problem': 'VM, emule edilen eski E1000 ag kartini kullaniyor. VMXNET3\'e gore cok daha verimsiz.',
            'risk': 'Dusuk ag performansi. Yuksek CPU kullanimi. Modern offload ozellikleri desteklenmez.',
            'action': 'NIC tipini VMXNET3 olarak degistirin. MAC adresi degisebilir, IP kontrolu yapin.'
        },
        'ZOMBIE_DISK': {
            'title': 'Zombie (Orphaned) Disk Dosyasi',
            'problem': 'Datastore\'da disk dosyasi var ancak hicbir VM konfigurasyonuna kayitli degil.',
            'risk': 'Storage israfi. Karmasik envanter yonetimi. Yedekleme ve temizlik sureclerinde kafa karisikligi.',
            'action': 'Dosyalari inceleyin. Kesinlikle kullanilmadigindan eminseniz datastore\'dan kalici olarak silin.'
        }
    }
    
    # Type labels for table
    type_labels = {
        'LOW_CPU_USAGE': 'Dusuk CPU',
        'EOL_OS': 'EOL OS',
        'OLD_HW_VERSION': 'Eski HW',
        'VM_TOOLS': 'VM Tools',
        'OLD_SNAPSHOT': 'Eski Snapshot',
        'LEGACY_NIC': 'Eski NIC',
        'ZOMBIE_DISK': 'Zombie Disk',
        'ZOMBIE_RESOURCE': 'Bagli ISO',
        'NUM_ALIGNMENT': 'NUMA',
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
    elements.append(Paragraph(turkish_to_ascii(f"RVTools - {report_title}"), title_style))
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
        for item in rightsizing_data[:250]:  # Limit to 250 rows
            table_data.append([
                Paragraph(turkish_to_ascii(str(item.get('vm', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('severity', ''))), cell_style),
                Paragraph(turkish_to_ascii(type_labels.get(item.get('type', ''), item.get('type', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('reason', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('current_value', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('recommended_value', ''))), cell_style),
                Paragraph(turkish_to_ascii(str(item.get('potential_savings', ''))), cell_style)
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
