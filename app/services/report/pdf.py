"""Assemblage du document PDF, section par section."""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.models import MutationAggregate
from app.services.report.palette import (
    CADASTRE_FOND,
    CADASTRE_TEXTE,
)
from app.services.report.sections import section_enrichissement, section_prix


class ReportPdfMixin:
    """Mise en page du rapport de faisabilite fonciere."""

    def create_pdf_report(
        self,
        mutation: MutationAggregate,
        stats: dict,
        enrichment: dict,
        price_chart_buf: io.BytesIO,
        radar_chart_buf: io.BytesIO | None,
        map_buf: io.BytesIO | None,
    ) -> bytes:
        """Create PDF using ReportLab."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']

        # Custom styles
        header_style = ParagraphStyle(
            'Header',
            parent=normal_style,
            fontSize=10,
            textColor=colors.gray,
            alignment=2 # Right
        )

        elements = []

        # -- Header --
        elements.append(Paragraph(f"Rapport généré le {datetime.now().strftime('%d/%m/%Y')}", header_style))
        elements.append(Paragraph(f"Ref: {mutation.id_mutation}", header_style))
        elements.append(Spacer(1, 1*cm))

        # -- Title --
        elements.append(Paragraph("Rapport de Faisabilité Foncière", title_style))
        elements.append(Spacer(1, 1*cm))

        # -- Section 1: Infos Cadastrales --
        elements.append(Paragraph("📍 Informations Cadastrales", heading_style))
        elements.append(Spacer(1, 0.5*cm))

        data = [
            [
                Paragraph("<b>Commune</b>", normal_style),
                Paragraph("<b>Date</b>", normal_style),
                Paragraph("<b>Surface</b>", normal_style),
                Paragraph("<b>Locaux</b>", normal_style)
            ],
            [
                mutation.code_commune,
                mutation.date_mutation.strftime("%d/%m/%Y") if mutation.date_mutation else "-",
                f"{mutation.surface_habitable_totale} m²",
                str(mutation.nombre_locaux)
            ]
        ]
        t = Table(data, colWidths=[4*cm]*4)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(CADASTRE_FOND)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(CADASTRE_TEXTE)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.5*cm))

        # Parcelles
        parcelles_str = ", ".join(mutation.parcelles)
        elements.append(Paragraph(f"<b>Parcelles concernées:</b> {parcelles_str}", normal_style))
        elements.append(Spacer(1, 0.5*cm))

        # Map Image
        if map_buf:
            elements.append(Paragraph("<b>Vue Parcellaire:</b>", normal_style))
            elements.append(Spacer(1, 0.2*cm))
            img_map = Image(map_buf, width=10*cm, height=10*cm)
            elements.append(img_map)
            elements.append(Spacer(1, 1*cm))

        elements.extend(section_prix(mutation, stats, price_chart_buf, heading_style))
        elements.extend(
            section_enrichissement(enrichment, radar_chart_buf, heading_style, normal_style)
        )

        # -- Footer --
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("Foncier-Express - Données DVF Open Data & OpenStreetMap",
            ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.gray, alignment=1)
        ))

        doc.build(elements)
        return buffer.getvalue()
