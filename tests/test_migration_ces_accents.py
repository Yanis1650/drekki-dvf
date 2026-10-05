"""Tests de la migration `fix_ces_potentiel_accents.sql`.

Elle corrige, sur une base deja construite, le CES potentiel des parcelles dont
`type_usage` porte un accent — « Résidentiel collectif » et « Dépendance » —
que l'etape densification comparait a des litteraux sans accent.

Une migration ne se relit pas : elle s'execute une fois sur une base de 1,6 Go
et il est trop tard. Ce qu'elle ne doit *pas* toucher compte donc autant que ce
qu'elle corrige : une valeur posee ensuite par GPU, BD TOPO ou RNU ne doit pas
etre ecrasee, et un usage deja juste ne doit pas bouger.
"""

from pathlib import Path

import duckdb
import pytest

MIGRATION = Path(__file__).parent.parent / "migrations" / "fix_ces_potentiel_accents.sql"

# id, type_usage, source_ces, ces_actuel, ces_potentiel, potentiel, surface, categorie
LIGNES = [
    # Corrigees : le defaut 0,40 doit ceder la place a la valeur de l'usage.
    ("P_COLLECTIF", "Résidentiel collectif", "bdnb_emprise", 0.10, 0.40, 0.30, 3000.0, "FORT"),
    ("P_DEPENDANCE", "Dépendance", "bdnb_emprise", 0.10, 0.40, 0.30, 3000.0, "FORT"),
    # Sans emprise : le potentiel vaut la moitie du CES potentiel.
    ("P_USAGE_SEUL", "Dépendance", "bdnb_usage_only", None, 0.40, 0.20, None, "MOYEN"),
    # Intouchables : la source dit que la valeur vient d'une etape ulterieure.
    ("P_PLU", "Résidentiel collectif", "plu_gpu", 0.10, 0.05, 0.00, 0.0, "SATURE"),
    ("P_RNU", "Dépendance", "rnu_proximite", 0.10, 0.30, 0.20, 2000.0, "MOYEN"),
    ("P_BDTOPO", "Résidentiel collectif", "bdtopo", 0.10, 0.50, 0.40, 4000.0, "FORT"),
    # Intouchables : ces usages correspondaient deja, avec ou sans accent.
    ("P_INDIVIDUEL", "Résidentiel individuel", "bdnb_emprise", 0.10, 0.40, 0.30, 3000.0, "FORT"),
    ("P_TERTIAIRE", "Tertiaire & Autres", "bdnb_emprise", 0.10, 0.60, 0.50, 5000.0, "FORT"),
    ("P_SANS_USAGE", None, "bdnb_emprise", 0.10, 0.40, 0.30, 3000.0, "FORT"),
]


@pytest.fixture
def base(tmp_path):
    """Base au schema de `densification_scores` apres un build complet."""
    chemin = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR, code_commune VARCHAR,
            surface_parcelle_m2 DOUBLE, surface_plancher_m2 DOUBLE,
            emprise_sol_m2 DOUBLE, ces_actuel DOUBLE, ces_potentiel DECIMAL(3,2),
            potentiel_densification DOUBLE, surface_constructible_restante DOUBLE,
            source_ces VARCHAR, type_usage VARCHAR, nb_niveau INTEGER,
            categorie VARCHAR, plu_datappro DATE, libelle_zone VARCHAR,
            zone_non_mutable BOOLEAN
        )
    """)
    for ident, usage, source, actuel, potentiel_ces, potentiel, surface, categorie in LIGNES:
        conn.execute(
            "INSERT INTO densification_scores VALUES"
            " (?, '35238', 10000.0, 1000.0, 1000.0, ?, ?, ?, ?, ?, ?, 1, ?,"
            "  DATE '2020-01-01', 'UB', FALSE)",
            [ident, actuel, potentiel_ces, potentiel, surface, source, usage, categorie],
        )
    conn.close()
    return chemin


def appliquer(chemin) -> None:
    conn = duckdb.connect(str(chemin))
    try:
        conn.execute(MIGRATION.read_text(encoding="utf-8"))
    finally:
        conn.close()


def lire(chemin) -> dict:
    conn = duckdb.connect(str(chemin), read_only=True)
    lignes = conn.execute("""
        SELECT id_parcelle, ces_potentiel, potentiel_densification,
               surface_constructible_restante, categorie
        FROM densification_scores
    """).fetchall()
    conn.close()
    return {r[0]: (float(r[1]), r[2], r[3], r[4]) for r in lignes}


def test_les_deux_usages_accentues_sont_corriges(base):
    """0,60 pour le collectif, 0,25 pour la dependance, et tout ce qui en decoule."""
    appliquer(base)
    apres = lire(base)

    ces, potentiel, surface, categorie = apres["P_COLLECTIF"]
    assert ces == 0.60
    assert potentiel == pytest.approx(0.50)          # 0,60 - 0,10
    assert surface == pytest.approx(5000.0)          # 0,50 x 10 000 m2
    assert categorie == "FORT"

    ces, potentiel, surface, categorie = apres["P_DEPENDANCE"]
    assert ces == 0.25
    assert potentiel == pytest.approx(0.15)          # 0,25 - 0,10
    assert surface == pytest.approx(1500.0)
    assert categorie == "MOYEN"                      # etait FORT a tort


def test_sans_emprise_le_potentiel_est_de_moitie(base):
    """`bdnb_usage_only` : la moitie du CES potentiel, et pas de surface."""
    appliquer(base)
    ces, potentiel, surface, categorie = lire(base)["P_USAGE_SEUL"]

    assert ces == 0.25
    assert potentiel == pytest.approx(0.125)         # 0,25 x 0,5
    assert surface is None
    assert categorie == "MOYEN"


@pytest.mark.parametrize("identifiant", ["P_PLU", "P_RNU", "P_BDTOPO"])
def test_les_valeurs_posees_par_les_etapes_suivantes_survivent(base, identifiant):
    """GPU, RNU et BD TOPO ecrasent le CES apres la densification : ne pas y toucher."""
    avant = lire(base)[identifiant]
    appliquer(base)
    assert lire(base)[identifiant] == avant


@pytest.mark.parametrize("identifiant", ["P_INDIVIDUEL", "P_TERTIAIRE", "P_SANS_USAGE"])
def test_les_usages_deja_justes_ne_bougent_pas(base, identifiant):
    """Ces trois-la correspondaient deja, ou tombaient sur le bon defaut."""
    avant = lire(base)[identifiant]
    appliquer(base)
    assert lire(base)[identifiant] == avant


def test_migration_idempotente(base):
    """Relancee, elle ne trouve plus rien a corriger."""
    appliquer(base)
    apres_une_fois = lire(base)

    appliquer(base)

    assert lire(base) == apres_une_fois


def test_aucune_ligne_perdue(base):
    """Un UPDATE, pas un DROP : le compte et les colonnes PLU restent."""
    appliquer(base)
    conn = duckdb.connect(str(base), read_only=True)
    total, zones = conn.execute("""
        SELECT COUNT(*), COUNT(libelle_zone) FROM densification_scores
    """).fetchone()
    conn.close()

    assert total == len(LIGNES)
    assert zones == len(LIGNES), "les colonnes posees par l'etape GPU doivent survivre"
