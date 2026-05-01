#!/bin/bash
# AWS EC2 Ubuntu 22.04 — one-time setup script
# Run as: sudo bash aws-setup.sh  (from anywhere)
set -e

DOMAIN="psx-chatbot.duckdns.org"
EMAIL="samad.x747@gmail.com"
APP_DIR="/opt/psx-chatbot"
REPO_URL="https://github.com/maryamfaizan53/watspapp-rag-tool.git"

echo "========================================"
echo " PSX RAG Chatbot — AWS Ubuntu Setup"
echo "========================================"

# ── 1. System update ─────────────────────────────────────────────────────
echo "[1/7] Updating system packages..."
apt-get update -y
apt-get install -y curl git ca-certificates certbot

# ── 2. Install Docker ────────────────────────────────────────────────────
echo "[2/7] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    echo "Docker installed"
else
    echo "Docker already installed — skipping"
fi
systemctl enable --now docker

# ── 3. Clone repo ────────────────────────────────────────────────────────
echo "[3/7] Cloning repository..."
mkdir -p "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
    git clone "$REPO_URL" "$APP_DIR"
else
    cd "$APP_DIR" && git pull origin main
fi
cd "$APP_DIR"

mkdir -p indexes certbot/certs certbot/www
chown -R ubuntu:ubuntu "$APP_DIR"

# ── 4. Create .env.prod ──────────────────────────────────────────────────
echo "[4/7] Checking .env.prod..."
if [ ! -f "$APP_DIR/.env.prod" ]; then
    cp "$APP_DIR/.env.prod.example" "$APP_DIR/.env.prod"
    AWS_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_AWS_IP")
    sed -i "s|FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|" "$APP_DIR/.env.prod"
    sed -i "s|VITE_API_URL=.*|VITE_API_URL=https://$DOMAIN|" "$APP_DIR/.env.prod"
    sed -i "s|GEMINI_MODEL=.*|GEMINI_MODEL=gemini-2.0-flash|" "$APP_DIR/.env.prod"
    sed -i "s|EMBEDDING_MODEL=.*|EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2|" "$APP_DIR/.env.prod"
    echo ""
    echo "  *** ACTION REQUIRED — edit .env.prod before continuing ***"
    echo "  nano $APP_DIR/.env.prod"
    echo ""
    echo "  Mandatory values to fill in:"
    echo "    POSTGRES_PASSWORD   — any strong password"
    echo "    JWT_SECRET          — run: openssl rand -hex 32"
    echo "    ENCRYPTION_KEY      — run: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo "    GEMINI_API_KEY      — your Gemini key"
    echo "    OPENAI_API_KEY      — your OpenAI key (for fallback)"
    echo "    LLM_PROVIDER        — openai  (primary=OpenAI, fallback=Gemini)"
    echo "    SEED_ADMIN_EMAIL    — admin login email"
    echo "    SEED_ADMIN_PASSWORD — admin login password"
    echo ""
    echo "  When done, re-run this script (it will skip steps already done)."
    exit 0
else
    echo ".env.prod already exists — continuing"
fi

# Load POSTGRES_PASSWORD for docker compose
set -a; source "$APP_DIR/.env.prod"; set +a

# ── 5. Get Let's Encrypt cert ────────────────────────────────────────────
echo "[5/7] Getting Let's Encrypt certificate for $DOMAIN..."
if [ ! -f "$APP_DIR/certbot/certs/live/$DOMAIN/fullchain.pem" ]; then
    # Bootstrap nginx (HTTP only) so certbot can complete the ACME challenge
    docker run --rm -d \
        --name certbot_nginx \
        -p 80:80 \
        -v "$APP_DIR/nginx/aws-bootstrap.conf:/etc/nginx/conf.d/default.conf:ro" \
        -v "$APP_DIR/certbot/www:/var/www/certbot:ro" \
        nginx:alpine

    sleep 3

    # Run certbot standalone via webroot (nginx serves the challenge)
    certbot certonly \
        --webroot \
        --webroot-path="$APP_DIR/certbot/www" \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN" \
        --cert-path "$APP_DIR/certbot/certs"

    # certbot writes to /etc/letsencrypt by default — move to our path
    if [ -d "/etc/letsencrypt/live/$DOMAIN" ] && [ ! -d "$APP_DIR/certbot/certs/live" ]; then
        cp -rL /etc/letsencrypt/. "$APP_DIR/certbot/certs/"
    fi

    docker stop certbot_nginx || true
    echo "Certificate obtained successfully"
else
    echo "Certificate already exists — skipping"
fi

# ── 6. Set up cert auto-renewal ──────────────────────────────────────────
echo "[6/7] Setting up certificate auto-renewal..."
cat > /etc/cron.d/certbot-renew << 'EOF'
0 3 * * * root certbot renew --quiet --deploy-hook "cp -rL /etc/letsencrypt/. /opt/psx-chatbot/certbot/certs/ && docker restart psx_nginx" 2>&1 | logger -t certbot
EOF
chmod 644 /etc/cron.d/certbot-renew
echo "Auto-renewal cron installed (runs daily at 3 AM)"

# ── 7. Start full stack ──────────────────────────────────────────────────
echo "[7/7] Starting full stack..."
cd "$APP_DIR"
docker compose -f docker-compose.aws.yml --env-file .env.prod up -d --build

echo ""
echo "Waiting 30s for services to start..."
sleep 30
docker compose -f docker-compose.aws.yml --env-file .env.prod ps

echo ""
echo "========================================"
echo " Setup complete!"
echo "========================================"
echo " App URL:  https://$DOMAIN"
echo " Health:   https://$DOMAIN/health"
echo ""
echo " NEXT STEPS:"
echo "  1. Update DuckDNS to point to this server's IP:"
echo "     https://www.duckdns.org/domains"
echo "     Set $DOMAIN → $(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_AWS_IP')"
echo ""
echo "  2. Seed the admin user:"
echo "     docker exec psx_backend python scripts/seed_admin.py"
echo ""
echo "  3. Telegram and WhatsApp webhooks stay the same URL (same domain)"
echo "     Just re-register them if they were pointing to old IP directly."
echo ""
