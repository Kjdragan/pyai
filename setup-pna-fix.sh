#!/bin/bash
# Setup script for PNA (Private Network Access) fix
# This script installs prerequisites and generates SSL certificates

set -e  # Exit on any error

echo "🛠 Setting up PNA fix for localhost access..."

# Create necessary directories
mkdir -p certs logs

# Check if running on WSL/Ubuntu
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS=$NAME
    echo "Detected OS: $OS"
fi

# Install Caddy
echo "📦 Installing Caddy..."
if command -v caddy &> /dev/null; then
    echo "✅ Caddy already installed: $(caddy version)"
else
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        # Ubuntu/Debian installation
        sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
        sudo apt update && sudo apt install caddy
    else
        # Generic Linux - download binary
        echo "Downloading Caddy binary..."
        curl -JLO "https://github.com/caddyserver/caddy/releases/latest/download/caddy_linux_amd64.tar.gz"
        tar -xzf caddy_linux_amd64.tar.gz
        sudo mv caddy /usr/local/bin/
        rm caddy_linux_amd64.tar.gz
    fi
    echo "✅ Caddy installed successfully"
fi

# Install mkcert
echo "🔐 Installing mkcert..."
if command -v mkcert &> /dev/null; then
    echo "✅ mkcert already installed: $(mkcert -version)"
else
    # Download mkcert binary
    curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
    chmod +x mkcert-v*-linux-amd64
    sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
    echo "✅ mkcert installed successfully"
fi

# Setup local CA and generate certificates
echo "🔑 Setting up SSL certificates..."
mkcert -install
mkcert -key-file certs/localhost-key.pem -cert-file certs/localhost.pem localhost 127.0.0.1 ::1

echo "✅ SSL certificates generated in certs/ directory"

# Make scripts executable
chmod +x start-with-proxy.sh 2>/dev/null || true
chmod +x stop-proxy.sh 2>/dev/null || true

echo ""
echo "🎉 PNA fix setup complete!"
echo ""
echo "Next steps:"
echo "1. Run './start-with-proxy.sh' to start your app with the proxy"
echo "2. Access your app at: https://localhost:8443"
echo "3. Your app will be accessible from public websites without PNA errors"
echo ""
echo "Files created:"
echo "- Caddyfile (proxy configuration)"
echo "- certs/localhost.pem & certs/localhost-key.pem (SSL certificates)"
echo "- logs/ directory for Caddy logs"
