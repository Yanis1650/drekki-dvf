"""Tests de l'ETL DFI — le filet manquant avant refonte.

467 lignes sans un seul test, alors que ce pipeline produit `dfi_filiations`,
la table dont depend tout l'arbre de filiation servi par l'API.

Le format DFI est un texte a champs separes par des points-virgules, ou les
lignes vont par paires : une ligne de type 1 porte les parcelles meres, la
suivante de type 2 porte les filles, et l'ETL en fait le produit cartesien.
C'est cet appariement qui merite un filet : il est positionnel, donc silencieux
quand il derape.
"""

from datetime import date

import duckdb
import pytest

from etl_dfi import DFIEtlPipeline

# dept;commune;prefixe;id_dfi;nature;date;geometre;placeholder;lot;type;parcelles...
GEOMETRE = "CABINET X"


def _ligne(id_dfi: str, type_ligne: str, parcelles: list[str], lot: str = "L0001") -> str:
    champs = ["035", "001", "000", id_dfi, "1", "20210301", GEOMETRE, "XNUMX", lot, type_ligne]
    return ";".join(champs + parcelles)


@pytest.fixture
def pipeline(tmp_path):
    return DFIEtlPipeline(output_path=tmp_path / "dfi.duckdb")


# --- parse_dfi_line --------------------------------------------------------


def test_ligne_valide_donne_tous_les_champs(pipeline):
    parsed = pipeline.parse_dfi_line(_ligne("D000001", "1", ["AC0001", "AC0002"]))

    assert parsed["code_departement"] == "035"
    assert parsed["code_commune"] == "001"
    assert parsed["prefixe"] == "000"
    assert parsed["id_dfi"] == "D000001"
    assert parsed["nature_dfi"] == "1"
    assert parsed["date_validation"] == date(2021, 3, 1)
    assert parsed["numero_lot"] == "L0001"
    assert parsed["type_ligne"] == "1"
    assert parsed["parcelles"] == ["AC0001", "AC0002"]


@pytest.mark.parametrize("ligne", ["", "   ", "\n"])
def test_ligne_vide_ignoree(pipeline, ligne):
    assert pipeline.parse_dfi_line(ligne) is None


def test_ligne_trop_courte_ignoree(pipeline):
    """Moins de dix champs : le type de ligne n'est meme pas lisible."""
    assert pipeline.parse_dfi_line("035;001;000;D000001;1;20210301;X;XNUMX;L0001") is None


@pytest.mark.parametrize("mauvaise_date", ["2021030", "202103011", "", "notadate"])
def test_date_non_conforme_rejette_la_ligne(pipeline, mauvaise_date):
    ligne = _ligne("D000001", "1", ["AC0001"]).replace(";20210301;", f";{mauvaise_date};")
    assert pipeline.parse_dfi_line(ligne) is None


def test_cellules_de_parcelle_filtrees_par_longueur(pipeline):
    """Une cellule valide fait 2 a 6 caracteres : le reste est du remplissage.

    Le format reserve 175 cellules par ligne ; la immense majorite est vide.
    """
    parsed = pipeline.parse_dfi_line(
        _ligne("D000001", "1", ["AC0001", "", "A", "AC00012345", "  ", "A1200"])
    )
    assert parsed["parcelles"] == ["AC0001", "A1200"]


def test_champs_espaces_sont_rognes(pipeline):
    ligne = "  035 ; 001 ; 000 ; D000001 ; 1 ; 20210301 ;X;XNUMX; L0001 ; 1 ; AC0001 "
    parsed = pipeline.parse_dfi_line(ligne)

    assert parsed["code_departement"] == "035"
    assert parsed["id_dfi"] == "D000001"
    assert parsed["parcelles"] == ["AC0001"]


# --- process_dfi_file ------------------------------------------------------


def _fichier(tmp_path, lignes: list[str]):
    chemin = tmp_path / "dfi.txt"
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def test_paire_produit_le_cartesien_meres_x_filles(pipeline, tmp_path):
    chemin = _fichier(tmp_path, [
        _ligne("D000001", "1", ["AB0001", "AB0002"]),
        _ligne("D000001", "2", ["AC0010", "AC0011", "AC0012"]),
    ])

    filiations = pipeline.process_dfi_file(chemin)

    assert len(filiations) == 6
    assert {(f["parcelle_mere"], f["parcelle_fille"]) for f in filiations} == {
        (m, f) for m in ("AB0001", "AB0002") for f in ("AC0010", "AC0011", "AC0012")
    }


