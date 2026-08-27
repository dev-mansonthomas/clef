#!/usr/bin/env bash
#
# CLEF — collecte des journaux GCP dans debug/logs/ (étape 3, après 00 et 01)
#
#   ./02-logs.sh dev                      tout : déploiement et exécution
#   ./02-logs.sh dev --what=run           seulement les journaux d'exécution
#   ./02-logs.sh dev --what=deploy        seulement construction et création de révision
#   ./02-logs.sh dev --revision=clef-api-00001-cwd
#
# À LANCER DEPUIS L'HÔTE. La VM ne détient aucune credential sortante.
#
# POURQUOI CET OUTIL
#
# Le dépôt est sur un montage partagé : les scripts tournent sur l'hôte, l'agent
# travaille dans la VM. Écrire les journaux dans `debug/logs/` les rend lisibles
# sans recopier des murs de sortie à la main.
#
# Et surtout : quand une révision Cloud Run **échoue au démarrage**,
# `gcloud run services logs read` ne la montre pas — elle n'a jamais servi de
# trafic. Il faut interroger Cloud Logging par nom de révision, et lire les
# `status.conditions` du service, où vit le vrai message d'échec. Cet outil fait
# les deux, y compris pour les conteneurs adjoints (le nom du conteneur est un
# label, pas un champ).
#
# ⚠️ Aucune valeur de secret n'est collectée : les secrets arrivent par
# `secretKeyRef`, dont seul le NOM apparaît dans un `describe`. Les adresses
# électroniques sont masquées avant écriture — ce sont des données personnelles.
#
# `debug/` est gitignoré.

set -uo pipefail   # pas de -e : une collecte partielle vaut mieux qu'un abandon

# ⚠️ L'aide est traitée AVANT tout : sinon « --help » est consommé comme nom
# d'environnement, et le script sort en code 2 sur un usage parfaitement légitime.
for arg in "$@"; do
    case "$arg" in --help|-h) HELP=1 ;; esac
done

ENVIRONMENT="${1:-}"
[ $# -gt 0 ] && shift

usage() {
    cat <<'USAGE'
Usage : ./02-logs.sh <dev|test|prod> [options]

  --what=run|deploy|all   Quoi collecter. Défaut : all
                            run    : journaux des conteneurs qui tournent ou ont tourné
                            deploy : Cloud Build + création de révision + conditions
  --service=api|frontend|all   Défaut : all
  --revision=NOM          Révision précise. Défaut : la dernière de chaque service
  --freshness=DUREE       Fenêtre de recherche. Défaut : 2h  (ex. 30m, 6h, 1d)
  --limit=N               Lignes par requête. Défaut : 300
  --help

Écrit dans debug/logs/ :
  02-logs.<env>.json                    index de la collecte et erreurs rencontrées
  <env>-<svc>-conditions.txt            status.conditions — le vrai message d'échec
  <env>-<svc>-revisions.txt             liste des révisions et leur état
  <env>-<svc>-describe.yaml             spécification déployée (adresses masquées)
  <env>-<svc>-<revision>-<conteneur>.log   journaux, un fichier par conteneur
  <env>-builds.txt / <env>-build-<id>.log  côté construction
USAGE
}

if [ "${HELP:-0}" = "1" ]; then usage; exit 0; fi

WHAT="all"; SERVICE_FILTER="all"; REVISION=""; FRESHNESS="2h"; LIMIT="300"
for arg in "$@"; do
    case "$arg" in
        --what=*)      WHAT="${arg#*=}" ;;
        --service=*)   SERVICE_FILTER="${arg#*=}" ;;
        --revision=*)  REVISION="${arg#*=}" ;;
        --freshness=*) FRESHNESS="${arg#*=}" ;;
        --limit=*)     LIMIT="${arg#*=}" ;;
        --help|-h)     usage; exit 0 ;;
        *) echo "❌ Option inconnue : $arg"; echo ""; usage; exit 2 ;;
    esac
done

case "$ENVIRONMENT" in
    dev|test|prod) ;;
    "") echo "❌ Environnement manquant."; echo ""; usage; exit 2 ;;
    *)  echo "❌ Environnement inconnu : $ENVIRONMENT"; echo ""; usage; exit 2 ;;
esac
case "$WHAT" in run|deploy|all) ;; *) echo "❌ --what invalide : $WHAT"; exit 2 ;; esac
case "$SERVICE_FILTER" in api|frontend|all) ;; *) echo "❌ --service invalide"; exit 2 ;; esac

ENV_FILE="deploy/deploy.${ENVIRONMENT}.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ $ENV_FILE absent — c'est lui qui porte PROJECT_ID et REGION."
    exit 1
fi
set -a
# shellcheck disable=SC1090
. "./$ENV_FILE"
set +a
: "${PROJECT_ID:?PROJECT_ID manquant dans $ENV_FILE}"
: "${REGION:?REGION manquant dans $ENV_FILE}"
SERVICE_NAME="${SERVICE_NAME:-clef-api}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-clef-frontend}"

