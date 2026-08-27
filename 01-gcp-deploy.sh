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
# Limite interne de Redis, à tenir SOUS celle du conteneur : un BGSAVE duplique les
# pages modifiées pendant sa durée, et cette copie échappe à `maxmemory`. Au-delà,
# c'est Cloud Run qui tue le conteneur, et l'instance repart du dernier instantané.
# Défaut : 65 % de la limite, calculé plutôt que codé en dur pour suivre REDIS_MEMORY.
if [ -z "${REDIS_MAXMEMORY:-}" ]; then
    _mem_mo=${REDIS_MEMORY%[MmGg]i}
    case "$REDIS_MEMORY" in *[Gg]i) _mem_mo=$((_mem_mo * 1024)) ;; esac
    REDIS_MAXMEMORY="$(( _mem_mo * 65 / 100 ))mb"
fi
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
for secret in CLEF_GOOGLE_CLIENT_ID CLEF_GOOGLE_CLIENT_SECRET CLEF_QR_CODE_SALT; do
    COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" \
              --filter="state=enabled" --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" = "0" ]; then
        echo "❌ Secret $secret sans version active."
        echo "   printf '%s' 'VALEUR' | gcloud secrets versions add $secret --data-file=- --project=$PROJECT_ID"
        FAILED=true
    fi
done
[ "$FAILED" = false ] && echo "  ✅ secrets renseignés"

# Les identifiants de feuilles sont lus par app/services/sheets_real.py, qui
# s'authentifie avec le SERVICE ACCOUNT — et ne peut donc pas les lire : le domaine
# @croix-rouge.fr interdit tout partage vers une adresse extérieure, ce qu'est une
# adresse .gserviceaccount.com. Les renseigner ne débloque rien ; les laisser vides
# ne casse rien de plus.
#
# Le référentiel arrive dans Redis par Apps Script, pas par ce chemin. Trois routes
# dépendent pourtant encore de sheets_real et prendront un 403 en production —
# constat N13 de docs/TODO.md. On le dit ici, une fois, plutôt que de laisser croire
# qu'une variable manquante en est la cause.
for var in VEHICULES_SPREADSHEET_ID BENEVOLES_SPREADSHEET_ID RESPONSABLES_SPREADSHEET_ID; do
    if [ -z "${!var:-}" ]; then
        echo "ℹ️  $var vide — sans effet : le service account ne peut de toute façon"
        echo "    pas lire une feuille du domaine (voir constat N13)."
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

        # CORS ne sert plus qu'à l'accès direct au backend : nginx relaie /api et
        # /auth, donc le parcours normal est en même origine.
        local cors="${backend_url:-http://localhost:8000}"
        [ -n "$frontend_url" ] && cors="${frontend_url},${cors}"

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
        local front="${frontend_url:-$backend_url}"
        local domain="${front#https://}"
        domain="${domain#http://}"

        SERVICE_NAME="$SERVICE_NAME" ENVIRONMENT="$ENVIRONMENT" \
        MAX_INSTANCES="$MAX_INSTANCES" MIN_INSTANCES="$MIN_INSTANCES" \
        SERVICE_ACCOUNT="$SERVICE_ACCOUNT" BACKEND_IMAGE="$BACKEND_IMAGE" \
        PROJECT_ID="$PROJECT_ID" EMAIL_GESTIONNAIRE_DT="$EMAIL_GESTIONNAIRE_DT" \
        CORS_ORIGINS="$cors" \
        ALLOWED_FRONTEND_URLS="$front" \
        FRONTEND_URL="$front" \
        DOMAIN="$domain" \
        BACKEND_URL="$backend_url" \
        GOOGLE_REDIRECT_URI="${front:+${front}/auth/callback}" \
        VEHICULES_SPREADSHEET_ID="${VEHICULES_SPREADSHEET_ID:-}" \
        BENEVOLES_SPREADSHEET_ID="${BENEVOLES_SPREADSHEET_ID:-}" \
        RESPONSABLES_SPREADSHEET_ID="${RESPONSABLES_SPREADSHEET_ID:-}" \
        REDIS_MEMORY="$REDIS_MEMORY" REDIS_MAXMEMORY="$REDIS_MAXMEMORY" \
        SNAPSHOTS_BUCKET="$SNAPSHOTS_BUCKET" \
            envsubst < "$TEMPLATE" > "$rendered"

        gcloud run services replace "$rendered" \
            --region="$REGION" --project="$PROJECT_ID"
        rm -f "$rendered"
    }

    BACKEND_URL=$(service_url "$SERVICE_NAME")
    FRONTEND_URL=$(service_url "$FRONTEND_SERVICE")
    FIRST_CREATION=false
    [ -z "$BACKEND_URL" ] && FIRST_CREATION=true

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

    echo "  ✅ backend déployé"
    echo ""
    echo "  📌 Ajouter cet URI de redirection au client OAuth de la console GCP :"
    echo "     ${BACKEND_URL}/auth/callback"
    echo ""
fi

if [[ "$COMPONENTS" == *frontend* ]]; then
    echo "☁️  Déploiement du frontend..."
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
