"""Tests des lectures de transactions du depot departemental.

`DuckDBTransactionsMixin` porte quatre methodes et 218 lignes, sans test
direct. La plus dense, `get_transactions_for_parcel`, enchaine trois requetes
en cascade : `list_contains` sur `mutations_aggregated`, un repli `UNNEST` si
la premiere echoue, puis `france_foncier_test` si rien n'est trouve. Trois
chemins qui doivent rendre le meme type d'objet — et qui ne lisent pas les
memes colonnes.
"""

from datetime import date
from decimal import Decimal

import duckdb
import pytest

from app.repositories.duckdb_repository import DuckDBLandRepository

COMMUNE = "35238"
PARCELLE = "35238000AB0297"
AUTRE = "35238000AB0298"


def _table_mutations(conn):
    conn.execute("""
        CREATE TABLE mutations_aggregated (
            id_mutation VARCHAR, date_mutation DATE, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR, parcelles VARCHAR[],
            surface_habitable_totale DOUBLE, nombre_locaux INTEGER,
            prix_m2 DOUBLE, longitude DOUBLE, latitude DOUBLE
        )
    """)
    conn.execute(f"""
        INSERT INTO mutations_aggregated VALUES
        ('MUT001', '2022-03-10', 'Vente', 150000, '{COMMUNE}', ['{PARCELLE}'],
         80, 1, 1875, -1.6778, 48.1173),
        ('MUT002', '2024-01-15', 'Vente', 200000, '{COMMUNE}', ['{PARCELLE}', '{AUTRE}'],
         50, 2, 4000, -1.6800, 48.1200),
        ('MUT003', '2023-06-20', 'Vente', 90000, '{COMMUNE}', ['{AUTRE}'],
         30, 1, 3000, -1.6790, 48.1180)
    """)


@pytest.fixture
def depot_mutations(tmp_path):
    chemin = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(chemin))
    _table_mutations(conn)
    conn.close()
    depot = DuckDBLandRepository(chemin)
    yield depot
    depot.close()


@pytest.fixture
def depot_enrichi(tmp_path):
    """Base sans `mutations_aggregated` : seul le repli enrichi peut repondre."""
    chemin = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(chemin))
    conn.execute("""
        CREATE TABLE france_foncier_test (
            id_mutation VARCHAR, date_mutation DATE, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR,
            cadastre_parcelle_id VARCHAR, surface_habitable_totale DOUBLE,
            nombre_locaux INTEGER, prix_m2 DOUBLE, longitude DOUBLE,
            latitude DOUBLE, is_outlier BOOLEAN, type_local VARCHAR
        )
    """)
    conn.execute(f"""
        INSERT INTO france_foncier_test VALUES
        ('MUT010', '2024-02-01', 'Vente', 300000, '{COMMUNE}', '{PARCELLE}',
         100, 1, 3000, -1.6778, 48.1173, FALSE, 'Maison'),
        ('MUT011', '2021-05-05', 'Vente', 900000, '{COMMUNE}', '{PARCELLE}',
         10, 1, 90000, -1.6778, 48.1173, TRUE, 'Appartement')
    """)
    conn.close()
    depot = DuckDBLandRepository(chemin)
    yield depot
    depot.close()


# --- get_transactions_for_parcel : voie principale -------------------------


async def test_mutations_de_la_parcelle_les_plus_recentes_d_abord(depot_mutations):
    mutations = await depot_mutations.get_transactions_for_parcel(PARCELLE)

    assert [m.id_mutation for m in mutations] == ["MUT002", "MUT001"]
    assert mutations[1].date_mutation == date(2022, 3, 10)
    assert mutations[1].valeur_fonciere == Decimal("150000")


async def test_une_mutation_portant_plusieurs_parcelles_ressort_pour_chacune(depot_mutations):
    """MUT002 couvre deux parcelles : elle doit apparaitre des deux cotes."""
    pour_l_une = await depot_mutations.get_transactions_for_parcel(PARCELLE)
    pour_l_autre = await depot_mutations.get_transactions_for_parcel(AUTRE)

    assert "MUT002" in [m.id_mutation for m in pour_l_une]
    assert "MUT002" in [m.id_mutation for m in pour_l_autre]


