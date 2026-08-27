"""Base commune aux indisponibilités de données.

Les endpoints protègent leur corps par un `except Exception` qui renvoie 500.
Sans classe commune, ce filet avalait aussi les indisponibilités légitimes et
les transformait en « erreur serveur » : la carte a ainsi renvoyé un 500 sur
son premier chargement, au lieu du 503 explicite prévu.

Chaque endpoint ré-émet `ResourceUnavailableError` avant son `except Exception`
générique ; les gestionnaires enregistrés dans `app.main` la traduisent en 503.
"""


class ResourceUnavailableError(RuntimeError):
    """Une ressource nécessaire n'est pas disponible sur ce serveur.

    Ce n'est pas une panne : la donnée n'a pas été chargée, ou une extension
    optionnelle manque. Le client doit recevoir 503, jamais 500.
    """
