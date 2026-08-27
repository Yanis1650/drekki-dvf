"""Chargement tolérant de l'extension spatiale DuckDB.

L'extension `spatial` est un binaire téléchargé puis chargé dynamiquement.
Elle peut être indisponible pour des raisons qui n'ont rien à voir avec le code :
pas de réseau au premier lancement, ou stratégie de contrôle d'application
(Smart App Control / WDAC sous Windows) qui bloque le chargement du .dll.

Auparavant chaque `_get_connection()` exécutait `INSTALL spatial; LOAD spatial;`
et laissait remonter l'IOException. Résultat : toutes les requêtes échouaient en
500, y compris celles purement tabulaires (tendances de marché, fiche parcelle)
qui n'ont aucun besoin de géométrie.

Ce module sépare les deux cas :
  - `ensure_spatial(conn)` tente le chargement une seule fois par connexion et
    renvoie un booléen — l'appelant continue même en cas d'échec ;
  - `require_spatial(conn)` lève `SpatialUnavailableError` pour les requêtes qui
    utilisent réellement ST_*, ce qui permet à l'API de répondre 503 avec un
    message explicite plutôt qu'un 500 opaque.
"""

import logging
import threading

import duckdb

from app.infrastructure.unavailable import ResourceUnavailableError

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_checked: set[int] = set()
_loaded: dict[int, bool] = {}
_warned = False


class SpatialUnavailableError(ResourceUnavailableError):
    """L'extension spatiale DuckDB n'a pas pu être chargée."""


def ensure_spatial(conn: duckdb.DuckDBPyConnection) -> bool:
    """Charge l'extension spatiale si possible. Ne lève jamais.

    Le résultat est mémorisé par connexion : on ne retente pas un INSTALL à
    chaque requête, ce qui évitait déjà un aller-retour disque inutile.

    Returns:
        True si les fonctions ST_* sont utilisables sur cette connexion.
    """
    global _warned
    key = id(conn)

    # Le verrou couvre toute la tentative, pas seulement la mise en cache.
    # FastAPI sert les endpoints synchrones depuis un pool de threads qui
    # partagent la connexion : deux requêtes simultanées lançaient chacune
    # `INSTALL spatial`, et l'une des deux échouait. La carte renvoyait alors
    # une erreur au premier chargement, puis fonctionnait — un défaut
    # intermittent, invisible en test séquentiel.
    with _lock:
        if key in _checked:
            return _loaded.get(key, False)

        try:
            conn.execute("INSTALL spatial;")
            conn.execute("LOAD spatial;")
            loaded = True
        except Exception as exc:
            loaded = False
            if not _warned:
                _warned = True
                logger.warning(
                    "Extension spatiale DuckDB indisponible : %s\n"
                    "Les requêtes géométriques (carte, recherche par rayon, "
                    "fallback spatial) renverront 503. Les requêtes tabulaires "
                    "restent opérationnelles. Voir docs/DEPLOYMENT.md "
                    "(section « Extension spatiale »).",
                    exc,
                )

        _checked.add(key)
        _loaded[key] = loaded

    return loaded


def require_spatial(conn: duckdb.DuckDBPyConnection) -> None:
    """Garantit que l'extension spatiale est disponible, ou lève.

    À appeler en tête des méthodes de repository qui utilisent ST_*.

    Raises:
        SpatialUnavailableError: si l'extension n'a pas pu être chargée.
    """
    if not ensure_spatial(conn):
        raise SpatialUnavailableError(
            "L'extension spatiale DuckDB n'est pas disponible sur ce serveur. "
            "Les fonctionnalités géographiques sont désactivées."
        )


def reset_cache() -> None:
    """Vide le cache de détection (tests uniquement)."""
    global _warned
    with _lock:
        _checked.clear()
        _loaded.clear()
        _warned = False
