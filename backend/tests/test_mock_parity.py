"""Parité mock / réel : toute méthode appelée doit exister sur le service réel.

Classe de bug rencontrée trois fois dans ce dépôt :

- **M16** — `calendar_service.get_events()` (le service réel expose `list_events`) ;
- **M31** — `sheets_service.get_benevole_by_email()`, sur le chemin
  d'**authentification** : en mode réel, `AttributeError` avalée deux fois, et tout
  utilisateur tombait à « Bénévole » sans périmètre, sans un log ;
- et deux appels de `routers/calendar.py` découverts en auditant les deux premiers.

Le point commun : les tests tournent en `USE_MOCKS=true`, donc le mock satisfait des
appels que l'implémentation réelle ne connaît pas. Aucun test ne pouvait le voir.

Ce test compare les appels du code aux méthodes réellement définies. Les quatre
occurrences existantes sont listées en dette explicite : elles ne font pas échouer la
suite, mais **toute nouvelle occurrence le fera**.
"""
import collections
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parent.parent / "app"

#: Correspondance résolue en suivant les fabriques de `app/mocks/service_factory.py`.
SERVICES = {
    "sheets_service": (["services/sheets_real.py"], "mocks/google_sheets_mock.py"),
    "calendar_service": (["services/calendar_service.py"], "mocks/google_calendar_mock.py"),
    "drive_service": (
        ["services/drive_real.py", "services/drive_service.py", "services/drive.py"],
        "mocks/google_drive_mock.py",
    ),
    "gmail_service": (
        ["services/gmail_real.py", "services/gmail_service.py"],
        "mocks/google_gmail_mock.py",
    ),
}

#: Méthodes du client `googleapiclient`, atteintes par chaînage : hors périmètre.
GOOGLE_API_CLIENT = {"files", "spreadsheets", "messages", "users", "events", "calendars"}

#: Dette connue au 2026-08-20. Chaque entrée est un appel qui **échouera en mode
#: réel**. Retirer une ligne d'ici quand le bug est corrigé — ne jamais en ajouter
#: sans avoir consigné le constat correspondant dans docs/TODO.md.
KNOWN_DEBT = {
    ("sheets_service", "get_vehicule_by_indicatif"),   # routers/reservations.py — M32
    ("calendar_service", "get_calendar_id"),           # routers/calendar.py     — M32
    ("calendar_service", "_get_calendar_name"),        # routers/calendar.py     — M32
    ("calendar_service", "get_events"),                # routers/ical.py         — M16
}


def _defined_methods(relative_paths) -> set:
    found = set()
    for rel in relative_paths:
        path = APP / rel
        if path.is_file():
            found |= set(
                re.findall(r"def\s+([a-zA-Z_]\w*)\s*\(", path.read_text(encoding="utf-8"))
            )
    return found


def _calls() -> dict:
    calls = collections.defaultdict(set)
    for source in APP.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        for var in SERVICES:
            # `(?<![\w.])` exclut le chaînage `x.service.y(`.
            for method in re.findall(rf"(?<![\w.]){var}\.([a-zA-Z_]\w*)\s*\(", text):
                calls[var].add((method, source.relative_to(APP).as_posix()))
    return calls


def test_no_new_call_to_a_method_missing_from_the_real_service():
    calls = _calls()
    unexpected = []

    for var, (real_paths, mock_path) in SERVICES.items():
        real = _defined_methods(real_paths)
        mock = _defined_methods([mock_path])
        for method, where in sorted(calls[var]):
            if method in real or method in GOOGLE_API_CLIENT:
                continue
            if (var, method) in KNOWN_DEBT:
                continue
            origin = "seulement sur le mock" if method in mock else "nulle part"
            unexpected.append(
                f"{var}.{method}() appelé par app/{where} — défini {origin}"
            )

    assert not unexpected, (
        "Appel(s) qui échoueront en mode réel (USE_MOCKS=false) :\n  "
        + "\n  ".join(unexpected)
        + "\n\nCorriger l'appel, ou l'ajouter à KNOWN_DEBT avec un constat dans "
        "docs/TODO.md si la correction est hors périmètre."
    )


def test_known_debt_is_still_accurate():
    """La dette listée doit rester réelle.

    Sans cela, une entrée obsolète masquerait une régression : si le bug est corrigé
    puis réintroduit sous le même nom, la liste l'absoudrait en silence.
    """
    calls = _calls()
    stale = []

    for var, method in sorted(KNOWN_DEBT):
        real_paths, _ = SERVICES[var]
        still_called = any(m == method for m, _ in calls[var])
        still_missing = method not in _defined_methods(real_paths)
        if not still_called:
            stale.append(f"{var}.{method}() n'est plus appelé — retirer de KNOWN_DEBT")
        elif not still_missing:
            stale.append(f"{var}.{method}() existe désormais — retirer de KNOWN_DEBT")

    assert not stale, "Dette obsolète :\n  " + "\n  ".join(stale)
