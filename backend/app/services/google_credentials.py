"""Chargement des credentials Google, partagé par les services réels.

Deux provenances, une seule identité :

- **En local**, `GOOGLE_APPLICATION_CREDENTIALS` pointe un fichier de clé de service
  account. C'est le mode de développement, et il reste prioritaire.
- **Sur Cloud Run**, le service s'exécute **sous** le service account : les credentials
  viennent du serveur de métadonnées, sans qu'aucune clé n'existe. C'est ce que fait
  `google.auth.default()`.

Pourquoi ça compte : quatre services dupliquaient le même chargement, et tous
**exigeaient** un fichier de clé. Un déploiement imposait donc de créer une
`google_service_account_key` à longue durée — le mauvais patron pointé par le constat
H6 — dont la clé privée se retrouvait en clair dans le state Terraform.

Aucune délégation à l'échelle du domaine n'est utilisée dans le dépôt : l'identité
obtenue par ADC est exactement celle qu'un fichier de clé du même service account
donnerait. La bascule ne change donc aucun droit d'accès. Les feuilles et dossiers
Drive doivent, dans les deux cas, être partagés avec l'adresse du service account.
"""
import logging
import os
from pathlib import Path
from typing import List

from google.auth import default as google_auth_default
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


def load_service_credentials(scopes: List[str]):
    """Retourne des credentials de service account pour les scopes demandés.

    Args:
        scopes: scopes OAuth requis par l'API appelée

    Returns:
        Objet de credentials utilisable par `googleapiclient.discovery.build`

    Raises:
        RuntimeError: si aucune des deux provenances n'aboutit, avec le moyen d'y
            remédier dans le message.
    """
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Un chemin qui n'existe pas ne doit pas faire échouer le démarrage : le cas réel
    # est un `.env` de développement déployé tel quel, pointant `/credentials/…` alors
    # que rien n'est monté. L'identité attachée suffit alors.
    if key_path and Path(key_path).is_file():
        logger.info("Credentials Google chargées depuis %s", key_path)
        return service_account.Credentials.from_service_account_file(
            key_path, scopes=scopes
        )

    if key_path:
        logger.warning(
            "GOOGLE_APPLICATION_CREDENTIALS pointe %s, qui n'existe pas : "
            "repli sur l'identité attachée (ADC).", key_path
        )

    try:
        credentials, project = google_auth_default(scopes=scopes)
    except Exception as exc:
        raise RuntimeError(
            "Aucune credential Google disponible : ni fichier de clé "
            "(GOOGLE_APPLICATION_CREDENTIALS) ni identité attachée (ADC). "
            f"Cause : {exc}. Sur Cloud Run, vérifier que le service tourne sous un "
            "service account ; en local, monter une clé ou lancer avec USE_MOCKS=true."
        ) from exc

    logger.info("Credentials Google obtenues par ADC (projet %s)", project)
    return credentials
