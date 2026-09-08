"""Tests de l'etape densification — le filet avant de reunir les deux versions.

`etl_build_steps/densification.py` est l'etape reellement executee par
`etl_build_dept.py`, et `data-pipeline/etl_densification.py` en etait une
variante autonome. Leurs formules ne concordaient pas : la seconde compare
`type_usage` a « Résidentiel collectif » et « Dépendance » avec leurs accents,
la premiere sans. Or `bdnb_stats` est un `SELECT *` du Parquet BDNB, qui les
ecrit accentues — les comparaisons sans accent ne peuvent donc jamais aboutir.
Trois des cinq usages tombent ainsi dans le defaut 0,40, et deux en sortent
fausses : « Résidentiel collectif » vaut 0,60 et « Dépendance » 0,25.
« Résidentiel individuel » ne correspond pas davantage, mais son defaut vaut
par chance sa valeur voulue.

Ces tests posent d'abord le reste du bareme — CES actuel, surface de plancher,
source du CES, categories — pour que la correction des accents ne le deplace
pas, puis constatent la correspondance usage -> CES potentiel.

Les parcelles sont des carres en coordonnees planes : `ST_Area` ne fait pas de
geodesie, un carre de 100 sur 100 vaut donc 10 000 m2.
"""

import duckdb
import pytest
from conftest import requires_spatial
from etl_build_steps.densification import step_densification
from etl_build_steps.densification_cli import charger_bdnb, main

DEPT = "35"

# Les cinq valeurs que `usage_niveau_1_txt` prend dans la BDNB, telles qu'elles
# arrivent dans `bdnb_stats`, accents compris.
USAGES = (
    "Résidentiel collectif",
    "Résidentiel individuel",
    "Tertiaire & Autres",
    "Dépendance",
    "Secondaire",
)


def carre(cote: float) -> str:
    """Polygone carre de `cote` unites, donc d'aire `cote` au carre."""
    return f"POLYGON((0 0, {cote} 0, {cote} {cote}, 0 {cote}, 0 0))"


@pytest.fixture
def base():
    """Fabrique une base `parcelles` + `bdnb_stats` et rend la connexion.

    `parcelles` prend des `(id_parcelle, cote_du_carre)`, `bdnb_stats` des
    `(id_parcelle, emprise_sol_m2, hauteur_moyenne, nb_niveau, type_usage)`.
    Passer `bdnb=None` omet la table : c'est le cas sans BDNB.
    """

    def fabriquer(parcelles, bdnb=()):
        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL spatial; LOAD spatial;")
        conn.execute("""
            CREATE TABLE parcelles (
                id_parcelle VARCHAR, code_commune VARCHAR,
                section VARCHAR, numero VARCHAR, geometry GEOMETRY
            )
        """)
        for id_parcelle, cote in parcelles:
            conn.execute(
                "INSERT INTO parcelles VALUES (?, ?, 'AB', '0001', ST_GeomFromText(?))",
                [id_parcelle, id_parcelle[:5], carre(cote)],
            )
        if bdnb is not None:
            conn.execute("""
                CREATE TABLE bdnb_stats (
                    parcelle_id VARCHAR, emprise_sol_m2 DOUBLE,
                    hauteur_moyenne DOUBLE, nb_niveau INTEGER, type_usage VARCHAR
                )
            """)
            for ligne in bdnb:
                conn.execute(
                    "INSERT INTO bdnb_stats VALUES (?, ?, ?, ?, ?)", list(ligne)
                )
        return conn

    return fabriquer


def scores(conn):
    return conn.execute(
        "SELECT id_parcelle, ces_actuel, ces_potentiel, categorie"
        " FROM densification_scores ORDER BY id_parcelle"
    ).fetchall()


# --- La correspondance usage -> CES potentiel -------------------------------


@requires_spatial
def test_ces_potentiel_differencie_par_usage(base):
    """Chaque usage a son CES potentiel ; sans lui, tout vaudrait 0,40."""
    conn = base(
        parcelles=[(f"35238000AB000{i}", 100) for i in range(len(USAGES))],
        bdnb=[
            (f"35238000AB000{i}", 1000.0, None, None, usage)
            for i, usage in enumerate(USAGES)
        ],
    )

    step_densification(conn, DEPT)

    obtenu = {
        usage: float(ces)
        for usage, ces in conn.execute(
            "SELECT type_usage, ces_potentiel FROM densification_scores"
        ).fetchall()
    }
    assert obtenu == {
        "Résidentiel collectif": 0.60,
        "Résidentiel individuel": 0.40,
        "Tertiaire & Autres": 0.60,
        "Dépendance": 0.25,
        "Secondaire": 0.35,
    }


