#!/bin/bash
# Pull latest code and restart all AWS services
# Run from /opt/psx-chatbot: bash deploy/aws-update.sh
set -e

cd /opt/psx-chatbot

echo "Pulling latest code..."
git pull origin main

echo "Building and restarting services..."
docker compose -f docker-compose.aws.yml --env-file .env.prod up -d --build

echo "Waiting for health check..."
sleep 20
docker compose -f docker-compose.aws.yml --env-file .env.prod ps

echo ""
echo "Backend health:"
curl -s http://localhost/health | python3 -m json.tool || echo "Not ready yet — wait 30s and retry"
