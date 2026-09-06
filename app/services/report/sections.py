"""Sections du rapport rendues comme des listes de flowables.

Chacune rend ce qu'elle produit plutot que de l'ajouter a une liste partagee :
c'est ce qui permet de les lire, et de les tester, une par une.
"""

import io

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, Spacer, Table, TableStyle

from app.domain.models import MutationAggregate
from app.services.report.palette import (
    ACCENT_VIF,
    DETAILS_FOND,
    DETAILS_TEXTE,
    PRIX_FOND,
    PRIX_TEXTE,
)


def section_prix(
    mutation: MutationAggregate,
    stats: dict,
    price_chart_buf: io.BytesIO,
    heading_style: ParagraphStyle,
) -> list:
    """Analyse de prix : le tableau de synthese, puis le graphique."""
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(PRIX_FOND)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(PRIX_TEXTE)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))

    return [
        Paragraph("💰 Analyse de Prix (Mericskay)", heading_style),
        t_price,
        Spacer(1, 0.5*cm),
        Image(price_chart_buf, width=16*cm, height=8*cm),
        Spacer(1, 1*cm),
    ]


def section_enrichissement(
    enrichment: dict,
    radar_chart_buf: io.BytesIO | None,
    heading_style: ParagraphStyle,
    normal_style: ParagraphStyle,
) -> list:
    """Scores qualitatifs.

    Omise quand les POI ne sont pas charges : un radar rempli de valeurs par
    defaut serait indiscernable d'une mesure reelle.
    """
    elements = [
        PageBreak(),
        Paragraph("🎯 Score d'Enrichissement Qualitatif", heading_style),
        Spacer(1, 0.5*cm),
    ]

    if not enrichment:
        elements.append(Paragraph(
            "Données d'environnement (transports, écoles, commerces) non "
            "disponibles pour ce secteur : cette section est volontairement "
            "laissée vide plutôt que d'afficher des valeurs par défaut.",
            normal_style,
        ))
        return elements

    big_score_style = ParagraphStyle(
        'BigScore', parent=normal_style, fontSize=18,
        textColor=colors.HexColor(ACCENT_VIF), alignment=1,
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(DETAILS_FOND)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(DETAILS_TEXTE)),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(Spacer(1, 1*cm))
    elements.append(t_details)

    return elements
