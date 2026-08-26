#!/usr/bin/env bash
#
# CLEF — provisionnement de l'infrastructure GCP (étape 1 sur 2)
#
#   ./00-infra.sh dev      puis  ./01-gcp-deploy.sh dev
#
# À LANCER DEPUIS L'HÔTE. La VM de développement ne détient aucune credential
# sortante, par construction : ce script échoue proprement si gcloud est absent.
#
# Ce qu'il fait, dans l'ordre :
#   1. vérifie les prérequis et l'authentification ;
#   2. crée le bucket de state Terraform (un backend ne peut pas se provisionner
#      lui-même — c'est le seul geste fait hors Terraform) ;
#   3. adopte le state local de l'ancienne racine, s'il existe et si le nouveau est
#      vide, pour ne pas tenter de recréer un keyring KMS déjà en place ;
#   4. init, plan, puis apply après confirmation ;
#   5. signale les secrets encore vides.
#
# Idempotent : le relancer ne fait que reconverger.

set -euo pipefail

ENVIRONMENT="${1:-}"
TF_DIR="deploy/terraform"
OLD_STATE="backend/terraform/terraform.tfstate"

# ---------------------------------------------------------------------------
# Aide et validation des arguments
# ---------------------------------------------------------------------------
usage() {
    cat <<'USAGE'
Usage : ./00-infra.sh <dev|test|prod> [--auto-approve]

  Provisionne l'infrastructure GCP de CLEF : APIs, service account, Artifact
  Registry, secrets, KMS, et le bucket des instantanés Redis.

  --auto-approve   N'affiche pas le plan pour confirmation. À réserver à une
                   réexécution dont on a déjà lu le plan.

Enchaîner ensuite avec : ./01-gcp-deploy.sh <env>
USAGE
}

AUTO_APPROVE=false
for arg in "$@"; do
    case "$arg" in
        --auto-approve) AUTO_APPROVE=true ;;
        --help|-h) usage; exit 0 ;;
    esac
done

case "$ENVIRONMENT" in
    dev|test|prod) ;;
    "") echo "❌ Environnement manquant."; echo ""; usage; exit 2 ;;
    *)  echo "❌ Environnement inconnu : $ENVIRONMENT"; echo ""; usage; exit 2 ;;
esac

TFVARS="$TF_DIR/environments/${ENVIRONMENT}.tfvars"
[ -f "$TFVARS" ] || { echo "❌ $TFVARS absent."; exit 1; }

PROJECT_ID=$(grep -E '^project_id' "$TFVARS" | cut -d'"' -f2)
REGION=$(grep -E '^region' "$TFVARS" | cut -d'"' -f2)
STATE_BUCKET="${PROJECT_ID}-clef-tfstate"

echo "🏗️  CLEF — infrastructure « $ENVIRONMENT »"
echo "    projet : $PROJECT_ID"
echo "    région : $REGION"
echo ""

# ---------------------------------------------------------------------------
# Préflight
# ---------------------------------------------------------------------------
echo "🔎 Prérequis..."

for cmd in gcloud tofu; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "❌ '$cmd' introuvable."
        [ "$cmd" = "gcloud" ] && echo "   Ce script se lance depuis l'HÔTE, pas depuis la VM de développement."
        exit 1
    fi
done

ACCOUNT=$(gcloud config get-value account 2>/dev/null || true)
if [ -z "$ACCOUNT" ] || [ "$ACCOUNT" = "(unset)" ]; then
    echo "❌ Non authentifié. Lancer : gcloud auth login"
    exit 1
fi
echo "  ✅ authentifié : $ACCOUNT"

if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
    echo "❌ Projet '$PROJECT_ID' inaccessible avec ce compte."
    exit 1
fi
echo "  ✅ projet accessible"
echo ""

# ---------------------------------------------------------------------------
# Bucket de state
# ---------------------------------------------------------------------------
# Un backend Terraform ne peut pas se provisionner lui-même : c'est le seul geste de
# ce script fait hors Terraform. Le versionnement n'est pas cosmétique — c'est ce qui
# permet de revenir en arrière après un apply malheureux.
echo "🪣 Bucket de state..."
if gcloud storage buckets describe "gs://$STATE_BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "  ✅ gs://$STATE_BUCKET existe déjà"
else
    echo "  → création de gs://$STATE_BUCKET"
    gcloud storage buckets create "gs://$STATE_BUCKET" \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --uniform-bucket-level-access \
        --public-access-prevention
    gcloud storage buckets update "gs://$STATE_BUCKET" --versioning
    echo "  ✅ créé et versionné"
fi
echo ""

# ---------------------------------------------------------------------------
# Adoption de l'ancien state
# ---------------------------------------------------------------------------
# L'ancienne racine backend/terraform a réellement provisionné un keyring KMS, un
# service account et 11 APIs. Sans adopter son state, le premier apply tenterait de
# les recréer — et échouerait, les noms étant déjà pris.
#
# Les adresses de ressources de la nouvelle racine sont volontairement identiques pour
# que cette adoption fonctionne.
REMOTE_STATE_EXISTS=false
if gcloud storage ls "gs://$STATE_BUCKET/${ENVIRONMENT}/default.tfstate" >/dev/null 2>&1; then
    REMOTE_STATE_EXISTS=true
