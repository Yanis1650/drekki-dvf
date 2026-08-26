"""Report Generator Service.

Handles the generation of charts (Matplotlib) and PDF documents (ReportLab).
"""

import io
import logging
from datetime import datetime

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from shapely import wkt
from shapely.geometry import Polygon as ShapelyPolygon

from app.domain.models import MutationAggregate, Parcelle

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generates visual assets and PDF reports."""

    def generate_price_chart(self, mutation: MutationAggregate, stats: dict) -> io.BytesIO:
        """Generate price comparison chart."""
        fig, ax = plt.subplots(figsize=(8, 4))

        categories = ['Minimum', 'Ce bien', 'Médiane', 'Maximum']
        prices = [
            float(stats.get('min_price_m2', 0)),
            float(mutation.prix_m2 or 0),
            float(stats.get('median_price_m2', 0)),
            float(stats.get('max_price_m2', 0)),
        ]
        colors_list = ['#94a3b8', '#22c55e', '#6366f1', '#94a3b8']

        bars = ax.bar(categories, prices, color=colors_list, edgecolor='white', linewidth=2)
        bars[1].set_edgecolor('#16a34a')
        bars[1].set_linewidth(3)

        ax.set_ylabel('Prix au m² (€)')
        ax.set_title('Comparaison Quartier')

        for bar, price in zip(bars, prices):
            height = bar.get_height()
            ax.annotate(f'{price:,.0f} €',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        return buffer

    def generate_radar_chart(self, enrichment: dict) -> io.BytesIO | None:
        """Radar des scores d'enrichissement, ou None si aucun score reel.

        Les defauts a 5/10 dessinaient un profil parfaitement moyen meme sans
        aucune donnee : impossible pour le lecteur de distinguer « secteur
        moyen » de « rien mesure ».
        """
        if not enrichment:
            return None

        categories = ['Éducation', 'Transport', 'Commerce', 'Environnement']
        scores = [
            float(enrichment.get('education_score', 0)),
            float(enrichment.get('transport_score', 0)),
            float(enrichment.get('commerce_score', 0)),
            float(enrichment.get('green_spaces_score', 0)),
        ]

        # Close the polygon
        scores_plot = scores + [scores[0]]
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

        ax.fill(angles, scores_plot, color='#6366f1', alpha=0.25)
        ax.plot(angles, scores_plot, color='#6366f1', linewidth=2)
        ax.scatter(angles[:-1], scores, color='#6366f1', s=50)

        # Labels
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 10)
        ax.set_yticks([2, 4, 6, 8, 10])
        ax.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=8, color='grey')

        ax.set_title('Profil Qualitatif', pad=20)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150)
        buffer.seek(0)
        plt.close(fig)
        return buffer

    def generate_parcel_map(self, parcelle: Parcelle | None) -> io.BytesIO | None:
        """Generate a static map image of the parcel geometry."""
        if not parcelle or not parcelle.geometry_wkt:
            return None

        try:
            poly = wkt.loads(parcelle.geometry_wkt)

            fig, ax = plt.subplots(figsize=(6, 6))

            if isinstance(poly, ShapelyPolygon):
                x, y = poly.exterior.xy
                ax.fill(x, y, alpha=0.5, fc='#6366f1', ec='#4338ca', linewidth=2)
            else:
                # MultiPolygon
                for geom in poly.geoms:
                    x, y = geom.exterior.xy
                    ax.fill(x, y, alpha=0.5, fc='#6366f1', ec='#4338ca', linewidth=2)

            ax.set_aspect('equal')
            ax.axis('off')  # Hide axes
            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, transparent=True)
            buffer.seek(0)
            plt.close(fig)
            return buffer
        except Exception as e:
            logger.error(f"Failed to plot parcel map: {e}")
            return None

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
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eff6ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
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

        # -- Section 2: Analyse Prix --
        elements.append(Paragraph("💰 Analyse de Prix (Mericskay)", heading_style))

        # Price grid
        price_data = [
            ["Valeur Foncière", "Prix m²", "Médiane Quartier"],
            [
                f"{mutation.valeur_fonciere:,.0f} €",
                f"{mutation.prix_m2:,.0f} €/m²",
                f"{float(stats.get('median_price_m2', 0)):,.0f} €/m²"
            ]
        ]
        t_price = Table(price_data, colWidths=[5*cm]*3)
        t_price.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0fdf4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#166534')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('PADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        elements.append(t_price)
        elements.append(Spacer(1, 0.5*cm))

        # Chart
        img = Image(price_chart_buf, width=16*cm, height=8*cm)
        elements.append(img)
        elements.append(Spacer(1, 1*cm))

        # -- Section 3: Enrichissement --
        # Omise quand les POI ne sont pas charges : un radar rempli de valeurs
        # par defaut serait indiscernable d'une mesure reelle.
        elements.append(PageBreak())
        elements.append(Paragraph("🎯 Score d'Enrichissement Qualitatif", heading_style))
        elements.append(Spacer(1, 0.5*cm))

        if not enrichment:
            elements.append(Paragraph(
                "Données d'environnement (transports, écoles, commerces) non "
                "disponibles pour ce secteur : cette section est volontairement "
                "laissée vide plutôt que d'afficher des valeurs par défaut.",
                normal_style,
            ))
        else:
            big_score_style = ParagraphStyle(
                'BigScore', parent=normal_style, fontSize=18,
                textColor=colors.HexColor('#4f46e5'), alignment=1,
            )
            global_score = float(enrichment.get('global_score', 0))
            elements.append(Paragraph(f"Global Score: <b>{global_score}/10</b>", big_score_style))
            elements.append(Spacer(1, 1*cm))

            if radar_chart_buf is not None:
                elements.append(Image(radar_chart_buf, width=12*cm, height=12*cm))

            details_data = [
                ["Catégorie", "Score"],
                ["Éducation", f"{float(enrichment.get('education_score', 0))}/10"],
                ["Transport", f"{float(enrichment.get('transport_score', 0))}/10"],
                ["Commerce", f"{float(enrichment.get('commerce_score', 0))}/10"],
                ["Environnement", f"{float(enrichment.get('green_spaces_score', 0))}/10"],
            ]
            t_details = Table(details_data, colWidths=[10*cm, 4*cm])
            t_details.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f3ff')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#4c1d95')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(Spacer(1, 1*cm))
            elements.append(t_details)

        # -- Footer --
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("Foncier-Express - Données DVF Open Data & OpenStreetMap",
            ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.gray, alignment=1)
        ))

        doc.build(elements)
        return buffer.getvalue()
