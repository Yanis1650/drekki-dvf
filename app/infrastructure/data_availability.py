"""Détection des jeux de données absents de la base.

Le pipeline ETL est modulaire : selon les étapes réellement exécutées pour un
département, certaines tables peuvent ne jamais avoir été créées (`dfi_filiations`
si l'ETL DFI n'a pas tourné, `points_interet` si l'enrichissement OSM n'a pas
tourné, etc.).

Jusqu'ici ces absences étaient rattrapées par un `except Exception: return []`,
ce qui transformait « je n'ai pas la donnée » en « il n'y a pas de donnée » —
et l'API affirmait par exemple « Parcelle originelle (pas de division connue) »
pour *toutes* les parcelles d'un département dont la filiation n'avait jamais
été chargée.

Ce module permet de distinguer les deux cas et de le dire explicitement au
client.
"""

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[tuple[int, str], bool] = {}


class DataUnavailableError(RuntimeError):
    """Un jeu de données requis n'a pas été chargé dans cette base.

    À distinguer d'un résultat vide : ici la question n'a pas de réponse,
    elle n'a simplement pas pu être posée.
    """

    def __init__(self, dataset: str, table: str, hint: str = "") -> None:
        self.dataset = dataset
        self.table = table
        self.hint = hint
        message = f"Jeu de données « {dataset} » indisponible (table `{table}` absente)."
        if hint:
            message = f"{message} {hint}"
        super().__init__(message)


def table_exists(conn: Any, table: str) -> bool:
    """Indique si une table existe sur cette connexion (résultat mémorisé).

    La connexion étant ouverte en lecture seule et le schéma figé pour sa durée
    de vie, le cache par (connexion, table) est sûr.
    """
    key = (id(conn), table)
    with _lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    try:
        row = conn.execute(
            "SELECT 1 FROM duckdb_tables() WHERE table_name = ? LIMIT 1", [table]
        ).fetchone()
        exists = row is not None
    except Exception as exc:  # connexion inutilisable : on ne cache pas
        logger.warning("Vérification d'existence de `%s` impossible : %s", table, exc)
        return False

    with _lock:
        _cache[key] = exists
    if not exists:
        logger.info("Table `%s` absente de la base — jeu de données non chargé.", table)
    return exists


def require_table(conn: Any, table: str, dataset: str, hint: str = "") -> None:
    """Vérifie la présence d'une table, ou lève `DataUnavailableError`.

    Args:
        conn: connexion DuckDB.
        table: nom physique de la table attendue.
        dataset: nom métier du jeu de données, destiné à l'utilisateur final.
        hint: commande ETL à lancer pour y remédier.
    """
    if not table_exists(conn, table):
        raise DataUnavailableError(dataset, table, hint)


def reset_cache() -> None:
    """Vide le cache (tests uniquement)."""
    with _lock:
        _cache.clear()
