# CLEF - Docker Development Environment

This document describes the local development environment setup using Docker Compose.

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- At least 4GB of RAM allocated to Docker
- Ports 4200, 8000, and 6379 available

## Quick Start

```bash
./run_local.sh
```

This script will:

1. Stop any existing containers
2. Build and start all services (frontend, backend, redis)
3. Wait for services to be healthy
4. Display access URLs

## Services

### Frontend (Angular 21)

- **URL**: [http://localhost:4200](http://localhost:4200)
- **Port**: 4200
- **Hot-reload**: Enabled (file changes trigger automatic rebuild)
- **Container**: clef-frontend

### Backend (FastAPI + Python 3.13)

- **URL**: [http://localhost:8000](http://localhost:8000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Port**: 8000
- **Hot-reload**: Enabled (uvicorn --reload)
- **Container**: clef-backend

### Redis (Mock MemoryStore)

- **Port**: 6379
- **Container**: clef-redis
- **Persistence**: Enabled (AOF)
- **Health check**: redis-cli ping

## Manual Commands

### Start services

```bash
docker-compose up -d
```

### Stop services

```bash
docker-compose down
```

### View logs (all services)

```bash
docker-compose logs -f
```

### View logs (specific service)

```bash
docker-compose logs -f frontend
docker-compose logs -f backend
docker-compose logs -f redis
```

### Restart a service

```bash
docker-compose restart backend
```

### Rebuild a service

```bash
docker-compose up -d --build backend
```

### Access Redis CLI

```bash
docker-compose exec redis redis-cli
```

### Access backend shell

```bash
docker-compose exec backend bash
```

### Access frontend shell

```bash
docker-compose exec frontend sh
```

## Volume Mounts

- **Frontend**: `./frontend` → `/app` (with node_modules excluded)
- **Backend**: `./backend` → `/app`
- **Redis**: Named volume for data persistence

## Environment Variables

Copy `.env.example` to `.env` and configure as needed:

```bash
cp .env.example .env
```

## Troubleshooting

### Port already in use

If you get a port conflict error, check what's using the port:

```bash
lsof -i :4200  # Frontend
lsof -i :8000  # Backend
lsof -i :6379  # Redis
```

### Frontend not compiling

The Angular dev server can take 1-2 minutes on first start. Check logs:

```bash
docker-compose logs -f frontend
```

### Backend not starting

Check if Redis is healthy:

```bash
docker-compose ps
docker-compose logs redis
```

### Clear everything and start fresh

```bash
docker-compose down -v  # Remove volumes too
./run_local.sh
```

## Development Workflow

1. Start the environment: `./run_local.sh`
2. Make changes to code in `frontend/` or `backend/`
3. Changes are automatically detected and services reload
4. Access frontend at [http://localhost:4200](http://localhost:4200)
5. Access backend API docs at [http://localhost:8000/docs](http://localhost:8000/docs)
6. Stop when done: `docker-compose down`

## Next Steps

- Configure Google APIs credentials
- Configure Okta authentication
- Set up mock data for development
- Add integration tests