fi

if [ "$REMOTE_STATE_EXISTS" = false ] && [ -f "$OLD_STATE" ] && [ "$ENVIRONMENT" = "dev" ]; then
    echo "📦 Adoption de l'ancien state local..."
    echo "    $OLD_STATE porte des ressources réelles (KMS, service account, APIs)."
    echo "    Sans cette adoption, le premier apply tenterait de les recréer."
    echo ""
    RESOURCES=$(python3 -c "
import json,sys
d=json.load(open('$OLD_STATE'))
for r in d.get('resources',[]): print(f\"      - {r['type']}.{r['name']}\")
" 2>/dev/null || echo "      (inventaire indisponible)")
    echo "$RESOURCES"
    echo ""
    read -r -p "    Adopter ce state ? [o/N] " reply
    if [ "$reply" = "o" ] || [ "$reply" = "O" ]; then
        cp "$OLD_STATE" "$TF_DIR/terraform.tfstate"
        echo "  ✅ copié — il sera migré vers GCS par l'init"
    else
        echo "  ⏭️  ignoré. ⚠️ L'apply échouera probablement sur des ressources déjà existantes."
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Init, plan, apply
# ---------------------------------------------------------------------------
echo "⚙️  Initialisation de Terraform..."
tofu -chdir="$TF_DIR" init \
    -backend-config="bucket=$STATE_BUCKET" \
    -backend-config="prefix=$ENVIRONMENT" \
    -migrate-state -force-copy -input=false
echo ""

# `terraform.tfstate` local n'a plus lieu d'être une fois migré : le laisser
# entretiendrait le doute sur la source de vérité.
if [ -f "$TF_DIR/terraform.tfstate" ]; then
    mv "$TF_DIR/terraform.tfstate" "$TF_DIR/terraform.tfstate.migre-vers-gcs"
    echo "ℹ️  State local renommé en terraform.tfstate.migre-vers-gcs (la source est GCS désormais)."
    echo ""
fi

echo "📋 Plan..."
PLAN_FILE=$(mktemp)
trap 'rm -f "$PLAN_FILE"' EXIT
tofu -chdir="$TF_DIR" plan -var-file="environments/${ENVIRONMENT}.tfvars" \
    -out="$PLAN_FILE" -input=false
echo ""

if [ "$AUTO_APPROVE" = false ]; then
    echo "⚠️  Relisez le plan ci-dessus. Points d'attention :"
    echo "     • aucune 'google_service_account_key' ne doit être CRÉÉE (constat H6) ;"
    echo "     • le keyring KMS et le service account doivent être RECONNUS, pas recréés ;"
    echo "     • une destruction de google_storage_bucket serait une perte de données."
    echo ""
    read -r -p "    Appliquer ? [o/N] " reply
    [ "$reply" = "o" ] || [ "$reply" = "O" ] || { echo "🛑 Abandonné. Rien n'a été appliqué."; exit 0; }
fi

echo ""
echo "🚀 Application..."
tofu -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"
echo ""

# ---------------------------------------------------------------------------
# Secrets encore vides
# ---------------------------------------------------------------------------
# Terraform crée les conteneurs de secrets, jamais leurs valeurs : une valeur passée
# par Terraform finirait dans le state. Sans version, le déploiement échouera au
# démarrage du conteneur — autant le dire maintenant.
echo "🔐 Secrets..."
MISSING=""
for secret in CLEF_GOOGLE_CLIENT_ID CLEF_GOOGLE_CLIENT_SECRET CLEF_QR_CODE_SALT CLEF_JWT_SECRET_KEY; do
    COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" \
              --filter="state=enabled" --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" = "0" ]; then
        MISSING="$MISSING $secret"
    else
        echo "  ✅ $secret ($COUNT version(s))"
    fi
done

if [ -n "$MISSING" ]; then
    echo ""
    echo "  ⚠️  Secrets sans aucune version :$MISSING"
    echo "      Le déploiement échouera au démarrage tant qu'ils sont vides."
    echo "      Pour chacun :"
    echo "        printf '%s' 'LA_VALEUR' | gcloud secrets versions add NOM --data-file=- --project=$PROJECT_ID"
    echo ""
    echo "      QR_CODE_SALT peut être généré (⚠️ le changer invalide les QR déjà imprimés) :"
    printf '        openssl rand -hex 32 | tr -d "\\n" | gcloud secrets versions add CLEF_QR_CODE_SALT --data-file=- --project=%s\n' "$PROJECT_ID"
fi
echo ""

echo "✅ Infrastructure « $ENVIRONMENT » en place."
echo ""
tofu -chdir="$TF_DIR" output
echo ""
echo "📌 Deux choses à faire avant le premier déploiement :"
echo "   1. Partager les feuilles Google et les dossiers Drive avec l'adresse du"
echo "      service account affichée ci-dessus (comme avec un utilisateur)."
echo "   2. Renseigner les secrets ci-dessus s'il en manque."
echo ""
echo "   Puis : ./01-gcp-deploy.sh $ENVIRONMENT"
