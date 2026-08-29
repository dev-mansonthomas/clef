#!/usr/bin/env bash
#
# CLEF — déploiement sur Cloud Run (étape 2 sur 2)
#
#   ./00-infra.sh dev      puis  ./01-gcp-deploy.sh dev
#
# À LANCER DEPUIS L'HÔTE. La VM de développement ne détient aucune credential
# sortante : le script échoue proprement si gcloud est absent.
#
# Les images sont construites par **Cloud Build**, pas localement : l'hôte n'a donc
# pas besoin de Docker, et l'image est construite dans la même région que le registre.
#
# Ce qu'il fait :
#   1. préflight — refuse de déployer si un prérequis manque, en le nommant ;
#   2. construit et pousse les images backend et frontend ;
#   3. déploie le service backend, avec Redis en sidecar, par `services replace` ;
#   4. déploie le frontend ;
#   5. vérifie /health et affiche les URLs.
#
# Idempotent : chaque exécution crée une nouvelle révision.

set -euo pipefail

ENVIRONMENT="${1:-}"
TEMPLATE="deploy/cloudrun-api.yaml.tpl"

usage() {
    cat <<'USAGE'
Usage : ./01-gcp-deploy.sh <dev|test|prod> [--components=api,frontend] [--skip-build]

  --components   Composants à déployer. Défaut : api,frontend
  --skip-build   Redéploie la dernière image poussée, sans reconstruire.
                 Utile pour ne changer qu'une variable d'environnement.

Prérequis : ./00-infra.sh <env> doit avoir été passé.
USAGE
}

COMPONENTS="api,frontend"
SKIP_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --components=*) COMPONENTS="${arg#*=}" ;;
        --skip-build)   SKIP_BUILD=true ;;
        --help|-h)      usage; exit 0 ;;
    esac
done

case "$ENVIRONMENT" in
    dev|test|prod) ;;
    "") echo "❌ Environnement manquant."; echo ""; usage; exit 2 ;;
    *)  echo "❌ Environnement inconnu : $ENVIRONMENT"; echo ""; usage; exit 2 ;;
esac

# ---------------------------------------------------------------------------
# Journalisation — transcription et rapport lisibles depuis la VM
# ---------------------------------------------------------------------------
# Le script tourne sur l'HÔTE, l'agent travaille dans la VM, et le dépôt est sur un
# montage partagé : écrire ici évite de recopier des sorties à la main pour analyse.
#
# `debug/` est gitignoré — rien de ceci n'est versionné.
#
# ⚠️ Aucune valeur de secret n'est journalisée. Le préflight LIT celles des trois
# secrets pour en vérifier la forme (voir plus bas), mais n'en écrit aucune : seul un
# verdict sort. Exception assumée, le `client_id` OAuth, affiché **quand il est
# refusé** — il n'est pas confidentiel, Google le publie dans chaque URL
# d'autorisation, et c'est la valeur que l'opérateur doit comparer à sa console.
# L'adresse du gestionnaire DT est notée comme présente ou absente, jamais recopiée :
# c'est une donnée personnelle.
DEBUG_DIR="debug/deploy"
mkdir -p "$DEBUG_DIR"
LOG_FILE="${DEBUG_DIR}/01-gcp-deploy.${ENVIRONMENT}.log"
REPORT_FILE="${DEBUG_DIR}/01-gcp-deploy.${ENVIRONMENT}.json"
: > "$LOG_FILE"

# Champs remplis au fil de l'exécution, écrits par le trap — donc présents même si le
# script s'arrête en cours de route, ce qui est précisément le cas intéressant.
R_PREFLIGHT="non atteint"
R_BACKEND_IMAGE=""
R_FRONTEND_IMAGE=""
R_BACKEND_URL=""
R_FRONTEND_URL=""
R_REDIRECT_URI=""
R_HEALTH=""
R_PUBLIC_DOMAIN=""
R_PUBLIC_VERIF=""
R_PASSES=0
R_STEP="démarrage"

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

ecrire_rapport() {
    local code=$?
    cat > "$REPORT_FILE" <<JSON
{
  "schemaVersion": 1,
  "tool": "01-gcp-deploy.sh",
  "ok": $([ "$code" -eq 0 ] && echo true || echo false),
  "exitCode": $code,
  "derniereEtape": "$(json_escape "$R_STEP")",
  "environnement": "$(json_escape "$ENVIRONMENT")",
  "projet": "$(json_escape "${PROJECT_ID:-}")",
  "region": "$(json_escape "${REGION:-}")",
  "tag": "$(json_escape "${TAG:-}")",
  "composants": "$(json_escape "$COMPONENTS")",
  "skipBuild": $SKIP_BUILD,
  "preflight": "$(json_escape "$R_PREFLIGHT")",
  "maxInstances": "$(json_escape "${MAX_INSTANCES:-}")",
  "minInstances": "$(json_escape "${MIN_INSTANCES:-}")",
  "redisMemory": "$(json_escape "${REDIS_MEMORY:-}")",
  "redisMaxmemory": "$(json_escape "${REDIS_MAXMEMORY:-}")",
  "emailGestionnaireDtRenseigne": $([ -n "${EMAIL_GESTIONNAIRE_DT:-}" ] && echo true || echo false),
  "spreadsheetIdsRenseignes": $([ -n "${VEHICULES_SPREADSHEET_ID:-}${BENEVOLES_SPREADSHEET_ID:-}${RESPONSABLES_SPREADSHEET_ID:-}" ] && echo true || echo false),
  "images": {
    "backend": "$(json_escape "$R_BACKEND_IMAGE")",
    "frontend": "$(json_escape "$R_FRONTEND_IMAGE")"
  },
  "passesServiceReplace": $R_PASSES,
  "urls": {
    "backend": "$(json_escape "$R_BACKEND_URL")",
    "frontend": "$(json_escape "$R_FRONTEND_URL")"
  },
  "uriRedirectionOauth": "$(json_escape "$R_REDIRECT_URI")",
  "health": "$(json_escape "$R_HEALTH")",
  "domainePublic": "$(json_escape "$R_PUBLIC_DOMAIN")",
  "verificationDomainePublic": "$(json_escape "$R_PUBLIC_VERIF")",
  "bucketInstantanes": "$(json_escape "${SNAPSHOTS_BUCKET:-}")",
  "transcription": "$(json_escape "$LOG_FILE")"
}
JSON
    echo ""
    echo "📝 Rapport : $REPORT_FILE"
    echo "   Transcription : $LOG_FILE"
}
trap ecrire_rapport EXIT

