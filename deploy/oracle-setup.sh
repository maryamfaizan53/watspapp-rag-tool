#!/bin/bash
# Oracle Cloud Free Tier — one-time VM setup script
# Run as: sudo bash oracle-setup.sh
# Tested on Ubuntu 22.04 ARM (Ampere A1)
set -e

echo "======================================"
echo " PSX RAG Chatbot — Oracle Cloud Setup"
echo "======================================"

# ── 1. System update ──────────────────────────────────────────────────────
echo "[1/6] Updating system packages..."
apt-get update -y && apt-get upgrade -y
apt-get install -y curl git unzip ca-certificates gnupg lsb-release

# ── 2. Install Docker ─────────────────────────────────────────────────────
echo "[2/6] Installing Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group (so sudo isn't needed later)
SUDO_USER_NAME=${SUDO_USER:-ubuntu}
usermod -aG docker "$SUDO_USER_NAME" || true
systemctl enable docker
systemctl start docker

# ── 3. Open firewall ports ────────────────────────────────────────────────
echo "[3/6] Configuring firewall (iptables)..."
# Oracle Cloud VMs have iptables rules blocking all ports except 22
# These rules open HTTP (80) and HTTPS (443)
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
# Persist rules across reboots
apt-get install -y iptables-persistent
netfilter-persistent save

# ── 4. Create deployment directory ────────────────────────────────────────
echo "[4/6] Creating deployment directory..."
mkdir -p /opt/psx-chatbot
cd /opt/psx-chatbot

# Clone repo (replace with your repo URL if forked)
if [ ! -d ".git" ]; then
    git clone https://github.com/maryamfaizan53/watspapp-rag-tool.git .
else
    echo "Repo already cloned — skipping clone."
fi

mkdir -p indexes nginx/ssl

# ── 5. Create .env.prod ───────────────────────────────────────────────────
echo "[5/6] Setting up environment..."
if [ ! -f ".env.prod" ]; then
    cp .env.prod.example .env.prod
    echo ""
    echo "  *** IMPORTANT ***"
    echo "  Edit /opt/psx-chatbot/.env.prod before starting:"
    echo "    - Set POSTGRES_PASSWORD"
    echo "    - Set JWT_SECRET (run: python3 -c \"import secrets; print(secrets.token_hex(32))\")"
    echo "    - Set ENCRYPTION_KEY (run: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
    echo "    - Set GEMINI_API_KEY"
    echo "    - Set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD"
    echo "    - Set FRONTEND_URL and VITE_API_URL to http://$(curl -s ifconfig.me)"
    echo ""
else
    echo ".env.prod already exists — skipping."
fi

# ── 6. Done ───────────────────────────────────────────────────────────────
echo "[6/6] Setup complete!"
echo ""
echo "Your Oracle VM public IP: $(curl -s ifconfig.me)"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/psx-chatbot/.env.prod with your credentials"
echo "  2. Run: cd /opt/psx-chatbot && bash deploy/oracle-update.sh"
echo "  3. Access your app at: http://$(curl -s ifconfig.me)"
echo ""
echo "Remember to open port 80 and 443 in Oracle Cloud Security List:"
echo "  OCI Console → Networking → Virtual Cloud Networks → Security Lists → Add Ingress Rule"