@requires_spatial
def test_usage_inconnu_prend_le_defaut(base):
    """Un usage absent du bareme, ou nul, vaut 0,40."""
    conn = base(
        parcelles=[("35238000AB0001", 100), ("35238000AB0002", 100)],
        bdnb=[
            ("35238000AB0001", 1000.0, None, None, "Usage inexistant"),
            ("35238000AB0002", 1000.0, None, None, None),
        ],
    )

    step_densification(conn, DEPT)

    assert [float(ligne[2]) for ligne in scores(conn)] == [0.40, 0.40]


# --- Le reste du bareme, qui ne doit pas bouger -----------------------------


@requires_spatial
def test_ces_actuel_est_le_rapport_emprise_sur_surface(base):
    """2 500 m2 batis sur 10 000 m2 de parcelle font un CES de 0,25."""
    conn = base(
        parcelles=[("35238000AB0001", 100)],
        bdnb=[("35238000AB0001", 2500.0, None, None, "Secondaire")],
    )

    step_densification(conn, DEPT)

    assert float(scores(conn)[0][1]) == 0.25


@requires_spatial
def test_ces_actuel_plafonne_a_1(base):
    """Une emprise plus grande que sa parcelle ne depasse pas 1,0."""
    conn = base(
        parcelles=[("35238000AB0001", 100)],
        bdnb=[("35238000AB0001", 50000.0, None, None, "Secondaire")],
    )

    step_densification(conn, DEPT)

    assert float(scores(conn)[0][1]) == 1.0


@requires_spatial
def test_surface_plancher_prefere_le_nombre_de_niveaux(base):
    """nb_niveau l'emporte sur la hauteur ; sinon hauteur / 3, au moins 1."""
    conn = base(
        parcelles=[(f"35238000AB000{i}", 100) for i in (1, 2, 3, 4)],
        bdnb=[
            ("35238000AB0001", 1000.0, 30.0, 3, "Secondaire"),     # 3 niveaux
            ("35238000AB0002", 1000.0, 9.0, None, "Secondaire"),   # 9 / 3 = 3
            ("35238000AB0003", 1000.0, 1.0, None, "Secondaire"),   # arrondi a 0 -> 1
            ("35238000AB0004", 1000.0, None, None, "Secondaire"),  # emprise seule
        ],
    )

    step_densification(conn, DEPT)

    planchers = [
        float(p)
        for (p,) in conn.execute(
            "SELECT surface_plancher_m2 FROM densification_scores ORDER BY id_parcelle"
        ).fetchall()
    ]
    assert planchers == [3000.0, 3000.0, 1000.0, 1000.0]


@requires_spatial
def test_source_ces_distingue_emprise_usage_et_inconnu(base):
    """La source du CES sert au score de confiance : trois cas, trois valeurs."""
    conn = base(
        parcelles=[(f"35238000AB000{i}", 100) for i in (1, 2, 3)],
        bdnb=[
            ("35238000AB0001", 1000.0, None, None, "Secondaire"),  # emprise
            ("35238000AB0002", None, None, None, "Secondaire"),    # usage seul
            ("35238000AB0003", None, None, None, None),            # rien
        ],
    )

    step_densification(conn, DEPT)

    sources = [
        s
        for (s,) in conn.execute(
            "SELECT source_ces FROM densification_scores ORDER BY id_parcelle"
        ).fetchall()
    ]
    assert sources == ["bdnb_emprise", "bdnb_usage_only", "inconnu"]


@requires_spatial
def test_potentiel_de_moitie_quand_seul_l_usage_est_connu(base):
    """Sans emprise, le potentiel est arbitrairement la moitie du CES potentiel.

    C'est la seule branche ou `potentiel_densification` ne se deduit pas d'un
    CES actuel mesure. Le facteur 0,5 est une convention du bareme, pas un
    calcul : ce test le fige pour qu'il ne derive pas en silence.
    """
    conn = base(
        parcelles=[("35238000AB0001", 100)],
        bdnb=[("35238000AB0001", None, None, None, "Secondaire")],
    )

    step_densification(conn, DEPT)

    potentiel, categorie = conn.execute(
        "SELECT potentiel_densification, categorie FROM densification_scores"
    ).fetchone()
    assert float(potentiel) == pytest.approx(0.175)  # 0,35 x 0,5
    assert categorie == "MOYEN"


@requires_spatial
def test_parcelle_d_un_metre_carre_ecartee(base):
    """Le bareme exige plus d'1 m2 : un CES sur une parcelle-residu n'a pas de sens."""
    conn = base(
        parcelles=[("35238000AB0001", 1), ("35238000AB0002", 2)],
        bdnb=[
            ("35238000AB0001", 1.0, None, None, "Secondaire"),
            ("35238000AB0002", 1.0, None, None, "Secondaire"),
        ],
    )

    step_densification(conn, DEPT)

    assert [ligne[0] for ligne in scores(conn)] == ["35238000AB0002"]