# Tout ce qui suit part à la fois à l'écran et dans la transcription.
exec > >(tee -a "$LOG_FILE") 2>&1

# ---------------------------------------------------------------------------
# Configuration de l'environnement
# ---------------------------------------------------------------------------
ENV_FILE="deploy/deploy.${ENVIRONMENT}.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ $ENV_FILE absent."
    echo "   Le copier depuis deploy/deploy.env.example et le renseigner."
    exit 1
fi
# Le chemin dépend de l'environnement : shellcheck ne peut pas le suivre statiquement.
set -a
# shellcheck disable=SC1090
. "./$ENV_FILE"
set +a

# Règles partagées avec 00-infra.sh — voir l'en-tête de ce fichier.
# `disable=SC1091` en plus de `source=` : sans l'option -x, shellcheck ne suit pas le
# fichier et sort en 1 sur un simple info — ce qui ferait échouer un contrôle de lint
# qui ne connaît pas l'option.
# shellcheck source=deploy/env-commun.sh disable=SC1091
. "./deploy/env-commun.sh"

: "${PROJECT_ID:?PROJECT_ID manquant dans $ENV_FILE}"
: "${REGION:?REGION manquant dans $ENV_FILE}"
: "${EMAIL_GESTIONNAIRE_DT:?EMAIL_GESTIONNAIRE_DT manquant dans $ENV_FILE}"

SERVICE_NAME="${SERVICE_NAME:-clef-api}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-clef-frontend}"
# Repli à 1, jamais 0 : chaque démarrage à froid rejoue le tirage du montage gcsfuse,
# qui échoue par intermittence et rend alors l'instance inutilisable. Ce n'est PAS un
# enjeu de perte de données — Redis écrit son instantané final sur SIGTERM en ~400 ms.
# Voir deploy/deploy.env.example.
MIN_INSTANCES="${MIN_INSTANCES:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
REDIS_MEMORY="${REDIS_MEMORY:-512Mi}"
# Limite interne de Redis, à tenir SOUS celle du conteneur : un BGSAVE duplique les
# pages modifiées pendant sa durée, et cette copie échappe à `maxmemory`. Au-delà,
# c'est Cloud Run qui tue le conteneur, et l'instance repart du dernier instantané.
# Défaut : 65 % de la limite, calculé plutôt que codé en dur pour suivre REDIS_MEMORY.
if [ -z "${REDIS_MAXMEMORY:-}" ]; then
    _mem_mo=${REDIS_MEMORY%[MmGg]i}
    case "$REDIS_MEMORY" in *[Gg]i) _mem_mo=$((_mem_mo * 1024)) ;; esac
    REDIS_MAXMEMORY="$(( _mem_mo * 65 / 100 ))mb"
fi
# Base publique. Quand un domaine est configuré, TOUTES les URL que l'application
# fabrique en découlent — un seul endroit à changer. Sinon on garde le comportement
# d'avant : les URL *.run.app relues après déploiement.
#
# ⚠️ PUBLIC_DOMAIN est un NOM D'HÔTE : ni schéma, ni chemin, ni port. La règle vit
# dans deploy/env-commun.sh, partagée avec 00-infra.sh : la même valeur alimente les
# URL de l'application ET le certificat, deux validations divergentes seraient pires
# qu'une.
#
# Le recoupement avec `public_domain` du tfvars a disparu avec les tfvars :
# `deploy/deploy.<env>.env` est désormais l'UNIQUE source, il n'y a plus rien à
# recouper.
if ! PUBLIC_DOMAIN="$(valider_domaine_public "${PUBLIC_DOMAIN:-}")"; then
    echo "   Corriger PUBLIC_DOMAIN dans $ENV_FILE."
    exit 2
fi
R_PUBLIC_DOMAIN="$PUBLIC_DOMAIN"

PUBLIC_BASE=""
[ -n "$PUBLIC_DOMAIN" ] && PUBLIC_BASE="https://${PUBLIC_DOMAIN}"

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/clef-images"
TAG="$(date -u +%Y%m%d-%H%M%S)"

echo "🚀 CLEF — déploiement « $ENVIRONMENT »"
echo "    projet     : $PROJECT_ID"
echo "    région     : $REGION"
echo "    composants : $COMPONENTS"
echo "    tag        : $TAG"
echo ""

# ---------------------------------------------------------------------------
# Préflight
# ---------------------------------------------------------------------------
# Chaque contrôle échoue en nommant ce qui manque. Sans cela, un prérequis absent se
# manifeste par une révision Cloud Run en échec, à trois niveaux de distance de sa
# cause.
echo "🔎 Préflight..."
FAILED=false

# envsubst (paquet gettext) rend le descripteur du service. Absent de macOS par
# défaut — donc de l hôte documenté. Sans ce contrôle, l échec survient APRÈS la
# construction et la poussée des deux images, ce qui contredit la promesse du
# préflight : refuser avant d agir.
if ! command -v envsubst >/dev/null 2>&1; then
    echo "❌ envsubst introuvable (paquet gettext)."
    echo "   Il rend deploy/cloudrun-api.yaml.tpl ; sans lui le déploiement du"
    echo "   backend est impossible."
    echo "   macOS   : brew install gettext && brew link --force gettext"
    echo "   Debian  : sudo apt-get install gettext-base"
    exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
    echo "❌ 'gcloud' introuvable. Ce script se lance depuis l'HÔTE, pas depuis la VM."
    exit 1
fi

ACCOUNT=$(gcloud config get-value account 2>/dev/null || true)
if [ -z "$ACCOUNT" ] || [ "$ACCOUNT" = "(unset)" ]; then
    echo "❌ Non authentifié. Lancer : gcloud auth login"
    exit 1
