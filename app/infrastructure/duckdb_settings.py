"""Ouverture en lecture seule des bases DuckDB, bornee en ressources.

Le backend partage son serveur avec une vingtaine d'autres sites. Par defaut,
DuckDB s'autorise 80 % de la memoire du conteneur et un fil par coeur, et ce
pour chaque processus : avec deux workers uvicorn, rien ne tenait l'ensemble
sous la limite de 4 Go du conteneur.

Les bornes viennent de l'environnement (docker-compose.prod.yml). Absentes,
DuckDB garde ses valeurs par defaut, ce qui convient en developpement.

Elles sont posees par SET apres l'ouverture, et non par `config=` : DuckDB
partage une instance par fichier au sein d'un processus, et refuse d'y ouvrir
une connexion avec une configuration differente. Ces reglages sont globaux a
l'instance : les reposer a chaque ouverture est sans effet de bord.
"""

import os
from pathlib import Path

import duckdb

# Variable d'environnement -> reglage DuckDB.
#
# `temp_directory` compte : sous `memory_limit`, DuckDB deborde sur disque, et
# son dossier par defaut est voisin de la base, montee en lecture seule.
# `max_temp_directory_size` borne ce debordement, le disque etant partage.
REGLAGES = {
    "DUCKDB_MEMORY_LIMIT": "memory_limit",
    "DUCKDB_THREADS": "threads",
    "DUCKDB_TEMP_DIRECTORY": "temp_directory",
    "DUCKDB_MAX_TEMP_DIRECTORY_SIZE": "max_temp_directory_size",
}


def connect_read_only(path: Path | str) -> duckdb.DuckDBPyConnection:
    """Connexion en lecture seule, avec les bornes de l'environnement."""
    conn = duckdb.connect(str(path), read_only=True)
    for variable, reglage in REGLAGES.items():
        valeur = os.environ.get(variable, "").strip()
        if valeur:
            # SET n'accepte pas de parametre lie ; la valeur vient de la
            # configuration de deploiement, mais on la cite quand meme.
            conn.execute(f"SET {reglage} = '{valeur.replace(chr(39), chr(39) * 2)}'")
    return conn
