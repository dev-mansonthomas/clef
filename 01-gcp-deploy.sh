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

: "${PROJECT_ID:?PROJECT_ID manquant dans $ENV_FILE}"
: "${REGION:?REGION manquant dans $ENV_FILE}"
: "${EMAIL_GESTIONNAIRE_DT:?EMAIL_GESTIONNAIRE_DT manquant dans $ENV_FILE}"

SERVICE_NAME="${SERVICE_NAME:-clef-api}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-clef-frontend}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
REDIS_MEMORY="${REDIS_MEMORY:-512Mi}"
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

# ⚠️ maxScale > 1 donnerait un Redis par instance, donc des jeux de données divergents
# sans aucun signal. C'est la contrainte structurelle du sidecar (ADR 0008).
if [ "$MAX_INSTANCES" != "1" ]; then
    echo "❌ MAX_INSTANCES=$MAX_INSTANCES — refusé."
    echo "   Redis vit en sidecar : chaque instance aurait sa propre base, et les"
    echo "   données divergeraient silencieusement. Tant que Redis est là, c'est 1."
    FAILED=true
fi

SERVICE_ACCOUNT="clef-backend@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "  ✅ service account : $SERVICE_ACCOUNT"
else
    echo "❌ Service account $SERVICE_ACCOUNT absent — lancer ./00-infra.sh $ENVIRONMENT"
    FAILED=true
fi

SNAPSHOTS_BUCKET="${PROJECT_ID}-clef-redis-snapshots"
if gcloud storage buckets describe "gs://$SNAPSHOTS_BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "  ✅ bucket d'instantanés : gs://$SNAPSHOTS_BUCKET"
else
    echo "❌ Bucket gs://$SNAPSHOTS_BUCKET absent — lancer ./00-infra.sh $ENVIRONMENT"
    echo "   Sans lui, Redis perdrait toutes les données à chaque redémarrage."
    FAILED=true
fi

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

if gcloud artifacts repositories describe clef-images \
     --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "  ✅ registre d'images"
else
    echo "❌ Registre clef-images absent — lancer ./00-infra.sh $ENVIRONMENT"
    FAILED=true
fi

# Un secret sans version fait échouer le démarrage du conteneur, pas le déploiement :
# la révision serait créée puis mourrait, avec un message peu parlant.
for secret in CLEF_GOOGLE_CLIENT_ID CLEF_GOOGLE_CLIENT_SECRET CLEF_QR_CODE_SALT CLEF_JWT_SECRET_KEY; do
    COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" \
              --filter="state=enabled" --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" = "0" ]; then
        echo "❌ Secret $secret sans version active."
        echo "   printf '%s' 'VALEUR' | gcloud secrets versions add $secret --data-file=- --project=$PROJECT_ID"
        FAILED=true
    fi
done
[ "$FAILED" = false ] && echo "  ✅ secrets renseignés"

# Les identifiants de feuilles sont lus par app/services/sheets_real.py. Absents,
# l'app démarre mais l'authentification ne résout aucun rôle (constats M9/M10, M31).
for var in VEHICULES_SPREADSHEET_ID BENEVOLES_SPREADSHEET_ID RESPONSABLES_SPREADSHEET_ID; do
    if [ -z "${!var:-}" ]; then
        echo "⚠️  $var vide dans $ENV_FILE."
        echo "    Non bloquant, mais la synchronisation du référentiel ne fonctionnera pas."
    fi
done

if [ "$FAILED" = true ]; then
    echo ""
    echo "🛑 Rien n'a été déployé. Corriger les points ci-dessus."
    exit 1
fi
echo "  ✅ préflight complet"
echo ""

# ---------------------------------------------------------------------------
# Construction des images
# ---------------------------------------------------------------------------
BACKEND_IMAGE="${REGISTRY}/clef-api:${TAG}"
FRONTEND_IMAGE="${REGISTRY}/clef-frontend:${TAG}"

