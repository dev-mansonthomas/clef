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
#   3. init, plan, puis apply après confirmation ;
#   4. signale les secrets encore vides.
#
# L'étape d'adoption du state de l'ancienne racine a disparu avec cette racine :
# `backend/terraform/` et `infra/` sont supprimées (constat N12).
#
# Idempotent : le relancer ne fait que reconverger.

set -euo pipefail

ENVIRONMENT="${1:-}"
TF_DIR="deploy/terraform"

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

# ─── Une seule source de variables : deploy/deploy.<env>.env ─────────────────
#
# ⚠️ Ce script lisait `deploy/terraform/environments/<env>.tfvars`, qui portait
# project_id, region et public_domain — en double avec le fichier d'environnement lu
# par 01-gcp-deploy.sh et 02-logs.sh. Deux sources pour une même valeur, dont une que
# personne ne pense à aller consulter : c'est ainsi qu'un domaine peut être corrigé
# d'un côté et pas de l'autre, avec pour symptôme un certificat qui ne couvre pas
# l'hôte que l'application annonce.
#
# Les tfvars sont SUPPRIMÉS. Terraform reçoit ces valeurs en `-var`, depuis le fichier
# d'environnement. Terraform garde ses propres DÉFAUTS (`variables.tf`) — un défaut
# n'est pas une source de vérité, c'est un repli.
# shellcheck source=deploy/env-commun.sh disable=SC1091
. "./deploy/env-commun.sh"
charger_env_deploiement "$ENVIRONMENT" || exit 1

: "${PROJECT_ID:?PROJECT_ID manquant dans $ENV_FILE}"
REGION="${REGION:-europe-west1}"
STATE_BUCKET="${PROJECT_ID}-clef-tfstate"

# Le domaine alimente le certificat managé : même règle que côté déploiement.
if ! PUBLIC_DOMAIN="$(valider_domaine_public "${PUBLIC_DOMAIN:-}")"; then
    echo "   Corriger PUBLIC_DOMAIN dans $ENV_FILE."
    exit 2
fi

# Les variables passées à Terraform. Seules celles RENSEIGNÉES sont transmises : les
# autres gardent le défaut déclaré dans variables.tf, qui reste le bon endroit pour
# une valeur qui ne dépend pas de l'environnement.
TF_ARGS=(
    -var "project_id=$PROJECT_ID"
    -var "environment=$ENVIRONMENT"
    -var "region=$REGION"
    -var "public_domain=$PUBLIC_DOMAIN"
)
[ -n "${KMS_REGION:-}" ]              && TF_ARGS+=(-var "kms_region=$KMS_REGION")
[ -n "${SNAPSHOT_RETENTION_DAYS:-}" ] && TF_ARGS+=(-var "snapshot_retention_days=$SNAPSHOT_RETENTION_DAYS")
[ -n "${KEEP_PUBLIC_IP:-}" ]          && TF_ARGS+=(-var "keep_public_ip=$KEEP_PUBLIC_IP")

# ---------------------------------------------------------------------------
# Journalisation — le plan et un rapport, lisibles depuis la VM
# ---------------------------------------------------------------------------
# Le script tourne sur l'HÔTE, l'agent travaille dans la VM, et le dépôt est sur un
# montage partagé. Écrire le plan ici permet de le faire auditer sans le recopier.
#
# ⚠️ Le flux n'est PAS redirigé vers un tee, contrairement à 01-gcp-deploy.sh : ce
# script pose une question de confirmation, et un tee en travers de stdout rend
# l'invite illisible ou la fait apparaître après coup. On écrit donc des fichiers
# explicites plutôt que de capturer la sortie.
#
# `debug/` est gitignoré. Le plan ne contient aucune valeur de secret : Terraform ne
# gère que les conteneurs, jamais les versions.
DEBUG_DIR="debug/deploy"
mkdir -p "$DEBUG_DIR"
PLAN_TXT="${DEBUG_DIR}/00-infra.${ENVIRONMENT}.plan.txt"
REPORT_FILE="${DEBUG_DIR}/00-infra.${ENVIRONMENT}.json"

R_STEP="démarrage"
R_APPLIQUE=false
R_DESTRUCTIONS=""