if ! command -v gcloud >/dev/null 2>&1; then
    echo "❌ 'gcloud' introuvable. Ce script se lance depuis l'HÔTE, pas depuis la VM."
    exit 1
fi

OUT="debug/logs"
mkdir -p "$OUT"
INDEX="${OUT}/02-logs.${ENVIRONMENT}.json"
FICHIERS=""
ERREURS=""

echo "📥 CLEF — collecte des journaux « $ENVIRONMENT »"
echo "    projet  : $PROJECT_ID"
echo "    région  : $REGION"
echo "    portée  : $WHAT / $SERVICE_FILTER, fenêtre $FRESHNESS"
echo ""

# ---------------------------------------------------------------------------
# Masquage des données personnelles
# ---------------------------------------------------------------------------
# Le `describe` d'un service expose les valeurs des variables d'environnement, dont
# EMAIL_GESTIONNAIRE_DT. `debug/` est gitignoré, mais autant ne pas écrire l'adresse :
# on garde la première lettre et le domaine, ce qui suffit à vérifier la
# configuration sans recopier une donnée personnelle.
masquer() {
    # ⚠️ Les adresses de service account (*.gserviceaccount.com) sont ÉPARGNÉES :
    # ce ne sont pas des personnes, et il faut pouvoir les lire pour vérifier quelle
    # identité le service utilise. Une première version masquait
    # « clef-backend@rcq-fr-dev.iam.gserviceaccount.com », ce qui rendait le
    # `describe` inutilisable pour le diagnostic sans rien protéger.
    sed -E '/gserviceaccount\.com/! s/([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)/\1***@\2/g'
}

# Enregistre une sortie de commande, ou l'erreur si la commande échoue. Ne
# s'interrompt jamais : une collecte partielle est ce qu'on veut en cas de panne.
collecter() {
    local fichier="$1" libelle="$2"; shift 2
    local sortie code
    sortie=$("$@" 2>&1); code=$?
    if [ $code -ne 0 ]; then
        printf '### ÉCHEC de la collecte « %s » (code %d)\n\n%s\n' \
            "$libelle" "$code" "$sortie" | masquer > "$fichier"
        echo "  ⚠️  $libelle : échec (détail dans $fichier)"
        ERREURS="${ERREURS}${libelle}|"
    elif [ -z "$sortie" ]; then
        printf '### Aucune donnée pour « %s » sur la fenêtre %s\n' \
            "$libelle" "$FRESHNESS" > "$fichier"
        echo "  ∅  $libelle : aucune donnée"
    else
        printf '%s\n' "$sortie" | masquer > "$fichier"
        echo "  ✅ $libelle → $fichier ($(wc -l < "$fichier" | tr -d ' ') lignes)"
    fi
    FICHIERS="${FICHIERS}${fichier}|"
}

derniere_revision() {
    gcloud run revisions list --service="$1" \
        --region="$REGION" --project="$PROJECT_ID" \
        --sort-by=~metadata.creationTimestamp --limit=1 \
        --format='value(metadata.name)' 2>/dev/null | head -1
}