@requires_spatial
def test_categories_aux_seuils(base):
    """FORT a 0,25, MOYEN a 0,10, FAIBLE au-dessus de 0,02, SATURE en dessous.

    Le potentiel vaut `ces_potentiel - ces_actuel`, ici 0,40 moins le CES
    obtenu en posant l'emprise voulue sur 10 000 m2.

    Le seuil FAIBLE est un `>` strict, mais aucun cas ne le prouve : un
    potentiel valant exactement 0,02 n'est pas constructible ici, la
    soustraction en flottant tombant a 0,020000000000000018. Passer ce `>` en
    `>=` resterait donc invisible — limite connue de ce filet.
    """
    conn = base(
        parcelles=[(f"35238000AB000{i}", 100) for i in (1, 2, 3, 4, 5, 6, 7)],
        bdnb=[
            ("35238000AB0001", 1000.0, None, None, "Résidentiel individuel"),  # 0,30
            ("35238000AB0002", 2500.0, None, None, "Résidentiel individuel"),  # 0,15
            ("35238000AB0003", 3700.0, None, None, "Résidentiel individuel"),  # 0,03
            ("35238000AB0004", 4000.0, None, None, "Résidentiel individuel"),  # 0,00
            # 0,22 : entre les deux seuils. Sans ce cas, abaisser le seuil FORT
            # de 0,25 a 0,20 ne se verrait pas, 0,30 restant FORT de part et
            # d'autre.
            ("35238000AB0005", 1800.0, None, None, "Résidentiel individuel"),  # 0,22
            # 0,07 : de meme entre MOYEN et FAIBLE, sans quoi abaisser le seuil
            # MOYEN de 0,10 a 0,05 ne se verrait pas non plus.
            ("35238000AB0006", 3300.0, None, None, "Résidentiel individuel"),  # 0,07
            # 0,01 : juste sous le seuil FAIBLE, qui est un `>` strict a 0,02.
            ("35238000AB0007", 3900.0, None, None, "Résidentiel individuel"),  # 0,01
        ],
    )

    step_densification(conn, DEPT)

    assert [ligne[3] for ligne in scores(conn)] == [
        "FORT", "MOYEN", "FAIBLE", "SATURE", "MOYEN", "FAIBLE", "SATURE",
    ]


@requires_spatial
def test_sans_bdnb_tout_est_inconnu(base):
    """Sans la table `bdnb_stats`, l'etape tourne et ne conclut rien."""
    conn = base(parcelles=[("35238000AB0001", 100)], bdnb=None)

    step_densification(conn, DEPT)

    id_parcelle, ces_actuel, _, categorie = scores(conn)[0]
    assert id_parcelle == "35238000AB0001"
    assert ces_actuel is None
    assert categorie == "INCONNU"


@requires_spatial
def test_autre_departement_ecarte(base):
    """Le filtre porte sur le prefixe de `code_commune`."""
    conn = base(
        parcelles=[("35238000AB0001", 100), ("44109000AB0001", 100)],
        bdnb=[
            ("35238000AB0001", 1000.0, None, None, "Secondaire"),
            ("44109000AB0001", 1000.0, None, None, "Secondaire"),
        ],
    )

    step_densification(conn, DEPT)

    assert [ligne[0] for ligne in scores(conn)] == ["35238000AB0001"]


# --- L'entree en ligne de commande ------------------------------------------
#
# Elle remplace `data-pipeline/etl_densification.py`, qui chargeait la BDNB
# lui-meme avant de calculer. `step_densification` exige la table `bdnb_stats`,
# que le pipeline complet cree a l'etape golden join : rejouer la seule
# densification sur une base qui ne l'a pas rendrait des INCONNU. D'ou
# `charger_bdnb`.


def ecrire_parquet_bdnb(chemin, lignes):
    """Ecrit un Parquet a la forme de `data/bdnb_stats.parquet`."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE tmp (
            parcelle_id VARCHAR, emprise_sol_m2 DOUBLE,
            hauteur_moyenne DOUBLE, nb_niveau INTEGER, type_usage VARCHAR
        )
    """)
    for ligne in lignes:
        conn.execute("INSERT INTO tmp VALUES (?, ?, ?, ?, ?)", list(ligne))
    conn.execute(f"COPY tmp TO '{chemin.as_posix()}' (FORMAT PARQUET)")
    conn.close()


@requires_spatial
def test_charger_bdnb_cree_la_table_depuis_le_parquet(tmp_path, base):
    """Le filtre est le prefixe de departement, comme a l'etape golden join."""
    parquet = tmp_path / "bdnb_stats.parquet"
    ecrire_parquet_bdnb(parquet, [
        ("35238000AB0001", 1000.0, None, None, "Secondaire"),
        ("44109000AB0001", 1000.0, None, None, "Secondaire"),
    ])
    conn = base(parcelles=[("35238000AB0001", 100)], bdnb=None)

    assert charger_bdnb(conn, DEPT, parquet) is True
    assert [i for (i,) in conn.execute(
        "SELECT parcelle_id FROM bdnb_stats"
    ).fetchall()] == ["35238000AB0001"]