fi
echo "  ✅ authentifié : $ACCOUNT"

# ⚠️ Distinguer « la ressource est absente » de « le contrôle n a pas pu conclure ».
#
# Les contrôles ci-dessous étaient écrits « if gcloud … >/dev/null 2>&1 », ce qui
# range TOUTE erreur dans « absent » : jeton expiré, droit manquant, API désactivée,
# mauvais projet. Le script a ainsi affiché trois « absent — lancer ./00-infra.sh »
# sur des ressources parfaitement existantes, et le conseil était non seulement
# inutile mais trompeur. Un diagnostic qui invente une cause est pire que pas de
# diagnostic.
#
# `gcloud config get-value account` ne fait aucun appel réseau : l authentification
# peut donc paraître bonne alors que tout appel à l API échoue.
#
# Codes : 0 = présente, 1 = absente, 2 = indéterminé (l erreur réelle est affichée).
verifier_existence() {
    local libelle="$1"; shift
    local sortie
    if sortie=$("$@" 2>&1); then
        return 0
    fi
    if printf '%s' "$sortie" | grep -qiE 'NOT_FOUND|not found|does not exist|404'; then
        return 1
    fi
    echo "⚠️  Contrôle « $libelle » NON CONCLUANT — ce n est pas une absence."
    printf '%s\n' "$sortie" | head -4 | sed 's/^/      /'
    echo "      Si le message parle de jeton ou de réauthentification :"
    echo "        gcloud auth login && gcloud auth application-default login"
    return 2
}

# ⚠️ maxScale > 1 donnerait un Redis par instance, donc des jeux de données divergents
# sans aucun signal. C'est la contrainte structurelle du sidecar (ADR 0008).
if [ "$MAX_INSTANCES" != "1" ]; then
    echo "❌ MAX_INSTANCES=$MAX_INSTANCES — refusé."
    echo "   Redis vit en sidecar : chaque instance aurait sa propre base, et les"
    echo "   données divergeraient silencieusement. Tant que Redis est là, c'est 1."
    FAILED=true
fi

SERVICE_ACCOUNT="clef-backend@${PROJECT_ID}.iam.gserviceaccount.com"
verifier_existence "service account" \
    gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID"
case $? in
    0) echo "  ✅ service account : $SERVICE_ACCOUNT" ;;
    1) echo "❌ Service account $SERVICE_ACCOUNT absent — lancer ./00-infra.sh $ENVIRONMENT"
       FAILED=true ;;
    *) FAILED=true ;;
esac

SNAPSHOTS_BUCKET="${PROJECT_ID}-clef-redis-snapshots"
verifier_existence "bucket d instantanés" \
    gcloud storage buckets describe "gs://$SNAPSHOTS_BUCKET" --project="$PROJECT_ID"
case $? in
    0) echo "  ✅ bucket d'instantanés : gs://$SNAPSHOTS_BUCKET" ;;
    1) echo "❌ Bucket gs://$SNAPSHOTS_BUCKET absent — lancer ./00-infra.sh $ENVIRONMENT"
       echo "   Sans lui, Redis perdrait toutes les données à chaque redémarrage."
       FAILED=true ;;
    *) FAILED=true ;;
esac

# ⚠️ Constat M12 : la CI et DEPLOYMENT.md déploient en europe-west1, alors que KMS et
# le reste de l'infra sont en europe-west9. Un service portant le même nom dans une
# autre région passerait inaperçu, et ce script en créerait un doublon — deux services
# vivants, deux URLs, et des utilisateurs répartis entre les deux sans le savoir.
for svc in "$SERVICE_NAME" "$FRONTEND_SERVICE"; do
    OTHER=$(gcloud run services list --project="$PROJECT_ID" \
              --filter="metadata.name=$svc" \
              --format='value(metadata.labels."cloud.googleapis.com/location")' 2>/dev/null \
            | grep -v "^${REGION}$" || true)
    if [ -n "$OTHER" ]; then
        echo "❌ Le service '$svc' existe déjà dans une autre région : $(echo "$OTHER" | tr '\n' ' ')"
        echo "   Déployer en $REGION créerait un DOUBLON : deux services vivants, deux URLs."
        echo "   Choisir : soit supprimer l'ancien, soit aligner REGION dans $ENV_FILE."
        echo "   gcloud run services delete $svc --region=<ancienne> --project=$PROJECT_ID"
        FAILED=true
    fi
done

verifier_existence "registre d images" \
    gcloud artifacts repositories describe clef-images \
    --location="$REGION" --project="$PROJECT_ID"
case $? in
    0) echo "  ✅ registre d'images" ;;
    1) echo "❌ Registre clef-images absent — lancer ./00-infra.sh $ENVIRONMENT"
       FAILED=true ;;
    *) FAILED=true ;;
esac

# Un secret sans version fait échouer le démarrage du conteneur, pas le déploiement :
# la révision serait créée puis mourrait, avec un message peu parlant.
#
# ⚠️ Et une version PRÉSENTE ne dit rien de son CONTENU. Ce contrôle ne comptait que
# les versions, et deux valeurs fausses ont chacune coûté un cycle complet de
# déploiement le 2026-08-28 :
#
#   1. « ton-client-id.apps.googleusercontent.com » — la commande de DEPLOYMENT.md
#      lancée telle quelle, sans substituer la vraie valeur ;
#   2. « CLEF-rcq-fr-dev-client_secret_1022015855967-2irg….apps.googleusercontent.com »
#      — le NOM DU FICHIER de credentials téléchargé, collé au lieu du champ
#      `.web.client_id` qu'il contient.
#
# Les deux finissent par `.apps.googleusercontent.com` : vérifier le suffixe n'aurait
# rien attrapé. Un identifiant Google a une STRUCTURE — `<numéro de projet>-<empreinte
# minuscule>.apps.googleusercontent.com` — et c'est elle qui distingue les trois cas.
# Le symptôme, sinon, est un « Error 401: invalid_client » côté Google, à deux
# redéploiements de sa cause.
PLACEHOLDERS='(^|[^a-z])(ton|votre|your|mon|my)-|changeme|change-me|placeholder|a-remplir|remplacer|xxxxx|todo|<|>'

