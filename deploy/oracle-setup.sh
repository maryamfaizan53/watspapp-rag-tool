#!/bin/bash
# Oracle Cloud — one-time VM setup script for Oracle Linux 9
# Run as: sudo bash oracle-setup.sh
set -e

echo "======================================"
echo " PSX RAG Chatbot — Oracle Linux Setup"
echo "======================================"

# ── 1. System update ──────────────────────────────────────────────────────
echo "[1/6] Updating system packages..."
dnf update -y
dnf install -y curl git unzip ca-certificates

# ── 2. Install Docker ─────────────────────────────────────────────────────
echo "[2/6] Installing Docker..."
dnf install -y dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
usermod -aG docker opc
echo "Docker installed successfully"

# ── 3. Open firewall ports ────────────────────────────────────────────────
echo "[3/6] Configuring firewall..."
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=443/tcp
firewall-cmd --reload
echo "Ports 80 and 443 opened"

# ── 4. Create deployment directory ────────────────────────────────────────
echo "[4/6] Setting up deployment directory..."
mkdir -p /opt/psx-chatbot
cd /opt/psx-chatbot

if [ ! -d ".git" ]; then
    git clone https://github.com/maryamfaizan53/watspapp-rag-tool.git .
else
    echo "Repo already cloned — skipping."
fi

mkdir -p indexes nginx/ssl

chown -R opc:opc /opt/psx-chatbot

# ── 5. Create .env.prod ───────────────────────────────────────────────────
echo "[5/6] Setting up environment file..."
if [ ! -f ".env.prod" ]; then
    cp .env.prod.example .env.prod
    echo ""
    echo "  *** ACTION REQUIRED ***"
    echo "  Edit /opt/psx-chatbot/.env.prod with your credentials:"
    echo ""
    echo "  nano /opt/psx-chatbot/.env.prod"
    echo ""
    echo "  Values to fill in:"
    echo "    POSTGRES_PASSWORD   — any strong password"
    echo "    JWT_SECRET          — run: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    echo "    ENCRYPTION_KEY      — run: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo "    GEMINI_API_KEY      — your Gemini API key"
    echo "    SEED_ADMIN_EMAIL    — admin@aiagentixz.com"
    echo "    SEED_ADMIN_PASSWORD — your admin password"
    echo "    FRONTEND_URL        — http://84.235.255.224"
    echo "    VITE_API_URL        — http://84.235.255.224"
    echo ""
else
    echo ".env.prod already exists — skipping."
fi

# ── 6. Done ───────────────────────────────────────────────────────────────
echo "[6/6] Setup complete!"
echo ""
echo "Public IP: 84.235.255.224"
echo ""
echo "Next steps:"
echo "  1. sudo nano /opt/psx-chatbot/.env.prod"
echo "  2. sudo bash /opt/psx-chatbot/deploy/oracle-update.sh"
echo "  3. Visit: http://84.235.255.224"