@requires_spatial
def test_charger_bdnb_respecte_une_table_deja_presente(tmp_path, base):
    """Le pipeline complet l'a deja creee : ne pas la refaire."""
    parquet = tmp_path / "bdnb_stats.parquet"
    ecrire_parquet_bdnb(parquet, [("35238000AB0999", 1.0, None, None, "Secondaire")])
    conn = base(
        parcelles=[("35238000AB0001", 100)],
        bdnb=[("35238000AB0001", 1000.0, None, None, "Secondaire")],
    )

    assert charger_bdnb(conn, DEPT, parquet) is True
    assert [i for (i,) in conn.execute(
        "SELECT parcelle_id FROM bdnb_stats"
    ).fetchall()] == ["35238000AB0001"]


@requires_spatial
def test_charger_bdnb_sans_parquet_le_dit_et_continue(tmp_path, base):
    """Sans Parquet, l'etape doit tourner quand meme — en INCONNU."""
    conn = base(parcelles=[("35238000AB0001", 100)], bdnb=None)

    assert charger_bdnb(conn, DEPT, tmp_path / "absent.parquet") is False

    step_densification(conn, DEPT)
    assert scores(conn)[0][3] == "INCONNU"


@requires_spatial
def test_main_rejoue_l_etape_sur_une_base_existante(tmp_path):
    """Le cas nominal : une base construite, la densification refaite."""
    chemin = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("""
        CREATE TABLE parcelles (
            id_parcelle VARCHAR, code_commune VARCHAR,
            section VARCHAR, numero VARCHAR, geometry GEOMETRY
        )
    """)
    conn.execute(
        "INSERT INTO parcelles VALUES (?, ?, 'AB', '0001', ST_GeomFromText(?))",
        ["35238000AB0001", "35238", carre(100)],
    )
    conn.execute("""
        CREATE TABLE bdnb_stats (
            parcelle_id VARCHAR, emprise_sol_m2 DOUBLE,
            hauteur_moyenne DOUBLE, nb_niveau INTEGER, type_usage VARCHAR
        )
    """)
    conn.execute(
        "INSERT INTO bdnb_stats VALUES (?, ?, ?, ?, ?)",
        ["35238000AB0001", 1000.0, None, None, "Résidentiel collectif"],
    )
    conn.close()

    assert main([DEPT, "--db", str(chemin)]) == 0

    relu = duckdb.connect(str(chemin), read_only=True)
    ces_potentiel, categorie = relu.execute(
        "SELECT ces_potentiel, categorie FROM densification_scores"
    ).fetchone()
    relu.close()
    assert float(ces_potentiel) == 0.60
    assert categorie == "FORT"


def test_main_sur_une_base_absente_echoue_proprement(tmp_path, capsys):
    """Pas de trace d'exception : un message et un code de retour."""
    code = main([DEPT, "--db", str(tmp_path / "nulle-part.duckdb")])

    assert code == 1
    assert "introuvable" in capsys.readouterr().out


@requires_spatial
def test_main_charge_la_bdnb_quand_la_base_ne_l_a_pas(tmp_path):
    """C'est ce que faisait la variante autonome : lire le Parquet elle-meme.

    Sans ce chargement, rejouer la densification seule sur une base construite
    sans golden join rendrait des categories INCONNU en silence.
    """
    # Parcelle volontairement absente de la vraie BDNB du depot : si le CLI
    # ignorait `--bdnb` pour retomber sur son chemin par defaut, le Parquet
    # reel ne la porterait pas et la categorie sortirait INCONNU.
    parcelle = "35999000ZZ9999"

    chemin = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("""
        CREATE TABLE parcelles (
            id_parcelle VARCHAR, code_commune VARCHAR,
            section VARCHAR, numero VARCHAR, geometry GEOMETRY
        )
    """)
    conn.execute(
        "INSERT INTO parcelles VALUES (?, ?, 'ZZ', '9999', ST_GeomFromText(?))",
        [parcelle, "35999", carre(100)],
    )
    conn.close()

    parquet = tmp_path / "bdnb_stats.parquet"
    ecrire_parquet_bdnb(parquet, [
        (parcelle, 1000.0, None, None, "Résidentiel collectif"),
    ])

    assert main([DEPT, "--db", str(chemin), "--bdnb", str(parquet)]) == 0

    relu = duckdb.connect(str(chemin), read_only=True)
    categorie = relu.execute("SELECT categorie FROM densification_scores").fetchone()[0]
    relu.close()
    assert categorie == "FORT"
