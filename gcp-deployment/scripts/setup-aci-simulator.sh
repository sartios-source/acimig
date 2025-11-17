#!/bin/bash
set -e

echo "=========================================="
echo "Setting up Mock APIC Server"
echo "=========================================="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.11
echo "Installing Python 3.11..."
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# Install required packages
echo "Installing system dependencies..."
sudo apt-get install -y \
    openssl \
    curl \
    wget \
    git \
    jq

# Create mock-apic directory
echo "Creating application directory..."
sudo mkdir -p /opt/mock-apic
sudo chown -R $(whoami):$(whoami) /opt/mock-apic

# Create Python virtual environment
echo "Setting up Python virtual environment..."
python3.11 -m venv /opt/mock-apic/venv
source /opt/mock-apic/venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install flask flask-cors gunicorn

# Generate self-signed SSL certificate
echo "Generating self-signed SSL certificate..."
openssl req -x509 -newkey rsa:4096 -nodes \
    -out /opt/mock-apic/cert.pem \
    -keyout /opt/mock-apic/key.pem \
    -days 365 \
    -subj "/C=US/ST=California/L=San Jose/O=POC/CN=mock-apic"

# Download mock APIC server code from GCS or copy from metadata
echo "Installing Mock APIC server..."
# This will be populated by deploy script
cat > /opt/mock-apic/server.py << 'MOCK_APIC_EOF'
MOCK_APIC_PLACEHOLDER
MOCK_APIC_EOF

# Download/generate mock data
echo "Generating mock ACI data..."
# This will be populated by deploy script
cat > /opt/mock-apic/generate_data.py << 'GENERATE_DATA_EOF'
GENERATE_DATA_PLACEHOLDER
GENERATE_DATA_EOF

python3 /opt/mock-apic/generate_data.py > /opt/mock-apic/mock_data.json

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/mock-apic.service > /dev/null << 'EOF'
[Unit]
Description=Mock APIC Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mock-apic
Environment="PATH=/opt/mock-apic/venv/bin"
ExecStart=/opt/mock-apic/venv/bin/python3 /opt/mock-apic/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "Starting Mock APIC service..."
sudo systemctl daemon-reload
sudo systemctl enable mock-apic
sudo systemctl start mock-apic

# Wait for service to be ready
echo "Waiting for Mock APIC to be ready..."
sleep 5

# Test the service
echo "Testing Mock APIC service..."
for i in {1..30}; do
    if curl -k https://localhost/health 2>/dev/null; then
        echo "Mock APIC is ready!"
        break
    fi
    echo "Waiting for Mock APIC to start... (attempt $i/30)"
    sleep 2
done

# Display status
echo "=========================================="
echo "Mock APIC Setup Complete!"
echo "=========================================="
sudo systemctl status mock-apic --no-pager
echo ""
echo "Service is running on https://$(curl -s ifconfig.me):443"
echo "Test with: curl -k https://$(curl -s ifconfig.me)/health"
echo "=========================================="
