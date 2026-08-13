# État de la reprise documentaire

Reconstruction menée le **2026-08-13** sur la branche `feat/sinistres-franchise`,
à partir du **code, des tests et de l'historique git seuls**.

## 1. Ce qui a été récupéré (vérifié)

| Élément | Méthode |
|---|---|
| Architecture, composants, flux de données | lecture du code, 86 routes relevées dans l'OpenAPI généré |
| Modèle de données Valkey complet | relevé des constructions de clés dans `valkey_service.py` |
| Modèle d'autorisation et chaîne de gardes | lecture de `app/auth/` |
| Commandes réelles d'install / build / test / run | **exécutées**, sorties collées dans `CLAUDE.md` |
| État réel des tests | **exécuté** : 12 échecs / 356 passés sans Valkey, 8 / 360 avec |
| État réel de Terraform | **exécuté** : les deux racines échouent à `validate` |
| Chronologie produit en 11 phases | `git log` complet |
| Renommages et migrations | commits identifiés (`a1695cb`, `1c59754`, `f206ac9`, `22d1759`) |
| Questions ouvertes de l'auteur et leurs réponses | `docs/specs-gestion-factures.md` §7, résolues en `ee66eb9` |
| ~60 constats de défauts et dérives | `docs/TODO.md` |

Bonne surprise : **un artefact documentaire authentique a survécu**,
`docs/specs-gestion-factures.md` (530 lignes, 2026-03-21). Il a été écrit *avant*
l'implémentation, puis enrichi de la résolution de ses propres questions ouvertes.
**Il n'a pas été écrasé** ; il est référencé par `docs/specs/dossiers-reparation.md`
et par le registre. Aucun fichier de `docs/` n'a jamais été supprimé de l'historique
— il n'y avait rien à exhumer.

## 2. Ce qui est inféré (à valider)

Tout est marqué `(inferred — verify)` dans les documents. Les inférences
structurantes :

- **Le *pourquoi* de chaque choix technique.** Valkey, Google Sheets comme
  référentiel, session sans état : les ADR 0001 à 0005 reconstruisent le *quoi* et
  les conséquences, mais leur rubrique « contexte » est une hypothèse.
- **Le besoin utilisateur.** Le PRD déduit les besoins du comportement du code. Rien
  n'a été recueilli auprès d'utilisateurs.
- **Les volumes attendus**, qui justifieraient l'absence de pagination et le `SCAN`
  de recherche de token.
- **L'origine du montant de 350 €** de franchise, codé comme défaut à trois endroits.
- **Quel arbre Terraform est autoritaire.**

## 3. ⚠️ RÉVISION DU 2026-08-13 — une grande partie a été retrouvée

La section 3 ci-dessous a été rédigée avant que le propriétaire ne fournisse
**`debug/specs-intent.md`** (2306 lignes) : le plan Augment Intent d'origine, avec
`## Key Decisions`, `## Assumptions`, `## Non-Goals`, et les Waves 1 à 30+.

**Ce que ce fichier restitue, et que j'avais déclaré perdu :**

| Point déclaré perdu | Ce que le fichier retrouvé en dit |
|---|---|
| Le *pourquoi* d'Okta → Google | `## Assumptions` : « ~~Okta~~ → Google OAuth 2.0 … (✅ migré Wave 6) ». Décision tracée |
| Le *pourquoi* de Redis → Valkey | Wave 10 « **Valkey 8 au lieu de Redis Memorystore** », puis Wave 10 « Correction Memorystore Valkey (**pas Compute Engine**) » — ce dernier explique le `google_compute_instance.valkey` mort dans `outputs.tf` (H7) |
| Les allers-retours sur le stockage JSON | Wave 14 « Corrections UX et Redis JSON », Wave 15 « Valkey 8 avec JSON natif », Wave 15 « Fix : module valkey-json », Wave 16 « JSON natif complet ». La séquence est tracée |
| Le statut de la source de vérité | Conception initiale : Sheets = vérité, MemoryStore = cache (TTL 1 an). Puis Wave 11 « **Architecture Multi-Tenant & Valkey Primaire** ». Voir [ADR 0002](adr/0002-google-workspace-comme-referentiel-de-verite.md), réécrit |
| Le référentiel de tickets (16.3, 28.7…) | Les tâches numérotées y figurent avec leurs liens `intent://local/task/<uuid>` |
| La structure du référentiel 19 colonnes | Documentée colonne par colonne — **identique** à ma reconstruction dans `docs/specs/import-vehicules-csv.md`, y compris « Assurance 2026 » et « N° Serie BAUS ». Ma reconstruction est donc validée |
| Le périmètre initial | `## Non-Goals` : la gestion des factures véhicules était **hors périmètre MVP**. Tout le module Dossiers Réparation a été construit après cette exclusion |

