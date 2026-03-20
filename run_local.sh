#!/bin/bash

# CLEF - Local Development Environment Launcher
# This script starts the entire development stack using Docker Compose

set -e

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

# Wait for Valkey
echo -n "  Valkey: "
for i in {1..30}; do
    if docker compose exec -T valkey valkey-cli ping > /dev/null 2>&1; then
        echo "✅ Ready"
        break
    fi
    if [ $i -eq 30 ]; then
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
    if [ $i -eq 60 ]; then
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
    if [ $i -eq 90 ]; then
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
echo "  - Valkey:    localhost:6379"
echo ""
echo "📝 Useful commands:"
echo "  - View logs:        docker compose logs -f"
echo "  - View logs (service): docker compose logs -f [frontend|backend|valkey]"
echo "  - Stop services:    docker compose down"
echo "  - Restart service:  docker compose restart [frontend|backend|valkey]"
echo ""
echo "🔄 Hot-reload is enabled for both frontend and backend"
echo ""

