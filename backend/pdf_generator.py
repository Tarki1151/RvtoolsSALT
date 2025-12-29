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
    
    # Type labels for table
    type_labels = {
        'POWERED_OFF_DISK': 'Kapali VM',
        'CPU_UNDERUTILIZED': 'Dusuk CPU',
        'EOL_OS': 'EOL OS',
        'OLD_HW_VERSION': 'Eski HW',
        'VM_TOOLS': 'VM Tools',
        'CPU_LIMIT': 'CPU Limit',
        'OLD_SNAPSHOT': 'Eski Snapshot',
        'LEGACY_NIC': 'Eski NIC',
        'CONSOLIDATE_SNAPSHOTS': 'Snapshot'
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
    
    elements = []
    
    # Header with logo
    if logo_path and os.path.exists(logo_path):
        try:
            # Dikdortgen logo - 40mm x 11mm (oran: 3.64:1)
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
