#!/bin/bash
# Pull latest code and restart all services
# Run from /opt/psx-chatbot: bash deploy/oracle-update.sh
set -e

cd /opt/psx-chatbot

echo "Pulling latest code..."
git pull origin main

echo "Building and restarting services..."
docker compose -f docker-compose.oracle.yml --env-file .env.prod pull --ignore-pull-failures || true
docker compose -f docker-compose.oracle.yml --env-file .env.prod up -d --build

echo "Waiting for health check..."
sleep 15
docker compose -f docker-compose.oracle.yml --env-file .env.prod ps

echo ""
echo "Done. Backend health:"
curl -s http://localhost/health | python3 -m json.tool || echo "Health check not ready yet — wait 30s and retry"
