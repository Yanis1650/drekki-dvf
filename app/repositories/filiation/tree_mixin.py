"""Reconstruction de l'arbre d'ancetres : borne en profondeur, sûre aux cycles."""

import logging

from app.domain.filiation_models import FiliationNode
from app.repositories.interfaces import DEFAULT_DEPTH_LIMIT

logger = logging.getLogger(__name__)


class FiliationTreeMixin:
    """Remontee recursive de la chaine des meres."""

    def build_filiation_tree(
        self,
        code_commune: str,
        section: str,
        numero: str,
        depth_limit: int = DEFAULT_DEPTH_LIMIT,
        _depth: int = 0,
        _visited: set[str] | None = None,
    ) -> FiliationNode:
        """Reconstruct the ancestor tree with depth bounding and cycle detection.

        Algorithm:
          1. Vérifier si parcelle_key est déjà dans _visited → cycle → arrêt + ERROR
          2. Vérifier _depth >= depth_limit → troncature → arrêt + WARNING
          3. Récupérer les parents depuis DFI
          4. Récursion sur le premier parent (cas simple) avec _visited mis à jour
          5. Calcul optionnel de cohérence géométrique fille/mère

        Note : les remembrements (SAFER) ne figurent pas dans les DFI ;
        un arbre sans ancêtre connu peut être normal pour ces communes.
        """
        if _visited is None:
            _visited = set()

        parcelle_key = f"{section}{numero.zfill(4)}"

        # --- Cycle detection -----------------------------------------------
        if parcelle_key in _visited:
            logger.error(
                "Cycle détecté dans filiation : %s est déjà dans la chaîne ancêtre "
                "(commune=%s). Arbre partiel retourné.",
                parcelle_key,
                code_commune,
            )
            return FiliationNode(
                id_parcelle=parcelle_key,
                depth=_depth,
                truncated=True,
                coherence_geo="NON_VERIFIABLE",
            )

        # --- Depth limit -------------------------------------------------------
        if _depth >= depth_limit:
            logger.warning(
                "Arbre filiation tronqué à depth=%d pour parcelle %s (commune=%s)",
                depth_limit,
                parcelle_key,
                code_commune,
            )
            return FiliationNode(
                id_parcelle=parcelle_key,
                depth=_depth,
                truncated=True,
                coherence_geo="NON_VERIFIABLE",
            )

        # Mark current node as visited before recursing
        _visited.add(parcelle_key)

        # --- Query parents -----------------------------------------------------
        parents = self.get_parents(code_commune, section, numero)

        if not parents:
            # Leaf node — original parcel, no known division
            return FiliationNode(
                id_parcelle=parcelle_key,
                depth=_depth,
            )

        # Take first parent (most common case: simple division)
        # TODO: Handle multiple parents (fusion) in future version
        parent_filiation = parents[0]
        parent_section = parent_filiation.parcelle_mere[:2]
        parent_numero = parent_filiation.parcelle_mere[2:]

        # --- Optional geometry coherence ---------------------------------------
        # Build full 14-char parcel IDs for the geometry check.
        # dept_prefix: last 2 chars of code_departement
        # ("035" → "35", "2A" → "2A", "971" → "71")
        dept = parent_filiation.code_departement[-2:] if parent_filiation.code_departement else ""
        prefixe = parent_filiation.prefixe or "000"
        id_fille = dept + parent_filiation.code_commune + prefixe + section + numero.zfill(4)
        id_mere = dept + parent_filiation.code_commune + prefixe + parent_section + parent_numero

        coherence = self.calculate_coherence_geo(id_mere, id_fille)

        # --- Recurse on parent -------------------------------------------------
        parent_node = self.build_filiation_tree(
            code_commune,
            parent_section,
            parent_numero,
            depth_limit=depth_limit,
            _depth=_depth + 1,
            _visited=_visited,
        )

        return FiliationNode(
            id_parcelle=parcelle_key,
            parent=parent_node,
            date_division=parent_filiation.date_validation,
            nature_operation=parent_filiation.nature_dfi,
            depth=_depth,
            coherence_geo=coherence,
        )