**Reste réellement non tracé** (le fichier dit *ce qui* a été décidé, rarement *pourquoi
ce choix plutôt qu'un autre*) : l'arbitrage technique ayant conduit à Valkey plutôt
qu'à PostgreSQL ou Firestore ; la raison de l'abandon de `sinistre_id` ; et la cause
des 4,5 mois d'arrêt.

⚠️ **Le fichier est dans `debug/`, gitignoré par le commit `2e08454`.** Il doit être
versionné sous `docs/` pour ne pas être reperdu. Il contient un email de contact
tiers : traitement à décider avant versionnement.

## 3bis. Ce qui était considéré comme perdu (rédigé avant la révision ci-dessus)

**Preuve matérielle de la perte** : **227 des 280 commits** portent des en-têtes
`Agent-Id: agent-<uuid>` et/ou `Linked-Note-Id: <uuid>`. Ces identifiants renvoient
à un système de mémoire d'agent externe. Aucun fichier, dossier ni UUID
correspondant n'existe dans le dépôt ni dans l'arbre de travail.

Sont irrécupérables :

1. **La justification des trois pivots d'architecture** : Okta → Google, Redis →
   Valkey (avec deux allers-retours sur la stratégie de stockage JSON), Google
   Calendar → réservations natives Valkey. Les commits décrivent le *quoi*, jamais
   le *pourquoi*.
2. **La raison de l'abandon de `sinistre_id`** au profit de deux booléens.
3. **Le référentiel de tickets.** Les numéros `16.3`, `16.4`, `28.7` apparaissent
   dans des messages de commit ; le tracker n'est pas dans le dépôt.
4. **La cause des 4,5 mois d'arrêt** (2026-03-24 → 2026-08-12).
5. **L'intention exacte au moment de l'arrêt.** Déduite : finir le câblage
   sinistre/franchise puis ouvrir une PR. Non confirmée.

⚠️ **Une nuance d'honnêteté.** Le commit de merge `2952215` porte un corps
inhabituellement explicite sur ses raisons. Ce n'est **pas** un vestige de l'auteur
d'origine : il a été rédigé le 2026-08-13 au cours de cette même session de reprise.
Ne pas le lire comme une trace retrouvée.

## 4. Les 3 prochaines actions recommandées

1. **Fermer C1 — les données personnelles exposées sans authentification.**
   Trois routes de `app/main.py` renvoient nom, prénom, email et UL de bénévoles à
   un appelant anonyme (vérifié par requête réelle). Enjeu RGPD sur des données de
   bénévoles Croix-Rouge, et correctif de quelques lignes. À faire avant tout autre
   développement, et avant tout nouveau déploiement.

2. **Fermer C2 — la prise de véhicule échoue en 422.** Le parcours central de l'app
   `form` est inopérant : les noms de champs du formulaire ne correspondent à aucun
   champ requis du modèle backend. À corriger *avec* un test d'intégration qui
   touche le vrai backend — l'e2e actuel mocke l'API, ce qui est précisément
   pourquoi la panne est passée inaperçue.

3. **Rendre la CI capable de dire la vérité.** Dans l'ordre : trancher H2 (la
   fixture CSV perdue, dernière cause de rouge), ajouter
   `needs: [backend-test, frontend-build]` au job de déploiement et faire tourner
   les tests aussi sur `push` (H1), puis réparer `ng test` (M4) et l'exécuter en CI.
   Sans cela, aucun des correctifs suivants ne sera protégé contre la régression.

Le reste — Terraform cassé (H7), franchise non enregistrable (M1), dérive de la
documentation de déploiement (M23) — est réel mais vient après ces trois-là.

## 5. Toolchain & écarts VM

Mesuré **dans la VM**, le 2026-08-13.

> ⚠️ **Ce tableau décrit la situation *avant* le chantier « CI verte » du même jour.**
> Il est conservé comme état des lieux de départ. Après chantier : le projet exige
> Python **3.14** (installé via `uv`, toujours absent du `PATH`), Node **24** partout
> (donc plus de divergence), le datastore est **`redis:8.10`**, et
> `@playwright/test` est en **1.62.1** — version qui cible exactement le
> `chromium-1234` déjà en cache, ce qui a débloqué les 30 e2e. Voir la section
> « Après le chantier » plus bas.

