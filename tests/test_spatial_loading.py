"""Tests du chargement de l'extension spatiale DuckDB.

Deux comportements verrouillés ici :

1. `ensure_spatial` ne doit tenter le chargement qu'une fois par connexion,
   même sous accès concurrent. FastAPI sert les endpoints synchrones depuis un
   pool de threads qui partagent la connexion : deux requêtes simultanées
   lançaient chacune `INSTALL spatial`, l'une des deux échouait, et la carte
   renvoyait une erreur à son premier chargement avant de fonctionner. Un
   défaut intermittent, invisible en test séquentiel.

2. `SpatialUnavailableError` et `DataUnavailableError` dérivent d'une base
   commune, pour que les endpoints puissent les ré-émettre avant leur
   `except Exception` générique et obtenir un 503 au lieu d'un 500.
"""

import threading
from unittest.mock import MagicMock

from app.infrastructure import duckdb_spatial
from app.infrastructure.data_availability import DataUnavailableError
from app.infrastructure.duckdb_spatial import (
    SpatialUnavailableError,
    ensure_spatial,
    require_spatial,
)
from app.infrastructure.unavailable import ResourceUnavailableError


class _CountingConn:
    """Connexion factice qui compte les INSTALL et sait échouer en parallèle."""

    def __init__(self, fail: bool = False, strict_serial: bool = False):
        self.installs = 0
        self._fail = fail
        self._strict_serial = strict_serial
        self._busy = False
        self._lock = threading.Lock()

    def execute(self, sql, params=None):
        if "INSTALL" in sql.upper():
            with self._lock:
                if self._strict_serial and self._busy:
                    raise RuntimeError("INSTALL concurrent — DuckDB refuse")
                self._busy = True
                self.installs += 1
            # fenêtre pendant laquelle un autre thread pourrait entrer
            threading.Event().wait(0.01)
            with self._lock:
                self._busy = False
            if self._fail:
                raise RuntimeError("extension bloquee")
        return MagicMock()


class TestEnsureSpatial:
    def setup_method(self):
        duckdb_spatial.reset_cache()

    def teardown_method(self):
        duckdb_spatial.reset_cache()

    def test_charge_une_seule_fois_par_connexion(self):
        conn = _CountingConn()
        assert ensure_spatial(conn) is True
        assert ensure_spatial(conn) is True
        assert ensure_spatial(conn) is True
        assert conn.installs == 1, "INSTALL rejoue a chaque appel"

    def test_pas_de_course_entre_threads(self):
        """Huit threads simultanés ne doivent produire qu'un seul INSTALL."""
        conn = _CountingConn(strict_serial=True)
        results, errors = [], []

        def worker():
            try:
                results.append(ensure_spatial(conn))
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        assert conn.installs == 1, f"{conn.installs} INSTALL concurrents"
        assert all(results), "tous les appels doivent voir l'extension chargee"

    def test_echec_memorise_sans_relancer(self):
        conn = _CountingConn(fail=True)
        assert ensure_spatial(conn) is False
        assert ensure_spatial(conn) is False
        assert conn.installs == 1

    def test_require_spatial_leve_si_indisponible(self):
        conn = _CountingConn(fail=True)
        try:
            require_spatial(conn)
        except SpatialUnavailableError:
            pass
        else:  # pragma: no cover
            raise AssertionError("SpatialUnavailableError attendue")

    def test_require_spatial_passe_si_disponible(self):
        require_spatial(_CountingConn())


class TestHierarchieDesExceptions:
    """Les endpoints ré-émettent la base commune avant leur except générique."""

    def test_spatial_derive_de_la_base_commune(self):
        assert issubclass(SpatialUnavailableError, ResourceUnavailableError)

    def test_data_derive_de_la_base_commune(self):
        assert issubclass(DataUnavailableError, ResourceUnavailableError)

    def test_un_except_generique_les_laisserait_passer(self):
        """Sans la garde, `except Exception` les avalerait en 500."""
        for exc in (SpatialUnavailableError("x"), DataUnavailableError("d", "t")):
            assert isinstance(exc, Exception)
            assert isinstance(exc, ResourceUnavailableError)