# Lit une valeur de secret. Ne l'affiche jamais, ne l'écrit jamais sur disque. Rend 1
# si la LECTURE a échoué — droit manquant, réseau — cas qu'il faut distinguer d'une
# valeur fausse.
#
# ⚠️ La sentinelle « S » n'est pas une coquetterie. Une substitution de commande
# `$(...)` SUPPRIME les retours ligne finaux : écrite naïvement, cette fonction ne
# pouvait pas voir un `\n` en fin de secret — le défaut le plus courant, `echo` au
# lieu de `printf '%s'`, et celui que le contrôle ci-dessous cherche. Vérifié en
# exécution avant correction : la valeur passait le contrôle. La sentinelle et le code
# de sortie sont collés après la valeur, puis retirés autour du DERNIER « S ».
VALEUR_SECRET=""
lire_secret() {
    local brut code
    brut=$(gcloud secrets versions access latest --secret="$1" \
        --project="$PROJECT_ID" 2>/dev/null; printf 'S%s' "$?")
    code="${brut##*S}"
    VALEUR_SECRET="${brut%S*}"
    [ "$code" = "0" ] || return 1
    return 0
}

for secret in CLEF_GOOGLE_CLIENT_ID CLEF_GOOGLE_CLIENT_SECRET CLEF_QR_CODE_SALT; do
    COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" \
              --filter="state=enabled" --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" = "0" ]; then
        echo "❌ Secret $secret sans version active."
        echo "   printf '%s' 'VALEUR' | gcloud secrets versions add $secret --data-file=- --project=$PROJECT_ID"
        FAILED=true
        continue
    fi

    if ! lire_secret "$secret"; then
        echo "  ⚠️  $secret : version présente, valeur ILLISIBLE depuis ce compte"
        echo "     (droit secretmanager.versions.access manquant ?) — contrôle de"
        echo "     forme non concluant, ce n'est PAS une valeur fausse."
        continue
    fi

    # Un caractère blanc est toujours une erreur de copie : `echo` au lieu de
    # `printf` ajoute un \n, invisible dans la console, fatal côté Google.
    case "$VALEUR_SECRET" in
        *[[:space:]]*)
            echo "❌ $secret contient un caractère blanc (espace ou retour ligne)."
            echo "   Cause quasi certaine : \`echo\` au lieu de \`printf '%s'\`."
            FAILED=true
            continue ;;
    esac

    if printf '%s' "$VALEUR_SECRET" | tr '[:upper:]' '[:lower:]' | grep -Eq "$PLACEHOLDERS"; then
        echo "❌ $secret ressemble à une valeur BOUCHON, pas à un vrai secret."
        echo "   Remplacer par la valeur réelle (voir DEPLOYMENT.md § « Renseigner les 3 secrets »)."
        FAILED=true
        continue
    fi

    case "$secret" in
        CLEF_GOOGLE_CLIENT_ID)
            # <numéro de projet>-<empreinte>.apps.googleusercontent.com
            if ! printf '%s' "$VALEUR_SECRET" \
                | grep -Eq '^[0-9]+(-[a-z0-9]+)?\.apps\.googleusercontent\.com$'; then
                echo "❌ CLEF_GOOGLE_CLIENT_ID n'a pas la forme d'un identifiant Google :"
                echo "     $VALEUR_SECRET"
                echo "   Attendu : <numéro-de-projet>-<empreinte>.apps.googleusercontent.com"
                echo "   Il est dans le fichier de credentials téléchargé, PAS dans son nom :"
                printf '     %s\n' \
                    "jq -r .web.client_id <fichier>.json | tr -d '\\n' \\" \
                    "  | gcloud secrets versions add CLEF_GOOGLE_CLIENT_ID --data-file=- --project=$PROJECT_ID"
                FAILED=true
            fi ;;
        CLEF_GOOGLE_CLIENT_SECRET)
            # Les clients récents donnent « GOCSPX-… ». Les anciens non : on avertit,
            # on ne refuse pas — un refus à tort bloquerait un déploiement légitime.
            case "$VALEUR_SECRET" in
                GOCSPX-*) ;;
                *) echo "  ⚠️  CLEF_GOOGLE_CLIENT_SECRET ne commence pas par « GOCSPX- »."
                   echo "     Forme inhabituelle pour un client récent — à vérifier, sans blocage." ;;
            esac ;;
        CLEF_QR_CODE_SALT)
            LONGUEUR=${#VALEUR_SECRET}
            if [ "$LONGUEUR" -lt 16 ]; then
                # qr_code_service.py:17 refuse en dessous : le conteneur répondrait 500
                # sur toute génération de QR code.
                echo "❌ CLEF_QR_CODE_SALT fait $LONGUEUR caractères ; le code en exige 16 au moins."
                FAILED=true
            elif [ "$LONGUEUR" -lt 32 ]; then
                echo "  ⚠️  CLEF_QR_CODE_SALT ne fait que $LONGUEUR caractères."
                echo "     Les jetons des QR codes COLLÉS sur les véhicules en dépendent, et"
                echo "     le sel ne peut plus changer une fois imprimés : viser 32+."
            fi ;;
    esac
done
VALEUR_SECRET=""
[ "$FAILED" = false ] && echo "  ✅ secrets renseignés (présence ET forme)"

# ⚠️ Aucun contrôle sur les trois `*_SPREADSHEET_ID` : retiré le 2026-08-29.
#
# Le préflight signalait leur absence par trois lignes `ℹ️`. C'était du bruit à chaque
# déploiement pour une non-information : le référentiel arrive dans Redis par Apps
# Script, et `sheets_real.py` ne pourrait de toute façon pas lire ces classeurs — le
# domaine @croix-rouge.fr interdit tout partage vers une adresse
# `.gserviceaccount.com`. Les renseigner ne débloque rien.
#
# Un préflight doit refuser ou se taire. Trois lignes qui disent « ceci est sans
# effet » entraînent à survoler sa sortie, et c'est la sortie où doivent ressortir les
# refus. Le fond du sujet est documenté là où on le cherche :
# `deploy/deploy.env.example` et le constat N13 de `docs/TODO.md`.

if [ "$FAILED" = true ]; then
    echo ""
    R_PREFLIGHT="échec"
    echo "🛑 Rien n'a été déployé. Corriger les points ci-dessus."
    exit 1
fi
R_PREFLIGHT="complet"
R_STEP="construction des images"
echo "  ✅ préflight complet"
echo ""

# ---------------------------------------------------------------------------
# Construction des images
# ---------------------------------------------------------------------------
BACKEND_IMAGE="${REGISTRY}/clef-api:${TAG}"
FRONTEND_IMAGE="${REGISTRY}/clef-frontend:${TAG}"
R_BACKEND_IMAGE="$BACKEND_IMAGE"
R_FRONTEND_IMAGE="$FRONTEND_IMAGE"

# ⚠️ `--default-buckets-behavior=regional-user-owned-bucket` n'est pas optionnel ici.
#
# `--region` place le BUILD dans la région ; il ne dit rien du bucket de staging où
# gcloud dépose l'archive des sources. Par défaut, Cloud Build en crée un en
# multi-région **US** (`gs://<projet>_cloudbuild`), et la policy d'organisation
# `constraints/gcp.resourceLocations` le refuse :
#
#     ERROR: (gcloud.builds.submit) HTTPError 412:
#            'us' violates constraint 'constraints/gcp.resourceLocations'
#
# Le message parle de « us » sans jamais nommer le bucket : rien n'y mène.
#
# Ce drapeau fait créer et gérer un bucket régional par Cloud Build lui-même, dans la
# région du build — ce qui évite aussi d'avoir à lui accorder des droits à la main sur
# un bucket qu'on aurait provisionné soi-même.
#
# Même famille de piège que la réplication `auto` des secrets : `global` et `us` ne
# sont pas des emplacements disponibles sur ce projet, et les valeurs par défaut de
# GCP y vont d'elles-mêmes.
BUILD_FLAGS=(
    --project="$PROJECT_ID"
    --region="$REGION"
    --default-buckets-behavior=regional-user-owned-bucket
)

if [ "$SKIP_BUILD" = false ]; then
    if [[ "$COMPONENTS" == *api* ]]; then
        echo "🔨 Image backend (Cloud Build, $REGION)..."
        gcloud builds submit backend --tag="$BACKEND_IMAGE" "${BUILD_FLAGS[@]}"
        echo ""
    fi
    if [[ "$COMPONENTS" == *frontend* ]]; then
        echo "🔨 Image frontend (Cloud Build, $REGION)..."
        gcloud builds submit frontend --tag="$FRONTEND_IMAGE" "${BUILD_FLAGS[@]}"
        echo ""
    fi
else
    echo "⏭️  Construction ignorée : réutilisation de la dernière image poussée."

    # ⚠️ Deux défauts corrigés ici.
    #
    # 1. Le format était "value(package)@value(version)" : gcloud refuse du texte
    #    littéral hors projection. L affectation sortait vide, stderr était jeté, et
    #    le script s arrêtait TOUJOURS sur « Aucune image à réutiliser » —
    #    --skip-build ne fonctionnait donc jamais.
    # 2. Seule l image backend était résolue. FRONTEND_IMAGE gardait un tag
    #    horodaté du jour, jamais poussé : le déploiement du frontend échouait sur
    #    « image not found », APRÈS que le service api ait déjà été remplacé.
    derniere_image() {
        gcloud artifacts docker images list "$1" \
            --project="$PROJECT_ID" --sort-by=~UPDATE_TIME --limit=1 \
            --format='value(format("{0}@{1}",package,version))' 2>/dev/null | head -1
    }

    if [[ "$COMPONENTS" == *api* ]]; then
        BACKEND_IMAGE=$(derniere_image "${REGISTRY}/clef-api")
        [ -n "$BACKEND_IMAGE" ] || {
            echo "❌ Aucune image backend dans ${REGISTRY}/clef-api."
            echo "   Relancer sans --skip-build."; exit 1; }
        echo "    backend  : $BACKEND_IMAGE"
    fi
    if [[ "$COMPONENTS" == *frontend* ]]; then
        FRONTEND_IMAGE=$(derniere_image "${REGISTRY}/clef-frontend")
        [ -n "$FRONTEND_IMAGE" ] || {
            echo "❌ Aucune image frontend dans ${REGISTRY}/clef-frontend."
            echo "   Relancer sans --skip-build."; exit 1; }
        echo "    frontend : $FRONTEND_IMAGE"
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Déploiement du backend, avec Redis en sidecar
# ---------------------------------------------------------------------------
# `gcloud run deploy` ne sait décrire ni plusieurs conteneurs ni un volume GCS : on
# passe donc par un descripteur de service complet.
if [[ "$COMPONENTS" == *api* ]]; then
    echo "☁️  Déploiement du backend (2 conteneurs : backend + redis)..."

    # Le service a besoin de sa propre URL : c'est elle qui forme l'URI de
    # redirection OAuth. Elle n'existe pas avant la première création — d'où la
    # seconde passe plus bas.
    service_url() {
        gcloud run services describe "$1" \
            --region="$REGION" --project="$PROJECT_ID" \
            --format='value(status.url)' 2>/dev/null || true
    }

    # Rend le descripteur puis l'applique. Appelé une fois, ou deux à la création.
    #
    # ⚠️ Les noms des variables d'environnement doivent être ceux que le code lit :
    # `CORS_ORIGINS` (app/main.py) et `GOOGLE_REDIRECT_URI` (app/auth/config.py).
    # Une variable bien remplie sous un autre nom laisse le défaut de développement
    # en place, sans aucune erreur — CORS bloque alors le frontend, et Google
    # renvoie les utilisateurs vers localhost.
    deploy_api() {
        local backend_url="$1" frontend_url="$2"
        local rendered
        rendered=$(mktemp)

        # CORS ne sert plus qu'à l'accès direct au backend : le LB, ou à défaut le
        # relais nginx, met le parcours normal en même origine.
        local cors="${backend_url:-http://localhost:8000}"
        [ -n "$frontend_url" ] && cors="${frontend_url},${cors}"
        [ -n "$PUBLIC_BASE" ] && cors="${PUBLIC_BASE},${cors}"

        # ⚠️ Ces trois-là visent le FRONTEND, pas le backend.
        #
        #   ALLOWED_FRONTEND_URLS  destinations autorisées après connexion ;
        #   FRONTEND_URL           liens d'approbation de devis dans les courriels ;
        #   DOMAIN                 hôte encodé dans les QR codes IMPRIMÉS.
        #
        # Au premier déploiement le frontend n'existe pas encore : on retombe sur
        # l'URL du backend, qui sert la même origine via son propre proxy, et la
        # seconde passe corrige dès que le frontend est là. Un repli sur localhost
        # serait pire : DOMAIN finirait imprimé sur des autocollants.
        # ⚠️ Le domaine public PRIME sur les URL run.app dès qu'il est configuré.
        #
        # C'est lui que le navigateur voit, donc lui qui doit servir de destination
        # après connexion (ALLOWED_FRONTEND_URLS), de base aux liens d'approbation
        # envoyés aux garages (FRONTEND_URL), et d'hôte encodé dans les QR codes
        # (DOMAIN). Laisser une URL run.app ici produirait des liens et des
        # autocollants qui cesseront de fonctionner le jour du verrouillage de
        # l'ingress.
        local front="${PUBLIC_BASE:-${frontend_url:-$backend_url}}"
        local domain="${front#https://}"
        domain="${domain#http://}"

        # ⚠️ ALLOWED_FRONTEND_URLS est une LISTE séparée par des virgules — les trois
        # autres sont des valeurs simples.
        #
        # `validate_redirect_url` (app/auth/config.py) la découpe et refuse toute
        # destination absente. Réduite à `front`, l'origine *.run.app disparaissait dès
        # qu'un domaine public existait, alors que ce service reste publiquement
        # invocable et présent dans CORS_ORIGINS : une connexion entamée depuis cette
        # URL repartait en « 400 Invalid redirect URL ». Le domaine public reste en
        # TÊTE — c'est la destination par défaut.
        local front_allowed="$front" origine
        for origine in "$frontend_url" "$backend_url"; do
            [ -n "$origine" ] || continue
            case ",${front_allowed}," in
                *",${origine},"*) continue ;;
            esac
            front_allowed="${front_allowed},${origine}"
        done

        SERVICE_NAME="$SERVICE_NAME" ENVIRONMENT="$ENVIRONMENT" \
        MAX_INSTANCES="$MAX_INSTANCES" MIN_INSTANCES="$MIN_INSTANCES" \
        SERVICE_ACCOUNT="$SERVICE_ACCOUNT" BACKEND_IMAGE="$BACKEND_IMAGE" \
        PROJECT_ID="$PROJECT_ID" EMAIL_GESTIONNAIRE_DT="$EMAIL_GESTIONNAIRE_DT" \
        CORS_ORIGINS="$cors" \
        ALLOWED_FRONTEND_URLS="${front_allowed}" \
        FRONTEND_URL="$front" \
        DOMAIN="$domain" \
        BACKEND_URL="$backend_url" \
        GOOGLE_REDIRECT_URI="${front:+${front}/auth/callback}" \
        DT_OAUTH_REDIRECT_URI="${front:+${front}/auth/callback-dt}" \
        VEHICULES_SPREADSHEET_ID="${VEHICULES_SPREADSHEET_ID:-}" \
        BENEVOLES_SPREADSHEET_ID="${BENEVOLES_SPREADSHEET_ID:-}" \
        RESPONSABLES_SPREADSHEET_ID="${RESPONSABLES_SPREADSHEET_ID:-}" \
        REDIS_MEMORY="$REDIS_MEMORY" REDIS_MAXMEMORY="$REDIS_MAXMEMORY" \
        SNAPSHOTS_BUCKET="$SNAPSHOTS_BUCKET" \
            envsubst < "$TEMPLATE" > "$rendered"

        # ⚠️ RÉESSAIS — le montage du volume GCS est une dépendance de démarrage, et
        # il échoue par intermittence.
        #
        # `GetStorageLayout … rpc error: code = Unimplemented` : gcsfuse interroge un
        # appel de plan de contrôle qui sert à détecter un espace de noms hiérarchique
        # — que ce bucket n'a pas. La documentation gcsfuse est explicite : ce contrôle
        # est intégral et NE PEUT PAS être désactivé. Aucune option de montage à
        # ajouter, donc.
        #
        # Trois échecs constatés le 2026-08-28/29 (un réveil, deux déploiements) pour
        # un succès. Et `minScale = 1` aggrave la visibilité du problème plutôt que le
        # problème : avec une instance minimale, la révision n'est PRÊTE qu'une fois un
        # démarrage réussi — donc un montage raté fait échouer le déploiement entier,
        # là où `minScale = 0` le laissait passer et échouait plus tard, à la première
        # requête.
        #
        # Réessayer est la seule réponse disponible tant que le montage n'est pas sorti
        # du chemin de démarrage.
        local essai
        for essai in 1 2 3; do
            if gcloud run services replace "$rendered" \
                --region="$REGION" --project="$PROJECT_ID"; then
                break
            fi
            if [ "$essai" -eq 3 ]; then
                rm -f "$rendered"
                echo "❌ Trois tentatives de déploiement en échec."
                echo "   Cause la plus probable : le montage du volume GCS d'instantanés."
                echo "   Vérifier avec : ./02-logs.sh $ENVIRONMENT --what=run"
                echo "   puis chercher « mount operation failed » dans le journal"
                echo "   d'infrastructure de la dernière révision."
                exit 1
            fi
            echo ""
            echo "  ↻ tentative $essai en échec — nouvelle tentative dans 20 s."
            echo "     (montage du volume GCS : échec intermittent connu)"
            sleep 20
        done
        rm -f "$rendered"

        # Tracé dans le rapport : c'est le nombre de passes et l'URI final qui
        # expliquent, après coup, pourquoi la connexion marche ou non.
        R_PASSES=$((R_PASSES + 1))
        R_REDIRECT_URI="${front:+${front}/auth/callback}"
    }

    BACKEND_URL=$(service_url "$SERVICE_NAME")
    FRONTEND_URL=$(service_url "$FRONTEND_SERVICE")
    FIRST_CREATION=false
    [ -z "$BACKEND_URL" ] && FIRST_CREATION=true

    # ⚠️ Renseigner l'étape AVANT d'agir, pas après.
    #
    # Le rapport du 2026-08-28 annonçait « derniereEtape: construction des images »
    # alors que l'échec venait de `services replace` — la sonde de démarrage de la
    # révision. Un rapport qui nomme la mauvaise étape envoie chercher la cause au
    # mauvais endroit, ce qui est pire que de ne rien nommer.
    R_STEP="déploiement du backend (services replace)"

    deploy_api "$BACKEND_URL" "$FRONTEND_URL"

    gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" \
        --member=allUsers --role=roles/run.invoker >/dev/null

    # Seconde passe : à la création, l'URL n'existait pas au premier rendu, donc
    # GOOGLE_REDIRECT_URI est parti vide. Le service tournerait, et la connexion
    # échouerait — le genre de panne qu'on ne relie pas au déploiement.
    if [ "$FIRST_CREATION" = true ]; then
        BACKEND_URL=$(service_url "$SERVICE_NAME")
        if [ -n "$BACKEND_URL" ]; then
            echo "  ↻ première création : redéploiement avec l'URL du service"
            echo "     ($BACKEND_URL) pour la redirection OAuth"
            deploy_api "$BACKEND_URL" "$FRONTEND_URL"
        fi
    fi

    R_STEP="backend déployé"
    echo "  ✅ backend déployé"
    echo ""
    # ⚠️ Afficher l'URI RÉELLEMENT déployé, jamais une recomposition.
    #
    # Ce message donnait « ${BACKEND_URL}/auth/callback » alors que deploy_api envoie
    # « ${PUBLIC_BASE}/auth/callback » dès qu'un domaine est configuré. L'opérateur
    # enregistrait donc l'URI *.run.app, l'application en annonçait un autre, et
    # TOUTE connexion échouait en redirect_uri_mismatch.
    if [ -n "$R_REDIRECT_URI" ]; then
        echo "  📌 À déclarer sur le client OAuth de la console GCP :"
        echo "     origine JavaScript : ${R_REDIRECT_URI%/auth/callback}"
        echo "     URI de redirection : $R_REDIRECT_URI"
        # Le second flux — délégation Calendar/Drive/Gmail d'un gestionnaire DT — a
        # son propre URI. Oublié en console, l'écran dt-admin échoue en
        # redirect_uri_mismatch, et RIEN d'autre ne le signale.
        echo "     URI de redirection : ${R_REDIRECT_URI%/auth/callback}/auth/callback-dt"
        echo "                          (délégation DT — les DEUX sont nécessaires)"
    else
        echo "  ⚠️  Aucune URL connue : URI de redirection OAuth vide, la connexion"
        echo "     échouera. Relancer une fois le service créé."
    fi
    echo ""