ecrire_rapport() {
    local code=$?
    # ⚠️ Le nettoyage du plan temporaire vit ICI, pas dans un second trap.
    #
    # Les traps bash ne s'additionnent pas : un `trap … EXIT` déclaré plus loin
    # REMPLACE celui-ci. C'est exactement ce qui s'était produit — un
    # `trap 'rm -f "$PLAN_FILE"' EXIT` posé à l'étape du plan écrasait
    # l'écriture du rapport, qui ne se produisait donc jamais sur une exécution
    # complète.
    #
    # Le code de sortie est capturé AVANT le `rm`, sinon on rapporterait celui du
    # nettoyage.
    rm -f "${PLAN_FILE:-}"
    local liste="[]"
    if [ -n "$R_DESTRUCTIONS" ]; then
        liste=$(printf '%s\n' "$R_DESTRUCTIONS" | sed 's/"/\\"/g; s/^/    "/; s/$/",/' \
                | sed '$ s/,$//')
        liste=$(printf '[\n%s\n  ]' "$liste")
    fi
    cat > "$REPORT_FILE" <<JSON
{
  "schemaVersion": 1,
  "tool": "00-infra.sh",
  "ok": $([ "$code" -eq 0 ] && echo true || echo false),
  "exitCode": $code,
  "derniereEtape": "$R_STEP",
  "environnement": "$ENVIRONMENT",
  "projet": "${PROJECT_ID:-}",
  "region": "${REGION:-}",
  "bucketDeState": "${STATE_BUCKET:-}",
  "applique": $R_APPLIQUE,
  "destructionsPlanifiees": $liste,
  "plan": "$PLAN_TXT"
}
JSON
    echo ""
    echo "📝 Rapport : $REPORT_FILE"
    [ -f "$PLAN_TXT" ] && echo "   Plan      : $PLAN_TXT"
}
trap ecrire_rapport EXIT

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
# L'adoption de l'ancien state a été RETIRÉE le 2026-08-28
# ---------------------------------------------------------------------------
# Ce script proposait d'adopter `backend/terraform/terraform.tfstate` : l'ancienne
# racine avait réellement provisionné le keyring KMS, le service account et les APIs,
# et sans adoption le premier apply aurait tenté de les recréer.
#
# L'adoption a eu lieu, le state vit dans GCS (bucket versionné), et les deux anciennes
# racines sont supprimées — constat N12 clos. Ce fichier d'état portait en outre
# `google_service_account_key.clef_backend`, donc une clé privée en clair sur disque :
# c'est le constat H6, et sa disparition est un bénéfice de plus.
#
# ⚠️ Si le state GCS était perdu, le repli n'est plus une copie locale mais les
# VERSIONS du bucket : `gcloud storage ls --all-versions gs://<bucket>/<env>/`.

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
# Pas de `trap` ici : il remplacerait celui du rapport. Le nettoyage est fait par
# `ecrire_rapport`, seul trap EXIT du script.
tofu -chdir="$TF_DIR" plan "${TF_ARGS[@]}" \
    -out="$PLAN_FILE" -input=false
echo ""