def test_ordre_inverse_des_types_reconnu(pipeline, tmp_path):
    """Type 2 puis type 1 : les meres restent celles de la ligne de type 1."""
    chemin = _fichier(tmp_path, [
        _ligne("D000001", "2", ["AC0010"]),
        _ligne("D000001", "1", ["AB0001"]),
    ])

    filiations = pipeline.process_dfi_file(chemin)

    assert len(filiations) == 1
    assert filiations[0]["parcelle_mere"] == "AB0001"
    assert filiations[0]["parcelle_fille"] == "AC0010"


def test_metadonnees_reprises_de_la_premiere_ligne(pipeline, tmp_path):
    chemin = _fichier(tmp_path, [
        _ligne("D000042", "1", ["AB0001"], lot="L0009"),
        _ligne("D000042", "2", ["AC0010"], lot="L0009"),
    ])

    f = pipeline.process_dfi_file(chemin)[0]

    assert f["id_dfi"] == "D000042"
    assert f["numero_lot"] == "L0009"
    assert f["code_commune"] == "001"
    assert f["date_validation"] == date(2021, 3, 1)


def test_paire_incoherente_ne_produit_rien(pipeline, tmp_path):
    """Deux lignes d'id_dfi differents ne forment pas une filiation."""
    chemin = _fichier(tmp_path, [
        _ligne("D000001", "1", ["AB0001"]),
        _ligne("D000002", "2", ["AC0010"]),
    ])

    assert pipeline.process_dfi_file(chemin) == []


def test_lot_different_ne_produit_rien(pipeline, tmp_path):
    chemin = _fichier(tmp_path, [
        _ligne("D000001", "1", ["AB0001"], lot="L0001"),
        _ligne("D000001", "2", ["AC0010"], lot="L0002"),
    ])

    assert pipeline.process_dfi_file(chemin) == []


@pytest.mark.parametrize("types", [("1", "1"), ("2", "2")])
def test_types_identiques_rejetes(pipeline, tmp_path, types):
    chemin = _fichier(tmp_path, [
        _ligne("D000001", types[0], ["AB0001"]),
        _ligne("D000001", types[1], ["AC0010"]),
    ])

    assert pipeline.process_dfi_file(chemin) == []


def test_lignes_vides_ne_desynchronisent_pas_l_appariement(pipeline, tmp_path):
    """Les blancs sont ignores avant l'appariement, pas comptes comme lignes."""
    chemin = _fichier(tmp_path, [
        _ligne("D000001", "1", ["AB0001"]),
        "",
        "   ",
        _ligne("D000001", "2", ["AC0010"]),
    ])

    filiations = pipeline.process_dfi_file(chemin)

    assert len(filiations) == 1
    assert filiations[0]["parcelle_mere"] == "AB0001"


def test_paires_successives_traitees_independamment(pipeline, tmp_path):
    chemin = _fichier(tmp_path, [
        _ligne("D000001", "1", ["AB0001"]),
        _ligne("D000001", "2", ["AC0010"]),
        _ligne("D000002", "1", ["AB0002"]),
        _ligne("D000002", "2", ["AC0020"]),
    ])

    filiations = pipeline.process_dfi_file(chemin)

    assert [(f["id_dfi"], f["parcelle_mere"], f["parcelle_fille"]) for f in filiations] == [
        ("D000001", "AB0001", "AC0010"),
        ("D000002", "AB0002", "AC0020"),
    ]


def test_une_ligne_orpheline_fait_perdre_la_paire_suivante(pipeline, tmp_path):
    """Comportement actuel epingle, non approuve.

    L'appariement est positionnel : les lignes sont prises deux par deux. Une
    ligne surnumeraire decale tout ce qui suit — ici la ligne orpheline est
    appariee avec la premiere ligne de la paire suivante, l'ensemble est
    rejete, et il ne reste rien. Le test fige la conduite existante pour que la
    refonte ne la change pas par accident ; la corriger — apparier sur
    (id_dfi, numero_lot) plutot que sur la position — est une decision a part.
    """
    chemin = _fichier(tmp_path, [
        _ligne("D000009", "1", ["AB9999"]),          # orpheline, sans type 2
        _ligne("D000001", "1", ["AB0001"]),
        _ligne("D000001", "2", ["AC0010"]),
    ])

    assert pipeline.process_dfi_file(chemin) == []