async def test_coordonnees_reprises(depot_mutations):
    mutations = await depot_mutations.get_transactions_for_parcel(PARCELLE)
    recente = mutations[0]

    assert recente.longitude == pytest.approx(-1.6800)
    assert recente.latitude == pytest.approx(48.1200)


async def test_limite_appliquee(depot_mutations):
    mutations = await depot_mutations.get_transactions_for_parcel(PARCELLE, limit=1)

    assert [m.id_mutation for m in mutations] == ["MUT002"]


async def test_parcelle_sans_mutation(depot_mutations):
    assert await depot_mutations.get_transactions_for_parcel("35238000ZZ9999") == []


async def test_type_local_absent_sur_la_voie_principale(depot_mutations):
    """Comportement actuel epingle, non approuve.

    La requete sur `mutations_aggregated` selectionne douze colonnes, la
    derniere etant `NULL AS type_local`. Le mapping, lui, lit `r[11]` comme
    `is_outlier` et cherche `type_local` en `r[12]`, qui n'existe pas sur ce
    chemin. Les deux champs sortent donc a leur valeur par defaut — ce qui est
    juste par accident, la colonne etant toujours nulle.

    Le test fige la conduite pour que la refonte ne la change pas sans
    decision ; renumeroter ces colonnes est un correctif a part.
    """
    mutations = await depot_mutations.get_transactions_for_parcel(PARCELLE)

    assert all(m.type_local is None for m in mutations)
    assert all(m.is_outlier is False for m in mutations)


# --- get_transactions_for_parcel : repli enrichi ---------------------------


async def test_repli_sur_la_table_enrichie(depot_enrichi):
    mutations = await depot_enrichi.get_transactions_for_parcel(PARCELLE)

    assert [m.id_mutation for m in mutations] == ["MUT010", "MUT011"]


async def test_le_repli_enrichi_lit_type_local_et_is_outlier(depot_enrichi):
    """Ce chemin-la selectionne treize colonnes : les deux champs sont servis."""
    par_id = {m.id_mutation: m for m in await depot_enrichi.get_transactions_for_parcel(PARCELLE)}

    assert par_id["MUT010"].type_local == "Maison"
    assert par_id["MUT010"].is_outlier is False
    assert par_id["MUT011"].is_outlier is True


async def test_repli_enrichi_enveloppe_la_parcelle_dans_une_liste(depot_enrichi):
    mutations = await depot_enrichi.get_transactions_for_parcel(PARCELLE)

    assert mutations[0].parcelles == [PARCELLE]


# --- les trois autres lectures ---------------------------------------------


async def test_mutations_par_commune(depot_mutations):
    mutations = await depot_mutations.get_mutations_by_commune(COMMUNE)

    assert {m.id_mutation for m in mutations} == {"MUT001", "MUT002", "MUT003"}


async def test_transactions_par_commune_deplie_une_ligne_par_parcelle(depot_mutations):
    """Cette lecture ne touche pas la table `transactions`.

    Elle derive de `mutations_aggregated` en depliant `parcelles` : une
    mutation portant deux parcelles produit deux transactions, une par
    parcelle, avec la meme valeur fonciere. MUT002 en couvre deux, d'ou quatre
    lignes pour trois mutations.
    """
    transactions = await depot_mutations.get_transactions_by_commune(COMMUNE)

    assert len(transactions) == 4
    mut002 = [t for t in transactions if t.id_mutation == "MUT002"]
    assert {t.id_parcelle for t in mut002} == {PARCELLE, AUTRE}
    assert all(t.valeur_fonciere == Decimal("200000") for t in mut002)


async def test_transactions_par_commune_filtre_les_dates(depot_mutations):
    transactions = await depot_mutations.get_transactions_by_commune(
        COMMUNE, date_from=date(2023, 1, 1), date_to=date(2023, 12, 31)
    )

    assert [t.id_mutation for t in transactions] == ["MUT003"]