fi

if [[ "$COMPONENTS" == *frontend* ]]; then
    echo "☁️  Déploiement du frontend..."
    R_STEP="déploiement du frontend"
    # nginx relaie /api et /auth vers le backend : il lui faut son NOM D'HÔTE, sans
    # schéma (le gabarit fait « proxy_pass https://${BACKEND_HOST} » et s'en sert
    # aussi comme en-tête Host, ce qu'exige le routage de Cloud Run).
    API_URL=$(service_url "$SERVICE_NAME")
    if [ -z "$API_URL" ]; then
        echo "❌ Le service $SERVICE_NAME n'existe pas : le frontend n'aurait aucune"
        echo "   route vers l'API. Déployer d'abord avec --components=api."
        exit 1
    fi
    BACKEND_HOST="${API_URL#https://}"

    gcloud run deploy "$FRONTEND_SERVICE" \
        --image="$FRONTEND_IMAGE" \
        --region="$REGION" --project="$PROJECT_ID" \
        --platform=managed --allow-unauthenticated \
        --port=80 --memory=256Mi --cpu=1 \
        --min-instances=0 --max-instances=5 \
        --set-env-vars="BACKEND_ORIGIN=${API_URL},BACKEND_HOST=${BACKEND_HOST}"
    R_STEP="frontend déployé"
    echo "  ✅ frontend déployé"

    # Le frontend vient peut-être d'être créé : son origine doit entrer dans
    # CORS_ORIGINS du backend, sinon le navigateur bloque tous ses appels.
    NEW_FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" \
        --region="$REGION" --project="$PROJECT_ID" \
        --format='value(status.url)' 2>/dev/null || true)
    if [[ "$COMPONENTS" == *api* ]] && [ -n "$NEW_FRONTEND_URL" ] \
       && [ "$NEW_FRONTEND_URL" != "${FRONTEND_URL:-}" ]; then
        echo "  ↻ origine du frontend nouvelle : mise à jour de CORS_ORIGINS"
        deploy_api "$(service_url "$SERVICE_NAME")" "$NEW_FRONTEND_URL"
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Vérification
# ---------------------------------------------------------------------------
echo "🔬 Vérification..."
BACKEND_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)' 2>/dev/null || true)
FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" \
    --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)' 2>/dev/null || true)

