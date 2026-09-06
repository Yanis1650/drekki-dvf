"""Les trois illustrations du rapport : prix, radar de scores, carte.

Chacune rend un PNG en memoire, ou None quand la donnee manque. Ce None
est deliberé : un graphique dessine avec des valeurs par defaut ne se
distingue pas, pour le lecteur, d'une vraie mesure.
"""

import io
import logging

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from shapely import wkt  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402

from app.domain.models import MutationAggregate, Parcelle  # noqa: E402
from app.services.report.palette import (  # noqa: E402
    ACCENT,
    ACCENT_FONCE,
    BIEN,
    BIEN_BORD,
    NEUTRE,
)

logger = logging.getLogger(__name__)


class ReportChartsMixin:
    """Generation des figures matplotlib du rapport."""

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
        colors_list = [NEUTRE, BIEN, ACCENT, NEUTRE]

        bars = ax.bar(categories, prices, color=colors_list, edgecolor='white', linewidth=2)
        bars[1].set_edgecolor(BIEN_BORD)
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

        ax.fill(angles, scores_plot, color=ACCENT, alpha=0.25)
        ax.plot(angles, scores_plot, color=ACCENT, linewidth=2)
        ax.scatter(angles[:-1], scores, color=ACCENT, s=50)

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
                ax.fill(x, y, alpha=0.5, fc=ACCENT, ec=ACCENT_FONCE, linewidth=2)
            else:
                # MultiPolygon
                for geom in poly.geoms:
                    x, y = geom.exterior.xy
                    ax.fill(x, y, alpha=0.5, fc=ACCENT, ec=ACCENT_FONCE, linewidth=2)

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
