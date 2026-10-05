"""Garde-fou sur la table de routage de l'API.

Les endpoints sont repartis entre plusieurs modules agreges par
`land.py`. Deplacer une route d'un module a l'autre sans mettre a jour cette
agregation la fait disparaitre sans erreur : l'application demarre, les tests
metier passent, et seule une requete reelle revele le 404.

Ces tests ne verifient pas ce que repondent les routes — c'est le role de
`test_api_endpoints.py` — mais qu'elles existent, sous le bon chemin et dans
le bon ordre.
"""

import pytest

from app.main import app


def _routes() -> list[str]:
    # Chemins de l'OpenAPI, dans l'ordre de declaration. `app.routes` ne
    # convient plus : depuis FastAPI 0.141, un routeur inclus y reste un seul
    # objet `_IncludedRouter`, sans les chemins qu'il porte, et ce test
    # echouait alors que les routes repondaient.
    return list(app.openapi()["paths"])


@pytest.mark.parametrize(
    "chemin",
    [
        "/api/v1/land/search",
        "/api/v1/land/search/enriched",
        "/api/v1/land/commune/{code_commune}",
        "/api/v1/land/commune/{code_commune}/stats",
    ],
)
def test_route_enregistree(chemin):
    assert chemin in _routes(), f"route absente de l'application : {chemin}"


def test_stats_declaree_avant_la_route_attrape_tout():
    """`/commune/{code}/stats` doit preceder `/commune/{code}`.

    Starlette retient la premiere route qui correspond. Dans l'ordre inverse,
    « stats » serait avale comme un code commune et l'endpoint de
    statistiques deviendrait inatteignable.
    """
    chemins = _routes()

    assert chemins.index("/api/v1/land/commune/{code_commune}/stats") < chemins.index(
        "/api/v1/land/commune/{code_commune}"
    )
