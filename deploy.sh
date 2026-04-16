#!/bin/bash
# PSX RAG Chatbot — Oracle Cloud VM Deployment Script
# Run this on your Oracle Cloud ARM VM (Ubuntu 22.04)
# Usage: bash deploy.sh

set -e

echo "=== PSX RAG Chatbot Deployment ==="

# ── 1. Install Docker ─────────────────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "[1/6] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in."
else
    echo "[1/6] Docker already installed."
fi

# ── 2. Install Docker Compose ─────────────────────────────────────────────────
if ! command -v docker compose &> /dev/null; then
    echo "[2/6] Installing Docker Compose plugin..."
    sudo apt-get update -q
    sudo apt-get install -y docker-compose-plugin
else
    echo "[2/6] Docker Compose already installed."
fi

# ── 3. Check .env.prod exists ─────────────────────────────────────────────────
echo "[3/6] Checking environment config..."
if [ ! -f ".env.prod" ]; then
    echo "ERROR: .env.prod not found!"
    echo "Copy .env.prod.example → .env.prod and fill in your credentials."
    exit 1
fi

# Load VITE_API_URL for frontend build arg
export $(grep VITE_API_URL .env.prod | xargs)

# ── 4. Create indexes directory ───────────────────────────────────────────────
echo "[4/6] Setting up directories..."
mkdir -p indexes
chmod 777 indexes

# ── 5. Build and start containers ─────────────────────────────────────────────
echo "[5/6] Building and starting containers..."
docker compose -f docker-compose.prod.yml --env-file .env.prod \
    build --build-arg VITE_API_URL=$VITE_API_URL

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# ── 6. Seed admin user ────────────────────────────────────────────────────────
echo "[6/6] Seeding admin user..."
sleep 10
docker exec psx_backend python scripts/seed_admin.py || echo "Admin may already exist, skipping."

echo ""
echo "=== Deployment Complete ==="
echo "Backend:  http://$(curl -s ifconfig.me):8080"
echo "Frontend: http://$(curl -s ifconfig.me)"
echo ""
echo "Next steps:"
echo "  1. Update WhatsApp webhook URL in Meta dashboard"
echo "  2. Re-register Telegram webhook with new URL"
echo "  3. Log in at http://$(curl -s ifconfig.me) with your admin credentials"
