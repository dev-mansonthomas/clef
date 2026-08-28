"""`.env.example` est la référence des variables d'environnement — donc elle se teste.

Le 2026-08-28, TROIS fichiers prétendaient décrire cette configuration, et les trois
se contredisaient :

* `backend/.env` portait **18 clés que rien ne lit**, dont cinq `VALKEY_*` — vestiges
  du Memorystore for Valkey détruit le 2026-08-26 — et lui manquait les trois
  `*_SPREADSHEET_ID` qu'exige pourtant `./run_local.sh --real` ;
* `backend/.env.example` annonçait quatre `SHEETS_URL_*` que seul `validate_env.py`
  connaît ;
* `validate_env.py` lui-même est périmé.

Aucun de ces fichiers n'était vérifiable, donc aucun n'était fiable, donc le suivant
qui cherchait la bonne valeur choisissait le mauvais fichier. Ce test rend
`.env.example` **exact par construction** : il compare sa liste de clés à ce que le
code lit réellement, dans les deux sens.

⚠️ La comparaison doit inclure les champs de `pydantic-settings`, lus PAR NOM sans
aucun `os.getenv` visible. Un test qui ne grep que `getenv` déclarerait orphelines
une douzaine de variables pourtant lues — c'est le piège déjà rencontré dans
`test_cloudrun_template.py`.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
EXEMPLE = BACKEND / ".env.example"
APP = BACKEND / "app"


def _lues_par_le_code() -> set[str]:
    noms: set[str] = set()
    motif = re.compile(
        r'(?:getenv|environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'
    )
    for fichier in APP.rglob("*.py"):
        texte = fichier.read_text(encoding="utf-8")
        noms |= set(motif.findall(texte))
        noms |= set(re.findall(r'environ\[\s*["\']([A-Z_][A-Z0-9_]*)["\']', texte))

    from app.auth.config import AuthSettings

    noms |= {champ.upper() for champ in AuthSettings.model_fields}
    return noms


def _declarees_dans_l_exemple() -> set[str]:
    noms = set()
    for ligne in EXEMPLE.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        noms.add(ligne.split("=", 1)[0].strip())
    return noms


def test_l_exemple_declare_tout_ce_que_le_code_lit():
    """Une variable lue mais absente de l'exemple tourne sur son défaut, sans erreur.

    C'est ainsi que les trois `*_SPREADSHEET_ID` ont disparu de `.env` sans que rien
    ne le signale, et que `./run_local.sh --real` a cessé de pouvoir démarrer.
    """
    manquantes = _lues_par_le_code() - _declarees_dans_l_exemple()
    assert not manquantes, (
        f"variables lues par le code et absentes de .env.example : {sorted(manquantes)}. "
        "Leur absence ne provoque aucune erreur — l'application tourne sur son défaut."
    )


def test_l_exemple_ne_declare_rien_que_le_code_ignore():
    """Une clé que rien ne lit est un piège : elle a l'air d'un réglage.

    Cinq `VALKEY_*` sont restées dans `.env` des mois après la destruction du
    Memorystore, et `JWT_SECRET` après le retrait de toute signature de jeton. Un
    lecteur y voit une configuration à ajuster, et cherche pourquoi son changement
    n'a aucun effet.
    """
    orphelines = _declarees_dans_l_exemple() - _lues_par_le_code()
    assert not orphelines, (
        f"clés déclarées que le code ne lit jamais : {sorted(orphelines)}. "
        "Soit le nom est faux, soit la clé est morte — dans les deux cas elle trompe."
    )


def test_aucune_valeur_reelle_dans_l_exemple():
    """L'exemple est versionné : il ne doit porter aucun secret ni identifiant réel.

    Les valeurs sensibles y sont laissées VIDES, marquées « ← À RENSEIGNER ».
    """
    brut = EXEMPLE.read_text(encoding="utf-8")
    # Les COMMENTAIRES décrivent la forme attendue (« GOCSPX-… ») : c'est de la
    # documentation utile, pas une valeur. Ne scruter que les affectations.
    texte = "\n".join(l.split("#", 1)[0] for l in brut.splitlines())
    for motif, quoi in (
        (r"GOCSPX-\S", "un client secret Google"),
        (r"[0-9]{6,}-[a-z0-9]{16,}\.apps\.googleusercontent\.com", "un client_id réel"),
        (r"-----BEGIN", "une clé privée"),
    ):
        assert not re.search(motif, texte), f".env.example contient {quoi}"

    for cle in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "QR_CODE_SALT"):
        ligne = next(
            l for l in brut.splitlines() if l.startswith(f"{cle}=")
        )
        valeur = ligne.split("=", 1)[1].split("#")[0].strip()
        assert valeur == "", f"{cle} doit rester vide dans l'exemple, trouvé « {valeur} »"
