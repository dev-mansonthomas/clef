#!/bin/bash

# CLEF - Local Development Environment Launcher
# This script starts the entire development stack using Docker Compose
#
# Deux modes :
#   ./run_local.sh          mode mock (défaut) — aucune credential requise
#   ./run_local.sh --real   intégration réelle — exige les credentials GCP
#
# Le mode réel n'a de sens que sur l'HÔTE : le modèle de sécurité veut que la VM de
# développement ne détienne aucune credential sortante.

set -e

usage() {
    cat <<'USAGE'
Usage : ./run_local.sh [--real] [--help]

  (aucune option)  Mode mock. Services Google et OIDC simulés, données fictives.
                   Fonctionne partout, y compris sans credential. C'est le défaut.

  --real           Intégration réelle. Utilise les vrais services Google via le
                   service account monté depuis ~/.cred/CLEF. À lancer depuis
                   l'hôte uniquement. Le script vérifie les prérequis avant de
                   démarrer quoi que ce soit et s'arrête net s'il en manque un.

  --help           Affiche cette aide.
USAGE
}

REAL_MODE=false
while [ $# -gt 0 ]; do
    case "$1" in
        --real) REAL_MODE=true ;;
        --help|-h) usage; exit 0 ;;
        *) echo "❌ Option inconnue : $1"; echo ""; usage; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Préflight du mode réel
# ---------------------------------------------------------------------------
# Sans ces contrôles, une credential absente se manifeste par un conteneur backend
# « unhealthy » et deux frontends qui ne démarrent pas — un symptôme à trois niveaux
# de distance de la cause. On échoue tôt, avec le nom du fichier manquant.
preflight_real() {
    local env_file="backend/.env"
    local failed=false

    echo "🔎 Vérification des prérequis du mode réel..."

    if [ ! -f "$env_file" ]; then
        echo "❌ $env_file absent. Le copier depuis backend/.env.example et le renseigner."
        exit 1
    fi

    # Chemin de la credential tel que le conteneur le verra, puis son équivalent hôte.
    local container_path
    container_path=$(grep -E '^GOOGLE_APPLICATION_CREDENTIALS=' "$env_file" | tail -1 | cut -d= -f2-)

    if [ -z "$container_path" ]; then
        echo "❌ GOOGLE_APPLICATION_CREDENTIALS n'est pas défini dans $env_file."
        echo "   Le mode réel en a besoin (app/services/sheets_real.py:30)."
        failed=true
    else
        # docker-compose monte ~/.cred/CLEF sur /credentials (lecture seule).
        local host_path
        host_path="${HOME}/.cred/CLEF/$(basename "$container_path")"
        if [ -f "$host_path" ]; then
            echo "  ✅ Service account : $host_path"
        else
            echo "❌ Service account introuvable : $host_path"
            echo "   Attendu parce que $env_file pointe $container_path,"
            echo "   et que docker-compose monte ~/.cred/CLEF sur /credentials."
            failed=true
        fi
    fi

    # Les identifiants de feuilles sont lus par sheets_real.py:24-26. Leur absence
    # n'empêche pas de démarrer, mais dégrade silencieusement l'authentification :
    # c'est un avertissement, pas un blocage. Détail dans le message ci-dessous.
    local missing_ids=""
    for var in VEHICULES_SPREADSHEET_ID BENEVOLES_SPREADSHEET_ID RESPONSABLES_SPREADSHEET_ID; do
        if ! grep -qE "^${var}=.+" "$env_file"; then
            missing_ids="$missing_ids $var"
        fi
    done
    if [ -n "$missing_ids" ]; then
        echo "⚠️  Identifiants de feuilles Google absents de $env_file :$missing_ids"
        echo "    Ce n'est pas bloquant, mais sachez ce que vous perdez :"
        echo "      • l'authentification lit les bénévoles dans Sheets à chaque requête"
        echo "        (auth/service.py:104). Sans ces identifiants, la lecture échoue,"
        echo "        l'exception est avalée (constat M2) et TOUT utilisateur devient un"
        echo "        « Bénévole » sans UL ni périmètre — sans aucun message d'erreur."
        echo "      • seul EMAIL_GESTIONNAIRE_DT reste reconnu comme Gestionnaire DT :"
        echo "        ce chemin ne passe pas par Sheets (auth/service.py:33)."
        echo "      • les écrans admin restent donc utilisables avec CE compte, et Drive,"
        echo "        Calendar et Gmail fonctionnent normalement."
        echo "    ⚠️  De plus, get_benevole_by_email() n'existe QUE sur le mock :"
        echo "        le service réel lèvera AttributeError, avalée elle aussi."
        echo "        Voir les constats M9/M10 et M31 de docs/TODO.md."
        echo ""
    else
        echo "  ✅ Identifiants de feuilles Google renseignés"
    fi

    if [ "$failed" = true ]; then
        echo ""
        echo "🛑 Rien n'a été démarré. Corriger les points ci-dessus, ou lancer sans"
        echo "   --real pour le mode mock."
        exit 1
    fi

    echo "  ✅ Prérequis réunis"
    echo ""
}

if [ "$REAL_MODE" = true ]; then
    echo "🔐 Mode INTÉGRATION RÉELLE — vrais services Google"
    echo ""
    preflight_real
    # Consommé par l'interpolation ${USE_MOCKS:-true} de docker-compose.yml.
    export USE_MOCKS=false
else
    echo "🎭 Mode MOCK — services Google et OIDC simulés, données fictives"
    echo "   (pour l'intégration réelle depuis l'hôte : ./run_local.sh --real)"
    echo ""
    export USE_MOCKS=true
fi

echo "🚀 Starting CLEF Development Environment..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker compose is available
if ! docker compose version > /dev/null 2>&1; then
    echo "❌ Error: 'docker compose' is not available. Please update Docker and try again."
    exit 1
fi

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker compose down

# Build and start services
echo "🔨 Building and starting services..."
docker compose up --build -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
echo ""

# Wait for Redis
echo -n "  Redis: "
for i in {1..30}; do
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo "✅ Ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "❌ Timeout"
        exit 1
    fi
    sleep 1
done

# Wait for Backend
echo -n "  Backend: "
for i in {1..60}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Ready"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "❌ Timeout"
        exit 1
    fi
    sleep 1
done

# Wait for Frontend
echo -n "  Frontend: "
for i in {1..90}; do
    if curl -f http://localhost:4200 > /dev/null 2>&1; then
        echo "✅ Ready"
        break
    fi
    if [ "$i" -eq 90 ]; then
        echo "❌ Timeout (Frontend may still be compiling)"
        break
    fi
    sleep 1
done

echo ""
echo "✅ CLEF Development Environment is running!"
echo ""
echo "📍 Services:"
echo "  - Frontend:  http://localhost:4200"
echo "  - Backend:   http://localhost:8000"
echo "  - API Docs:  http://localhost:8000/docs"
echo "  - Redis:     localhost:6379"
echo ""
echo "📝 Useful commands:"
echo "  - View logs:        docker compose logs -f"
echo "  - View logs (service): docker compose logs -f [frontend|backend|redis]"
echo "  - Stop services:    docker compose down"
echo "  - Restart service:  docker compose restart [frontend|backend|redis]"
echo ""
echo "🔄 Hot-reload is enabled for both frontend and backend"
echo ""