if [ "$SKIP_BUILD" = false ]; then
    if [[ "$COMPONENTS" == *api* ]]; then
        echo "🔨 Image backend (Cloud Build)..."
        gcloud builds submit backend \
            --tag="$BACKEND_IMAGE" \
            --project="$PROJECT_ID" \
            --region="$REGION"
        echo ""
    fi
    if [[ "$COMPONENTS" == *frontend* ]]; then
        echo "🔨 Image frontend (Cloud Build)..."
        gcloud builds submit frontend \
            --tag="$FRONTEND_IMAGE" \
            --project="$PROJECT_ID" \
            --region="$REGION"
        echo ""
    fi
else
    echo "⏭️  Construction ignorée : réutilisation de la dernière image poussée."
    BACKEND_IMAGE=$(gcloud artifacts docker images list "${REGISTRY}/clef-api" \
        --project="$PROJECT_ID" --sort-by=~UPDATE_TIME --limit=1 \
        --format="value(package)@value(version)" 2>/dev/null | head -1)
    [ -n "$BACKEND_IMAGE" ] || { echo "❌ Aucune image backend à réutiliser."; exit 1; }
    echo "    backend : $BACKEND_IMAGE"
    echo ""
fi

# ---------------------------------------------------------------------------
# Déploiement du backend, avec Redis en sidecar
# ---------------------------------------------------------------------------
# `gcloud run deploy` ne sait décrire ni plusieurs conteneurs ni un volume GCS : on
# passe donc par un descripteur de service complet.
if [[ "$COMPONENTS" == *api* ]]; then
    echo "☁️  Déploiement du backend (2 conteneurs : backend + redis)..."

    # L'URL du service est nécessaire au service lui-même (callbacks OAuth). Elle est
    # déterministe une fois le service créé ; au premier déploiement, elle est vide et
    # on relit après coup.
    BACKEND_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" \
        --format='value(status.url)' 2>/dev/null || true)
    FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" \
        --region="$REGION" --project="$PROJECT_ID" \
        --format='value(status.url)' 2>/dev/null || true)
    ALLOWED_FRONTEND_URLS="${FRONTEND_URL:-http://localhost:4200}"

    RENDERED=$(mktemp)
    trap 'rm -f "$RENDERED"' EXIT
    SERVICE_NAME="$SERVICE_NAME" ENVIRONMENT="$ENVIRONMENT" \
    MAX_INSTANCES="$MAX_INSTANCES" MIN_INSTANCES="$MIN_INSTANCES" \
    SERVICE_ACCOUNT="$SERVICE_ACCOUNT" BACKEND_IMAGE="$BACKEND_IMAGE" \
    PROJECT_ID="$PROJECT_ID" EMAIL_GESTIONNAIRE_DT="$EMAIL_GESTIONNAIRE_DT" \
    ALLOWED_FRONTEND_URLS="$ALLOWED_FRONTEND_URLS" \
    BACKEND_URL="${BACKEND_URL:-}" \
    VEHICULES_SPREADSHEET_ID="${VEHICULES_SPREADSHEET_ID:-}" \
    BENEVOLES_SPREADSHEET_ID="${BENEVOLES_SPREADSHEET_ID:-}" \
    RESPONSABLES_SPREADSHEET_ID="${RESPONSABLES_SPREADSHEET_ID:-}" \
    REDIS_MEMORY="$REDIS_MEMORY" SNAPSHOTS_BUCKET="$SNAPSHOTS_BUCKET" \
        envsubst < "$TEMPLATE" > "$RENDERED"

    gcloud run services replace "$RENDERED" \
        --region="$REGION" --project="$PROJECT_ID"

    gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" \
        --member=allUsers --role=roles/run.invoker >/dev/null
    echo "  ✅ backend déployé"
    echo ""
fi

if [[ "$COMPONENTS" == *frontend* ]]; then
    echo "☁️  Déploiement du frontend..."
    gcloud run deploy "$FRONTEND_SERVICE" \
        --image="$FRONTEND_IMAGE" \
        --region="$REGION" --project="$PROJECT_ID" \
        --platform=managed --allow-unauthenticated \
        --port=80 --memory=256Mi --cpu=1 \
        --min-instances=0 --max-instances=5
    echo "  ✅ frontend déployé"
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
echo ""

echo "✅ Déploiement « $ENVIRONMENT » terminé."
echo ""
echo "📍 URLs :"
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