| Outil | Version requise (+ où détectée) | Cette VM a | Verdict |
|---|---|---|---|
| Python | `>=3.13` (`backend/pyproject.toml:9`) ; `python:3.13-slim` (`backend/Dockerfile:2,22`) ; `python-version: '3.13'` (`.github/workflows/ci.yml:27`) | `python3` du PATH = **3.12.3** ; mais `uv` dispose d'un **CPython 3.13.14** managé, et le venv du projet tourne dessus | **OK via `uv`**, mauvaise version sur le PATH |
| `python3 -m venv` | nécessaire au parcours d'install documenté (`README.md`) | **cassé** : `ensurepip is not available` | **MANQUANT** |
| Node.js | `22` (`frontend/Dockerfile:4`, `frontend/Dockerfile.dev:1`, `.github/workflows/ci.yml:61`) | **24.18.0** | **MAUVAISE VERSION** (les 3 builds passent tout de même) |
| npm | `10.9.4` (`frontend/package.json:29`, champ `packageManager`) | 11.16.0 global, mais `npx ng version` rapporte **npm 10.9.4** dans le projet | OK en pratique |
| Angular CLI | `^21.2.2` (`frontend/package.json:58`) | **21.2.2** via `npx` (présent dans `node_modules`) | **OK** |
| Valkey serveur | `valkey/valkey-bundle:8` (`docker-compose.yml:4`) — **modules JSON et Search requis** | lancé en conteneur, `module list` → `json`, `search` | **OK** (conteneur, pas natif VM) |
| `redis-cli` | client Valkey 8 | 8.8.0 | **OK** |
| Docker | Engine + Compose v2 (`run_local.sh:12,18`) | Docker 29.5.2, Compose v5.1.4 | **OK** |
| OpenTofu | `required_version = ">= 1.0"` (`backend/terraform/providers.tf:2`, `infra/main.tf:6`) | 1.12.3 | **OK** (validate seul dans la VM) |
| `terraform` (binaire) | invoqué littéralement par `DEPLOYMENT.md:117-124` | absent | **NON REQUIS EN VM** — `tofu` le remplace ; la doc est obsolète (M23) |
| `gcloud` | `.github/workflows/ci.yml:97`, `backend/scripts/setup_gcp.sh` | absent | **NON REQUIS EN VM** — action créditée, côté hôte par le modèle de sécurité |
| `gh` | `backend/scripts/setup_github_secrets.sh:65-78` | absent | **NON REQUIS EN VM** — idem |
| Playwright | `^1.58.2` (`frontend/package.json:60`) | navigateurs en cache dans `~/.cache/ms-playwright` | **OK** |
| clasp (Apps Script) | aucun `.clasp.json` ni `appsscript.json` — déploiement manuel par l'éditeur web | absent | **NON REQUIS EN VM** |
| Go, Java/Maven, .NET, Rust | **aucune trace** dans le dépôt (pas de `go.mod`, `pom.xml`, `build.gradle`, `composer.json`, `rust-toolchain.toml`) | présents | **NON REQUIS** pour ce projet |
| PHP / Composer | non utilisés | absents | **NON REQUIS** |
| pyenv / nvm / asdf / mise / sdkman | aucun fichier d'ancrage dans le dépôt (`.nvmrc`, `.node-version`, `.python-version`, `.tool-versions` : tous absents) | **aucun installé** | **MANQUANT** — voir ci-dessous |

### Risque de divergence entre projets

Deux cas sont **observés, pas supposés** :

- **Node.** Le projet épingle Node 22 en trois endroits indépendants ; la VM fournit
  Node 24. Le décalage existe déjà. Un autre projet exigeant Node 20 ou 24
  entrerait en collision, et rien dans le dépôt n'ancre la version côté poste.
- **Python.** `requires-python = ">=3.13"` contre un `python3` en 3.12.3, sans
  binaire `python3.13` sur le PATH et avec `python3 -m venv` cassé. Aujourd'hui la
  situation est masquée par `uv`, qui provisionne un 3.13 managé, et par le fait que
  l'exécution réelle se fait dans Docker ou dans GitHub Actions.

Conclusion : le besoin n'est pas « installer une version de plus », c'est **un
gestionnaire de versions par projet**. Un seul outil couvre Node et Python et lit un
fichier d'ancrage versionné : **`mise`** (ou `asdf`).

### VM provisioning request

