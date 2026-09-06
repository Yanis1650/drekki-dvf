"""Cycle de vie des ressources longues : connexions DuckDB et navigateur.

Trois comportements verrouilles ici, chacun correspondant a un defaut reel.

1. Les repositories et services sont construits a chaque requete HTTP. Les
   dependances FastAPI ne sont pas des generateurs : rien ne les referme.
   Chaque instance ouvrait donc sa propre connexion DuckDB. Elles partagent
   desormais un registre par fichier, comme le pool le fait par departement.

2. Le cache de l'extension spatiale etait indexe par `id(conn)` dans un dict
   jamais purge. CPython recyclant les `id()` apres collecte, une connexion
   neuve pouvait heriter du verdict d'une connexion morte. La cle est
   maintenant faible : elle disparait avec sa connexion.

3. `cleanup_browser` existait mais n'etait branchee sur aucun evenement
   d'arret : le Chromium de Playwright survivait a l'application.
"""

import gc
from pathlib import Path

import duckdb
import pytest

from app.infrastructure import duckdb_spatial
from app.infrastructure.duckdb_pool import (
    close_shared_connection,
    close_shared_connections,
    get_shared_connection,
)
from app.repositories.duckdb_base import DuckDBConnectionBase


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(path))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.close()
    yield path
    close_shared_connection(path)


class TestSharedConnections:
    def test_une_seule_connexion_par_fichier(self, db: Path):
        first = get_shared_connection(db)
        second = get_shared_connection(str(db))
        assert first is second, "deux connexions ouvertes pour le meme fichier"

    def test_deux_repositories_partagent_la_connexion(self, db: Path):
        """Le defaut d'origine : une connexion par requete HTTP."""
        one = DuckDBConnectionBase(db_path=db)
        two = DuckDBConnectionBase(db_path=db)
        assert one._get_connection() is two._get_connection()

    def test_le_pool_reste_prioritaire_quand_un_departement_est_donne(self, db: Path):
        """Le mode multi-departements ne passe pas par le registre partage."""
        class _Pool:
            def __init__(self):
                self.asked = []

            def get_connection(self, dept):
                self.asked.append(dept)
                return "connexion-du-pool"

        pool = _Pool()
        base = DuckDBConnectionBase(db_path=db, pool=pool)
        assert base._get_connection(dept="35") == "connexion-du-pool"
        assert pool.asked == ["35"]

    def test_close_relache_le_fichier_et_la_suivante_est_neuve(self, db: Path):
        first = get_shared_connection(db)
        close_shared_connection(db)
        with pytest.raises(duckdb.Error):
            first.execute("SELECT 1")
        assert get_shared_connection(db) is not first

    def test_close_all_ferme_tout(self, db: Path):
        conn = get_shared_connection(db)
        close_shared_connections()
        with pytest.raises(duckdb.Error):
            conn.execute("SELECT 1")


class TestSpatialCacheLifetime:
    def setup_method(self):
        duckdb_spatial.reset_cache()

    def teardown_method(self):
        duckdb_spatial.reset_cache()

    def test_le_verdict_ne_survit_pas_a_sa_connexion(self):
        """La cle faible est ce qui empeche un `id()` recycle de mentir."""
        class _Conn:
            def execute(self, sql, params=None):
                return None

        conn = _Conn()
        assert duckdb_spatial.ensure_spatial(conn) is True
        assert len(duckdb_spatial._loaded) == 1

        del conn
        gc.collect()
        assert len(duckdb_spatial._loaded) == 0, "verdict conserve apres la mort de la connexion"

    def test_deux_connexions_ont_chacune_leur_verdict(self):
        class _Conn:
            def __init__(self, fail):
                self._fail = fail

            def execute(self, sql, params=None):
                if self._fail and "INSTALL" in sql.upper():
                    raise RuntimeError("extension bloquee")
                return None

        ok, ko = _Conn(fail=False), _Conn(fail=True)
        assert duckdb_spatial.ensure_spatial(ok) is True
        assert duckdb_spatial.ensure_spatial(ko) is False
        assert duckdb_spatial.ensure_spatial(ok) is True


class TestApplicationShutdown:
    @pytest.mark.asyncio
    async def test_le_lifespan_ferme_navigateur_et_connexions(self, monkeypatch, db: Path):
        """`cleanup_browser` etait du code mort : ce test la rebranche."""
        from app import main

        called: list[str] = []

        async def fake_cleanup_browser():
            called.append("browser")

        monkeypatch.setattr(main, "cleanup_browser", fake_cleanup_browser)
        conn = get_shared_connection(db)

        async with main.lifespan(main.app):
            pass

        assert called == ["browser"], "le navigateur Playwright n'est pas ferme a l'arret"
        with pytest.raises(duckdb.Error):
            conn.execute("SELECT 1")