if [ -n "$BACKEND_URL" ]; then
    HEALTH=$(curl -fsS --max-time 30 "${BACKEND_URL}/health" 2>/dev/null || echo "INJOIGNABLE")
    R_HEALTH="$HEALTH"
    echo "  /health → $HEALTH"
    case "$HEALTH" in
        *'"redis":"connected"'*)
            echo "  ✅ le sidecar Redis répond" ;;
        *'"redis":"disconnected"'*)
            echo "  ❌ Redis injoignable depuis le backend."
            echo "     Vérifier les logs du conteneur 'redis' : le montage GCS a pu échouer."
            echo "     gcloud run services logs read $SERVICE_NAME --region=$REGION --project=$PROJECT_ID" ;;
        *)  echo "  ⚠️  réponse inattendue — voir les logs." ;;
    esac
fi

# ⚠️ Quand un domaine est configuré, c'est LUI qu'il faut éprouver.
#
# Cette étape ne sondait que ${BACKEND_URL}/health, l'URL *.run.app — celle que
# personne n'utilise dès qu'il y a un domaine. Un certificat encore en
# FAILED_NOT_VISIBLE, un enregistrement A absent ou un NEG visant le mauvais service
# passaient donc inaperçus, et le script concluait « ✅ Déploiement terminé ».
#
# Les trois sondes couvrent les trois chemins distincts du load balancer :
#   /health    → service par DÉFAUT (nginx, frontend) ;
#   /api/test  → règle de chemin /api/* (NEG de l'API) ;
#   http://    → l'url map de redirection, sur le port 80.
PUB_FAIL=false
if [ -n "$PUBLIC_BASE" ]; then
    echo ""
    echo "  🌐 Domaine public : $PUBLIC_DOMAIN"

    if PUB_HEALTH=$(curl -fsS --max-time 30 "${PUBLIC_BASE}/health" 2>/dev/null); then
        echo "  ✅ ${PUBLIC_BASE}/health → $(printf '%s' "$PUB_HEALTH" | head -1)"
    else
        PUB_FAIL=true
        echo "  ❌ ${PUBLIC_BASE}/health injoignable (frontend, service par défaut)"
    fi

    if curl -fsS --max-time 30 "${PUBLIC_BASE}/api/test" >/dev/null 2>&1; then
        echo "  ✅ ${PUBLIC_BASE}/api/test → l'API répond à travers le load balancer"
    else
        PUB_FAIL=true
        echo "  ❌ ${PUBLIC_BASE}/api/test : la règle /api/* n'atteint pas l'API"
    fi

    # Sans -L : c'est la redirection elle-même qu'on mesure, pas sa cible. Le chemin
    # doit être conservé — les QR codes et les courriels en portent un.
    PUB_REDIR=$(curl -s -o /dev/null --max-time 30 -w '%{http_code} %{redirect_url}' \
        "http://${PUBLIC_DOMAIN}/form/" 2>/dev/null || printf '000 ')
    PUB_CODE="${PUB_REDIR%% *}"
    PUB_CIBLE="${PUB_REDIR#* }"

    # ⚠️ GCP renvoie le PORT EXPLICITE dans la redirection :
    #
    #     Location: https://clef.paquerette.com:443/form/
    #
    # Ma première version comparait à l'URL sans port et concluait « redirige, mais
    # pas où il faut » sur une redirection parfaitement correcte — constaté au premier
    # déploiement réel, le 2026-08-28. Un contrôle trop strict qui crie au loup vaut
    # à peine mieux qu'un contrôle absent : on apprend à ignorer sa sortie.
    PUB_CIBLE_NORM=$(printf '%s' "$PUB_CIBLE" | sed 's|:443/|/|')

    if [ "$PUB_CODE" = "301" ] && [ "$PUB_CIBLE_NORM" = "https://${PUBLIC_DOMAIN}/form/" ]; then
        echo "  ✅ http:// → 301 vers https, chemin conservé"
    elif [ "$PUB_CODE" = "301" ]; then
        PUB_FAIL=true
        echo "  ❌ http:// redirige, mais pas où il faut : $PUB_CIBLE"
        echo "     attendu : https://${PUBLIC_DOMAIN}/form/ (le port :443 est toléré)"
    else
        PUB_FAIL=true
        echo "  ❌ http:// ne redirige pas en 301 (réponse : $PUB_REDIR)"
    fi

    if [ "$PUB_FAIL" = true ]; then
        R_PUBLIC_VERIF="incomplet"
        echo ""
        echo "  ⚠️  Le domaine public ne répond pas complètement. Causes usuelles :"
        echo "     • certificat pas encore ACTIVE — le DNS d'abord, puis 15 min à 24 h ;"
        echo "     • enregistrement A absent, ou pointant ailleurs que l'IP du LB ;"
        echo "     • ./00-infra.sh $ENVIRONMENT pas passé avec public_domain renseigné."
        echo "     gcloud compute ssl-certificates list --global --project=$PROJECT_ID"
        echo "     tofu -chdir=deploy/terraform output dns_a_creer"
    else
        R_PUBLIC_VERIF="ok"
    fi