```
# ==== VM provisioning request — projet CLEF (2026-08-13) ====
# À ajouter à scripts/vm-provision.sh, puis ./03-vm-up.sh

# 1. BLOQUANT — python3 -m venv est cassé (ensurepip absent).
#    Le parcours d'install documenté du projet échoue.
apt-get install -y python3.12-venv

# 2. REQUIS — gestionnaire de versions par projet.
#    Motif : CLEF épingle Node 22 (Dockerfile + CI) alors que la VM a Node 24,
#    et exige Python >= 3.13 alors que le python3 du PATH est en 3.12.3.
#    Mes projets divergeront sur ces deux runtimes : un install global ne suffit pas.
#    mise couvre Node et Python avec un fichier .tool-versions versionné par projet.
curl https://mise.run | sh
# puis, dans le dépôt CLEF (à committer) :
#   mise use node@22
#   mise use python@3.13

# 3. RECOMMANDÉ — Node 22 disponible à côté de Node 24.
#    Fourni par mise (point 2) ; sinon installer Node 22 explicitement.
mise install node@22

# ---- Volontairement NON demandé ----
# gcloud, gh, terraform : actions créditées ou tournées vers l'extérieur.
#   Elles restent côté hôte conformément au modèle de sécurité. tofu 1.12.3
#   suffit en VM pour fmt/init -backend=false/validate.
# valkey-server : tourne en conteneur via docker compose. redis-cli 8.8.0
#   couvre déjà l'inspection manuelle.
# uv : déjà présent (0.11.26) et déjà en usage — il contourne proprement
#   le venv cassé et fournit CPython 3.13.14.
# Go, Java/Maven, .NET, Rust, PHP : ce projet ne les utilise pas.
# ============================================================
```

## 6. Questions qui nécessitent l'auteur ou le commanditaire

Reportées en fin de la synthèse de session ; les cinq retenues portent sur le
montant de la franchise, l'ambition multi-DT, l'arbre Terraform autoritaire, le
statut du référentiel Google Sheets, et l'arbitrage sur la fixture CSV perdue.


---

## Après le chantier « CI verte » — 2026-08-13 (seconde passe)

Ce que ce chantier a changé par rapport à l'état des lieux ci-dessus. Toutes les
valeurs sont **mesurées par exécution**.

### Toolchain, après alignement

| Outil | Exigé par le dépôt | Cette VM | Verdict |
|---|---|---|---|
| Python | `>=3.14` (`pyproject.toml`, `Dockerfile`, `ci.yml`) | `python3` du PATH = **3.12.3** ; `uv` gère un **CPython 3.14.6** | **OK via `uv`** — le PATH reste en 3.12, `tests/test_runtime.py` garde l'écart |
| `python3 -m venv` | plus au parcours documenté | **réparé** (`ensurepip` présent) | OK, mais donnerait un venv 3.12 : insuffisant |
| Node.js | **24** (Dockerfiles + `ci.yml`) | **24.18.0** | **OK** — divergence supprimée |
| Datastore | **`redis:8.10`** (`docker-compose.yml`) | conteneur ; `MODULE LIST` → `ReJSON`, `search`, `timeseries`, `bf`, `vectorset` | **OK** |
| `redis-cli` | fourni par l'image | 8.8.0 en VM, 8.10 dans l'image | **OK** |
| Playwright | **`^1.62.1`** (`package.json`) | `chromium-1234` **déjà en cache** — aucun téléchargement | **OK** — c'est ce bump qui a débloqué les e2e |

### Ce que la mise au vert a révélé

Rendre les suites exécutables a mis au jour des défauts qu'aucun outil ne pouvait
voir tant que rien ne tournait. Ils sont tous consignés dans
[`docs/TODO.md`](TODO.md), section « Constats nouveaux » :

- **Deux écrans inaccessibles** (`/super-admin`, `/configuration-ul`) : routes et
  guards en place, aucun lien de navigation (H9, corrigé).
- **Trois motifs de mock e2e ne correspondaient à aucune URL réelle** — les requêtes
  fuyaient vers le proxy du serveur de dev (corrigés).
- **Deux jeux de données mock hors contrat d'API** : `status_ct` en chaîne au lieu de
  `{value, color}`, et les réservations sur l'ancien modèle Google Calendar (corrigés).
- **Une fixture e2e dépendante de l'heure d'exécution** : la réservation était placée
  « dans 24 h », donc hors de la plage horaire affichée par le calendrier passé 22 h
  (corrigée).
- **L'autorisation évaluée après l'acquisition du datastore** dans les 8 routes de
  `config.py` (M26, non corrigé — hors périmètre).
- **Un flake de tri** dans l'historique du carnet de bord (M27, observé, non corrigé).

### Ce qui reste perdu ou ouvert

Rien de ce chantier ne change les conclusions de la section « Ce qui est
définitivement perdu » ci-dessus. En particulier :

- **Terraform reste cassé** et provisionne toujours un Memorystore for **Valkey** :
  seul le nom du fichier a changé (`memorystore_valkey.tf` → `memorystore_redis.tf`).
  La cible de production n'est pas tranchée — voir
  [ADR 0006](adr/0006-redis-8-10-remplace-valkey.md) et `docs/TODO.md` H7/N1.
- **Les constats de sécurité** C1, C3, S1–S12 et les bugs R1–R7 sont **intacts** : ce
  chantier ne les a ni corrigés ni aggravés.
