# Décisions d'architecture

Un fichier par décision structurante : son contexte, ce qui a été décidé, ce
que cela coûte, et ce qui a été écarté. Une décision qui n'a pas d'alternative
crédible n'est pas une décision — elle n'a pas sa place ici.

Ces documents ne sont pas mis à jour quand le code change : ils datent une
décision. Si une décision est renversée, on ajoute un enregistrement qui la
remplace et on marque l'ancien comme remplacé.

| # | Décision | Statut |
|---|---|---|
| [0001](0001-duckdb-lecture-seule.md) | DuckDB en lecture seule plutôt qu'une base transactionnelle | Acceptée |
| [0002](0002-absence-de-donnee-explicite.md) | Une donnée absente est un `503`, jamais une valeur par défaut | Acceptée |
| [0003](0003-une-base-par-departement.md) | Une base par département plutôt qu'une base France entière | Acceptée |
| [0004](0004-releases-dvf-immuables.md) | Une release DVF est immuable et franchit une porte qualité | Acceptée |
| [0005](0005-charte-verifiee-par-script.md) | La charte graphique est vérifiée par un script, pas par revue | Acceptée |
| [0006](0006-verifier-le-rendu-pas-seulement-le-build.md) | Le rendu est vérifié dans un navigateur, pas seulement le build | Acceptée |