fi
echo ""

R_STEP="terminé"
R_BACKEND_URL="$BACKEND_URL"
R_FRONTEND_URL="$FRONTEND_URL"
if [ "$PUB_FAIL" = true ]; then
    echo "⚠️  Déploiement « $ENVIRONMENT » terminé, mais le domaine public ne répond"
    echo "    pas complètement — voir juste au-dessus. Les services eux-mêmes sont à jour."
else
    echo "✅ Déploiement « $ENVIRONMENT » terminé."
fi
echo ""
echo "📍 URLs :"
[ -n "$PUBLIC_BASE" ]  && echo "   public   : $PUBLIC_BASE"
[ -n "$BACKEND_URL" ]  && echo "   backend  : $BACKEND_URL"
[ -n "$FRONTEND_URL" ] && echo "   frontend : $FRONTEND_URL"
echo ""
echo "📌 Au premier déploiement :"
echo "   • Seul $EMAIL_GESTIONNAIRE_DT peut se connecter — ce chemin ne consulte pas"
echo "     le référentiel. Tous les autres comptes attendent la synchronisation."
echo "   • Créer une clé API de délégation dans l'écran de configuration, puis la"
echo "     renseigner dans les propriétés du script « CLEF Benevoles »."
echo "   • Vérifier après 10 min que l'instantané est écrit :"
echo "     gcloud storage ls -l gs://$SNAPSHOTS_BUCKET/"
