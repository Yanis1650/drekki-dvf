"""Conversion des lignes DuckDB vers les modeles du domaine.

Deux duplications sont resorbees ici. Le mapping d'une transaction etait ecrit
mot pour mot dans `get_transactions_by_commune` et `get_transactions_in_bbox`,
et les deux convertisseurs de mutations ne differaient que par la presence des
coordonnees.
"""

from datetime import date, datetime
from decimal import Decimal

from app.domain.models import MutationAggregate, NatureMutation, Transaction, TypeLocal

# Colonnes attendues par `vers_transactions`, dans cet ordre.
COLONNES_TRANSACTION = (
    "id_mutation, date_mutation, nature_mutation, valeur_fonciere, "
    "code_commune, id_parcelle, type_local, surface_reelle_bati, nombre_pieces"
)

# Colonnes attendues par `vers_mutations`, dans cet ordre. Les deux dernieres
# (longitude, latitude) ne sont lues qu'avec `avec_coordonnees=True`, et la
# requete par rayon intercale `prix_m2` en 9e position.
COLONNES_MUTATION = (
    "id_mutation, date_mutation, nature_mutation, valeur_fonciere, "
    "code_commune, parcelles, surface_habitable_totale, nombre_locaux"
)


def prefixer(colonnes: str, alias: str) -> str:
    """Prefixe chaque colonne par un alias de table (`t.id_mutation`, ...)."""
    return ", ".join(f"{alias}.{c.strip()}" for c in colonnes.split(","))


def vers_date(valeur) -> date:
    """DuckDB rend une date ou une chaine selon le type declare de la colonne."""
    if isinstance(valeur, str):
        return datetime.strptime(valeur, "%Y-%m-%d").date()
    return valeur


def appliquer_bornes(
    requete: str,
    params: list,
    date_from: date | None,
    date_to: date | None,
    colonne: str = "date_mutation",
) -> str:
    """Ajoute les bornes de date a une clause WHERE deja ouverte.

    Rend la requete completee ; `params` est enrichi sur place, dans l'ordre.

    Les deux bornes s'ajoutent independamment. C'est la forme qui evite le
    defaut corrige dans `get_mutations_in_radius` : la version precedente
    inserait chaque borne par `str.replace` sur une ancre commune, si bien que
    la premiere insertion consommait l'ancre et que `date_to` etait ensuite
    ignoree sans la moindre erreur.
    """
    if date_from:
        requete += f" AND {colonne} >= ?"
        params.append(date_from)
    if date_to:
        requete += f" AND {colonne} <= ?"
        params.append(date_to)
    return requete


def vers_transactions(resultats: list) -> list[Transaction]:
    """Lignes de `transactions` vers le domaine, colonnes dans l'ordre ci-dessus."""
    return [
        Transaction(
            id_mutation=r[0],
            date_mutation=r[1],
            nature_mutation=NatureMutation(r[2]),
            valeur_fonciere=Decimal(str(r[3])),
            code_commune=r[4],
            id_parcelle=r[5],
            type_local=TypeLocal(r[6]) if r[6] else None,
            surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
            nombre_pieces=r[8],
        )
        for r in resultats
    ]


def vers_mutations(
    resultats: list, *, avec_coordonnees: bool = False
) -> list[MutationAggregate]:
    """Lignes de `mutations_aggregated` vers le domaine.

    `nature_mutation` est ecrite en dur a « Vente » alors que la colonne r[2]
    est selectionnee : conduite d'origine, conservee telle quelle et epinglee
    par `test_mutations_nature_forcee_a_vente`.
    """
    mutations = []
    for r in resultats:
        coordonnees = (
            {"longitude": r[9], "latitude": r[10]} if avec_coordonnees else {}
        )
        mutations.append(
            MutationAggregate(
                id_mutation=r[0],
                date_mutation=vers_date(r[1]),
                nature_mutation=NatureMutation("Vente"),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
                **coordonnees,
            )
        )
    return mutations