# --- load_to_duckdb --------------------------------------------------------


def _filiation(mere: str, fille: str) -> dict:
    return {
        "code_departement": "035", "code_commune": "001", "prefixe": "000",
        "id_dfi": "D000001", "nature_dfi": "1", "date_validation": date(2021, 3, 1),
        "numero_lot": "L0001", "parcelle_mere": mere, "parcelle_fille": fille,
    }


def test_chargement_cree_la_table_et_les_lignes(tmp_path):
    chemin = tmp_path / "dfi.duckdb"
    pipeline = DFIEtlPipeline(output_path=chemin)

    pipeline.load_to_duckdb([_filiation("AB0001", "AC0010"), _filiation("AB0002", "AC0011")])

    conn = duckdb.connect(str(chemin), read_only=True)
    try:
        lignes = conn.execute(
            "SELECT parcelle_mere, parcelle_fille FROM dfi_filiations ORDER BY 1"
        ).fetchall()
    finally:
        conn.close()
    assert lignes == [("AB0001", "AC0010"), ("AB0002", "AC0011")]


def test_chargement_cree_les_deux_index(tmp_path):
    """Les index composites portent les deux sens de lecture de la filiation."""
    chemin = tmp_path / "dfi.duckdb"
    DFIEtlPipeline(output_path=chemin).load_to_duckdb([_filiation("AB0001", "AC0010")])

    conn = duckdb.connect(str(chemin), read_only=True)
    try:
        index = {r[0] for r in conn.execute("SELECT index_name FROM duckdb_indexes()").fetchall()}
    finally:
        conn.close()
    assert {"idx_dfi_fille", "idx_dfi_mere"} <= index


def test_liste_vide_ne_cree_aucune_table(tmp_path):
    chemin = tmp_path / "vide.duckdb"
    pipeline = DFIEtlPipeline(output_path=chemin)

    pipeline.load_to_duckdb([])

    assert not chemin.exists()


def test_connexion_pretee_n_est_pas_fermee(tmp_path):
    """DuckDB refuse deux connexions au meme fichier : etl_build_dept prete la sienne."""
    conn = duckdb.connect(str(tmp_path / "partagee.duckdb"))
    pipeline = DFIEtlPipeline(output_path=tmp_path / "ignore.duckdb", conn=conn)

    pipeline.load_to_duckdb([_filiation("AB0001", "AC0010")])

    # Toujours utilisable : la connexion appartient a l'appelant.
    assert conn.execute("SELECT COUNT(*) FROM dfi_filiations").fetchone()[0] == 1
    conn.close()


def test_deux_chargements_s_ajoutent(tmp_path):
    """CREATE TABLE IF NOT EXISTS : un second passage complete, il ne remplace pas."""
    chemin = tmp_path / "dfi.duckdb"
    pipeline = DFIEtlPipeline(output_path=chemin)

    pipeline.load_to_duckdb([_filiation("AB0001", "AC0010")])
    pipeline.load_to_duckdb([_filiation("AB0002", "AC0011")])

    conn = duckdb.connect(str(chemin), read_only=True)
    try:
        total = conn.execute("SELECT COUNT(*) FROM dfi_filiations").fetchone()[0]
    finally:
        conn.close()
    assert total == 2


# --- run -------------------------------------------------------------------


def test_run_enchaine_extraction_et_chargement(tmp_path):
    source = _fichier(tmp_path, [
        _ligne("D000001", "1", ["AB0001", "AB0002"]),
        _ligne("D000001", "2", ["AC0010"]),
    ])
    base = tmp_path / "sortie.duckdb"

    total = DFIEtlPipeline(output_path=base).run(source)

    assert total == 2
    conn = duckdb.connect(str(base), read_only=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM dfi_filiations").fetchone()[0] == 2
    finally:
        conn.close()


def test_run_sur_fichier_absent_leve(tmp_path):
    with pytest.raises(FileNotFoundError):
        DFIEtlPipeline(output_path=tmp_path / "x.duckdb").run(tmp_path / "absent.txt")