# ---------------------------------------------------------------------------
# Un service : conditions, révisions, spécification, journaux par conteneur
# ---------------------------------------------------------------------------
traiter_service() {
    local svc="$1" court="$2"
    shift 2
    local conteneurs=("$@")

    echo "🔎 Service $svc"

    if [ "$WHAT" = "deploy" ] || [ "$WHAT" = "all" ]; then
        # ⚠️ C'est ICI que vit le message d'échec d'un démarrage, pas dans les logs :
        # « The user-provided container failed the startup probe » est une condition
        # du service, avec un message souvent plus précis que celui de gcloud.
        collecter "${OUT}/${ENVIRONMENT}-${court}-conditions.txt" "$court : conditions" \
            gcloud run services describe "$svc" --region="$REGION" --project="$PROJECT_ID" \
            --format='yaml(status.conditions, status.latestCreatedRevisionName, status.latestReadyRevisionName)'

        collecter "${OUT}/${ENVIRONMENT}-${court}-revisions.txt" "$court : révisions" \
            gcloud run revisions list --service="$svc" --region="$REGION" \
            --project="$PROJECT_ID" --format='table(metadata.name, status.conditions[0].status, status.conditions[0].message, metadata.creationTimestamp)'

        # La spécification réellement déployée : c'est le seul moyen de vérifier que
        # les annotations et les variables ont bien atterri, plutôt que de le supposer.
        collecter "${OUT}/${ENVIRONMENT}-${court}-describe.yaml" "$court : spécification" \
            gcloud run services describe "$svc" --region="$REGION" \
            --project="$PROJECT_ID" --format=yaml
    fi

    if [ "$WHAT" = "run" ] || [ "$WHAT" = "all" ]; then
        local rev="$REVISION"
        [ -n "$rev" ] || rev=$(derniere_revision "$svc")
        if [ -z "$rev" ]; then
            echo "  ∅  aucune révision pour $svc"
            return
        fi
        echo "     révision : $rev"

        # Un fichier par conteneur. Le nom du conteneur est un LABEL, pas un champ :
        # sans ce filtre, les lignes du backend et du sidecar sont entremêlées et on
        # attribue au mauvais conteneur.
        local c
        for c in "${conteneurs[@]}"; do
            collecter "${OUT}/${ENVIRONMENT}-${court}-${rev}-${c}.log" \
                "$court/$rev/$c" \
                gcloud logging read \
                "resource.type=\"cloud_run_revision\" resource.labels.revision_name=\"${rev}\" labels.\"run.googleapis.com/container_name\"=\"${c}\"" \
                --project="$PROJECT_ID" --limit="$LIMIT" --freshness="$FRESHNESS" \
                --order=asc \
                --format='value(timestamp, severity, textPayload)'
        done

        # Et une passe SANS filtre de conteneur : elle rattrape les lignes émises par
        # l'infrastructure (montage gcsfuse, sondes, arrêts), qui ne portent pas de
        # nom de conteneur et seraient donc invisibles ci-dessus.
        collecter "${OUT}/${ENVIRONMENT}-${court}-${rev}-infrastructure.log" \
            "$court/$rev/infrastructure" \
            gcloud logging read \
            "resource.type=\"cloud_run_revision\" resource.labels.revision_name=\"${rev}\" NOT labels.\"run.googleapis.com/container_name\":*" \
            --project="$PROJECT_ID" --limit="$LIMIT" --freshness="$FRESHNESS" \
            --order=asc --format='value(timestamp, severity, textPayload, jsonPayload)'
    fi
    echo ""
}

if [ "$SERVICE_FILTER" = "api" ] || [ "$SERVICE_FILTER" = "all" ]; then
    traiter_service "$SERVICE_NAME" "api" backend redis
fi
if [ "$SERVICE_FILTER" = "frontend" ] || [ "$SERVICE_FILTER" = "all" ]; then
    traiter_service "$FRONTEND_SERVICE" "frontend" "$FRONTEND_SERVICE"
fi

# ---------------------------------------------------------------------------
# Côté construction
# ---------------------------------------------------------------------------
if [ "$WHAT" = "deploy" ] || [ "$WHAT" = "all" ]; then
    echo "🔨 Cloud Build"
    collecter "${OUT}/${ENVIRONMENT}-builds.txt" "constructions récentes" \
        gcloud builds list --region="$REGION" --project="$PROJECT_ID" --limit=5 \
        --format='table(id, status, createTime, duration, images)'

    # Le journal de la dernière construction en échec, s'il y en a une : c'est celle
    # qu'on veut lire, pas la dernière tout court.
    ECHEC=$(gcloud builds list --region="$REGION" --project="$PROJECT_ID" \
        --filter='status!=SUCCESS' --limit=1 --format='value(id)' 2>/dev/null | head -1)
    if [ -n "$ECHEC" ]; then
        collecter "${OUT}/${ENVIRONMENT}-build-${ECHEC}.log" "construction en échec $ECHEC" \
            gcloud builds log "$ECHEC" --region="$REGION" --project="$PROJECT_ID"
    else
        echo "  ∅  aucune construction en échec sur les 5 dernières"
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------
liste_json() {
    local brut="$1"
    [ -z "$brut" ] && { printf '[]'; return; }
    printf '%s' "$brut" | tr '|' '\n' | sed '/^$/d' \
        | sed 's/"/\\"/g; s/^/    "/; s/$/",/' | sed '$ s/,$//' \
        | { printf '[\n'; cat; printf '  ]'; }
}

cat > "$INDEX" <<JSON
{
  "schemaVersion": 1,
  "tool": "02-logs.sh",
  "environnement": "$ENVIRONMENT",
  "projet": "$PROJECT_ID",
  "region": "$REGION",
  "portee": { "what": "$WHAT", "service": "$SERVICE_FILTER" },
  "revisionDemandee": "$REVISION",
  "fenetre": "$FRESHNESS",
  "limiteParRequete": $LIMIT,
  "fichiers": $(liste_json "$FICHIERS"),
  "collectesEnEchec": $(liste_json "$ERREURS")
}
JSON

echo "📝 Index : $INDEX"
echo ""
echo "Par où commencer la lecture :"
echo "  1. ${OUT}/${ENVIRONMENT}-api-conditions.txt   le message d'échec réel"
echo "  2. ${OUT}/${ENVIRONMENT}-api-*-redis.log      le sidecar, s'il n'a pas démarré"
echo "  3. ${OUT}/${ENVIRONMENT}-api-*-infrastructure.log   montage gcsfuse et sondes"
