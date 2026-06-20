import io
from datetime import datetime, timezone
from typing import List, Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, String as DString
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

from app.models.complaint import Complaint, ComplaintStatus

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to calculate the total page count and draw
    a professional footer with page numbers and a horizontal rule.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Draw top header rule & text (if not page 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#0f4c81"))
            self.drawString(36, letter[1] - 30, "GOVERNMENT OF NCT OF DELHI — GRIEVANCE MONITORING SYSTEM")
            self.setStrokeColor(colors.HexColor("#0f4c81"))
            self.setLineWidth(0.5)
            self.line(36, letter[1] - 35, letter[0] - 36, letter[1] - 35)

        # Draw bottom footer line
        self.setStrokeColor(colors.HexColor("#CCCCCC"))
        self.setLineWidth(0.5)
        self.line(36, 45, letter[0] - 36, 45)
        
        # Footer text
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#555555"))
        self.drawString(36, 30, "Report generated automatically. Delhi Grievance Redressal Monitoring System.")
        
        # Page pageNumber of page_count on the right
        text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 30, text)
        self.restoreState()

class PDFReportGenerator:
    @classmethod
    def generate_report(cls, complaints: List[Complaint], report_type: str, filter_desc: str) -> bytes:
        """
        Generates a premium government analytics report PDF from the complaints list.
        """
        buffer = io.BytesIO()
        # Page size: Letter (8.5 x 11 inches) -> 612 x 792 points.
        # Margins: 0.5 inch (36 points)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        
        # Define Custom Styles
        title_style = ParagraphStyle(
            "GovTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0f4c81"),
            alignment=1, # Centered
            spaceAfter=4
        )
        
        subtitle_style = ParagraphStyle(
            "GovSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#333333"),
            alignment=1,
            spaceAfter=15
        )

        h1_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#0f4c81"),
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#333333")
        )

        card_title_style = ParagraphStyle(
            "CardTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#555555"),
            alignment=1
        )

        card_val_style = ParagraphStyle(
            "CardValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            textColor=colors.HexColor("#0f4c81"),
            alignment=1
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.white
        )

        story = []

        # 1. Government Header Block
        story.append(Paragraph("GOVERNMENT OF NCT OF DELHI", title_style))
        story.append(Paragraph("DEPARTMENT OF DELHI GRIVANCE REDRESSAL — MONITORING SYSTEM", subtitle_style))
        
        # 2. Metadata Table
        now_str = datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC")
        meta_data = [
            [Paragraph("<b>Report Type:</b>", body_style), Paragraph(report_type.upper(), body_style),
             Paragraph("<b>Generated At:</b>", body_style), Paragraph(now_str, body_style)],
            [Paragraph("<b>Filter Scope:</b>", body_style), Paragraph(filter_desc, body_style),
             Paragraph("<b>Total Records:</b>", body_style), Paragraph(str(len(complaints)), body_style)]
        ]
        meta_table = Table(meta_data, colWidths=[80, 200, 80, 180])
        meta_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('LINEBELOW', (0,1), (-1,1), 1, colors.HexColor("#DDDDDD")),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 15))

        # 3. Handle Empty State
        if not complaints:
            empty_style = ParagraphStyle(
                "EmptyState",
                parent=styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=11,
                leading=14,
                textColor=colors.HexColor("#777777"),
                alignment=1,
                spaceBefore=30,
                spaceAfter=30
            )
            story.append(Paragraph("No grievance records found matching the specified report criteria.", empty_style))
            doc.build(story, canvasmaker=NumberedCanvas)
            return buffer.getvalue()

        # 4. Aggregations & Counts
        total_count = len(complaints)
        pending_count = 0
        resolved_count = 0
        escalated_count = 0
        status_counts = {}
        officer_stats = {} # officer_id -> {name, resolved, pending}

        for c in complaints:
            status_counts[c.status.value] = status_counts.get(c.status.value, 0) + 1
            if c.status in (ComplaintStatus.SUBMITTED, ComplaintStatus.PROCESSING, ComplaintStatus.ASSIGNED, ComplaintStatus.ESCALATED):
                pending_count += 1
            if c.status == ComplaintStatus.RESOLVED:
                resolved_count += 1
            if c.status == ComplaintStatus.ESCALATED:
                escalated_count += 1
            
            # Track officer performance
            if c.assigned_officer:
                o_id = c.assigned_to
                if o_id not in officer_stats:
                    officer_stats[o_id] = {"name": c.assigned_officer.name, "resolved": 0, "pending": 0}
                if c.status == ComplaintStatus.RESOLVED:
                    officer_stats[o_id]["resolved"] += 1
                else:
                    officer_stats[o_id]["pending"] += 1

        # Summary Metric Cards Table
        summary_data = [
            [Paragraph("TOTAL COMPLAINTS", card_title_style), Paragraph("PENDING", card_title_style),
             Paragraph("RESOLVED", card_title_style), Paragraph("ESCALATED", card_title_style)],
            [Paragraph(str(total_count), card_val_style), Paragraph(str(pending_count), card_val_style),
             Paragraph(str(resolved_count), card_val_style), Paragraph(str(escalated_count), card_val_style)]
        ]
        summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8F9FA")),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 15))

        # 5. Charts / Visuals Section (Optional, but included for high-end look)
        chart_story = []
        chart_story.append(Paragraph("Status Distribution", h1_style))
        
        # Prepare Pie Chart
        draw = Drawing(540, 160)
        pc = Pie()
        pc.x = 40
        pc.y = 10
        pc.width = 140
        pc.height = 140
        
        # Set data & labels
        sorted_status = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
        pc.data = [val for _, val in sorted_status]
        pc.labels = [f"{key} ({val})" for key, val in sorted_status]
        
        # Custom coloring for pie chart
        color_scheme = [
            colors.HexColor("#0f4c81"), # Primary
            colors.HexColor("#f1c40f"), # Warning/Yellow
            colors.HexColor("#e74c3c"), # Danger/Red
            colors.HexColor("#2ecc71"), # Success/Green
            colors.HexColor("#9b59b6"), # Purple
            colors.HexColor("#34495e"), # Dark Slate
            colors.HexColor("#1abc9c")  # Teal
        ]
        for idx in range(len(pc.data)):
            pc.slices[idx].fillColor = color_scheme[idx % len(color_scheme)]
            
        draw.add(pc)
        
        # Legend
        leg = Legend()
        leg.x = 240
        leg.y = 130
        leg.dx = 8
        leg.dy = 8
        leg.fontName = "Helvetica"
        leg.fontSize = 8
        leg.boxAnchor = 'nw'
        leg.columnMaximum = 5
        leg.colorNamePairs = [(color_scheme[i % len(color_scheme)], sorted_status[i][0]) for i in range(len(sorted_status))]
        draw.add(leg)
        
        chart_story.append(draw)
        story.append(KeepTogether(chart_story))
        story.append(Spacer(1, 15))

        # 6. Officer Performance Section
        officer_story = []
        officer_story.append(Paragraph("Officer Performance Ranking", h1_style))
        
        # Rank by resolved counts descending
        sorted_officers = sorted(officer_stats.values(), key=lambda x: x["resolved"], reverse=True)
        
        if sorted_officers:
            perf_data = [[
                Paragraph("Rank", table_header_style),
                Paragraph("Officer Name", table_header_style),
                Paragraph("Resolved Complaints", table_header_style),
                Paragraph("Pending Tasks", table_header_style)
            ]]
            
            for idx, item in enumerate(sorted_officers, start=1):
                perf_data.append([
                    Paragraph(str(idx), body_style),
                    Paragraph(item["name"], body_style),
                    Paragraph(str(item["resolved"]), body_style),
                    Paragraph(str(item["pending"]), body_style)
                ])
                
            perf_table = Table(perf_data, colWidths=[50, 240, 125, 125])
            perf_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f4c81")),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8F9FA")]),
            ]))
            officer_story.append(perf_table)
        else:
            officer_story.append(Paragraph("No officer assignments recorded for this reporting period.", body_style))
            
        story.append(KeepTogether(officer_story))
        
        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()