# ---------------------------------------------------------------------------
# Garde-fou : ne jamais détruire une ressource qui n'appartient pas à CLEF
# ---------------------------------------------------------------------------
# Le projet GCP est PARTAGÉ avec une autre application entière. Une ressource
# détruite ici et appartenant au voisin serait une panne chez quelqu'un d'autre,
# causée par notre outillage.
#
# La règle : toute destruction d'une ressource PORTEUSE DE DONNÉES OU D'IDENTITÉ
# doit viser un objet dont l'identifiant contient « clef ». Sinon, on refuse — sans
# demander, sans proposer de forcer.
#
# Les `google_project_service` en sont exclus à dessein : leur identifiant est un nom
# d'API (« compute.googleapis.com »), jamais préfixé, et leur destruction ne fait que
# les sortir du state — `disable_on_destroy = false` garantit que l'API reste activée.
# C'est vérifié séparément ci-dessous.
verifier_destructions() {
    local plan_texte
    plan_texte=$(tofu -chdir="$TF_DIR" show -no-color "$PLAN_FILE")

    # Le plan, en clair, pour audit après coup — y compris si on abandonne ensuite.
    printf '%s\n' "$plan_texte" > "$PLAN_TXT"
    R_STEP="plan écrit"
    R_DESTRUCTIONS=$(printf '%s\n' "$plan_texte" \
        | grep -E "will be destroyed|must be replaced" \
        | sed 's/^  # //' || true)

    # Types dont une destruction est irréversible ou porte une identité.
    local sensibles='google_secret_manager_secret|google_storage_bucket|google_kms|google_service_account|google_artifact_registry|google_redis|google_memorystore|google_sql'

    local suspectes
    suspectes=$(printf '%s\n' "$plan_texte" | awk -v sensibles="$sensibles" '
        # ATTENTION : « must be replaced » compte autant que « will be destroyed ».
        # Terraform emploie ce second libelle pour un remplacement force, qui
        # DETRUIT puis recree. Le cas est concret : google_secret_manager_secret na
        # aucun prevent_destroy, et modifier son bloc replication force un
        # remplacement, donc la perte de toutes ses versions. Le garde-fou annoncait
        # alors « aucune destruction planifiee ».
        #
        # (Pas dapostrophe dans ce commentaire : il vit dans un programme awk entre
        # guillemets simples, quune apostrophe terminerait.)
        /^  # .* (will be destroyed|must be replaced)/ {
            adresse = $2
            sensible = (adresse ~ sensibles)
            bloc = ""
            next
        }
        # Le prefixe varie selon le type de bloc : « - » sur une destruction, mais
        # « ~ », « + » ou rien du tout dans un bloc de remplacement « -/+ ». Ne
        # reconnaitre que « - » laissait la liste vide sur un remplacement, donc
        # refusait aussi les remplacements legitimes de CLEF.
        sensible && /^ +[-+~]? *(id|name|secret_id|bucket|account_id|repository_id|email) +=/ {
            # La valeur est la chaîne ENTRE GUILLEMETS. Surtout pas $NF : la ligne
            # se termine par « -> null » sur une destruction, et on comparerait
            # « null » au lieu de l identifiant — refusant alors tout apply légitime.
            if (match($0, /"[^"]*"/)) bloc = bloc " " substr($0, RSTART + 1, RLENGTH - 2)
        }
        sensible && /^    }/ {
            if (tolower(bloc) !~ /clef/) print adresse " ->" bloc
            sensible = 0
        }
    ')

    if [ -n "$suspectes" ]; then
        echo "🛑 REFUS — le plan détruirait des ressources qui ne semblent pas appartenir à CLEF :"
        echo ""
        printf '%s\n' "$suspectes" | sed 's/^/       /'
        echo ""
        echo "    Le projet $PROJECT_ID est partagé avec une autre application."
        echo "    Aucune ressource non préfixée 'clef' ne doit être détruite par cet outil."
        echo "    Rien n'a été appliqué. Corriger la configuration, pas ce garde-fou."
        exit 1
    fi

    # Les APIs sortant du state : vérifier qu'aucune ne serait désactivée.
    local apis_desactivees
    apis_desactivees=$(printf '%s\n' "$plan_texte" | awk '
        /^  # google_project_service.* (will be destroyed|must be replaced)/ { addr = $2; vu = 1; next }
        vu && /disable_on_destroy *= *true/ { print addr; vu = 0 }
        vu && /^    }/ { vu = 0 }
    ')
    if [ -n "$apis_desactivees" ]; then
        echo "🛑 REFUS — ces APIs seraient DÉSACTIVÉES sur un projet partagé :"
        printf '%s\n' "$apis_desactivees" | sed 's/^/       /'
        echo "    Poser 'disable_on_destroy = false' avant de continuer."
        exit 1
    fi

    local nb
    nb=$(printf '%s\n' "$plan_texte" | grep -cE "will be destroyed|must be replaced" || true)
    if [ "$nb" -gt 0 ]; then
        echo "  ✅ $nb destruction(s) planifiée(s), toutes sur des ressources CLEF :"
        printf '%s\n' "$plan_texte" | grep -E "will be destroyed|must be replaced" \
            | sed 's/^  # /       /'
        echo ""
    else
        echo "  ✅ aucune destruction planifiée"
        echo ""
    fi
}

verifier_destructions

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
R_STEP="apply"
tofu -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"
R_APPLIQUE=true
R_STEP="appliqué"
echo ""

# ---------------------------------------------------------------------------
# Secrets encore vides
# ---------------------------------------------------------------------------
# Terraform crée les conteneurs de secrets, jamais leurs valeurs : une valeur passée
# par Terraform finirait dans le state. Sans version, le déploiement échouera au
# démarrage du conteneur — autant le dire maintenant.
echo "🔐 Secrets..."
MISSING=""
for secret in CLEF_GOOGLE_CLIENT_ID CLEF_GOOGLE_CLIENT_SECRET CLEF_QR_CODE_SALT; do
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
    echo "      CLEF_QR_CODE_SALT peut être généré (⚠️ le changer invalide les QR déjà imprimés) :"
    printf '        openssl rand -hex 32 | tr -d "\\n" | gcloud secrets versions add CLEF_QR_CODE_SALT --data-file=- --project=%s\n' "$PROJECT_ID"
fi
echo ""

echo "✅ Infrastructure « $ENVIRONMENT » en place."
echo ""
tofu -chdir="$TF_DIR" output
echo ""
echo "📌 À faire avant le premier déploiement : renseigner les secrets ci-dessus"
echo "   s'il en manque."
echo ""
echo "   ⚠️  NE PAS chercher à partager les feuilles Google ou les dossiers Drive"
echo "       avec ce service account : le domaine @croix-rouge.fr interdit le"
echo "       partage vers une adresse extérieure, et une adresse .gserviceaccount.com"
echo "       en est une. C'est structurel, pas un réglage à trouver."
echo ""
echo "       C'est pour cela que les données circulent dans l'autre sens :"
echo "         • bénévoles   : Apps Script POUSSE la feuille vers l'API (clé API) ;"
echo "         • véhicules   : Apps Script tire depuis l'API vers la feuille ;"
echo "         • Drive/Gmail : sous l'OAuth du gestionnaire DT, dont le refresh"
echo "                         token est chiffré par KMS — pas sous ce compte."
echo ""
echo "   Puis : ./01-gcp-deploy.sh $ENVIRONMENT"
