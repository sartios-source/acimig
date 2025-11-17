#!/bin/bash
set -e

echo "=========================================="
echo "Setting up MCP Server"
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
sudo apt-get install -y curl wget git jq

# Create mcp-server directory
echo "Creating application directory..."
sudo mkdir -p /opt/mcp-server
sudo chown -R $(whoami):$(whoami) /opt/mcp-server

# Create Python virtual environment
echo "Setting up Python virtual environment..."
python3.11 -m venv /opt/mcp-server/venv
source /opt/mcp-server/venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install aiohttp python-dotenv

# Download MCP server code
echo "Installing MCP server..."
# This will be populated by deploy script
cat > /opt/mcp-server/server.py << 'MCP_SERVER_EOF'
MCP_SERVER_PLACEHOLDER
MCP_SERVER_EOF

# Get ACI Simulator IP from metadata
APIC_IP=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/aci_simulator_ip" -H "Metadata-Flavor: Google")
MCP_PORT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/mcp_port" -H "Metadata-Flavor: Google" || echo "5000")

# Create environment file
echo "Creating environment configuration..."
cat > /opt/mcp-server/.env << EOF
APIC_URL=https://${APIC_IP}
APIC_USERNAME=admin
APIC_PASSWORD=C1sco12345
MCP_PORT=${MCP_PORT}
EOF

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/mcp-server.service > /dev/null << 'EOF'
[Unit]
Description=MCP Server for ACI Migrator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mcp-server
Environment="PATH=/opt/mcp-server/venv/bin"
EnvironmentFile=/opt/mcp-server/.env
ExecStart=/opt/mcp-server/venv/bin/python3 /opt/mcp-server/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "Starting MCP Server..."
sudo systemctl daemon-reload
sudo systemctl enable mcp-server
sudo systemctl start mcp-server

# Wait for service to be ready
echo "Waiting for MCP Server to be ready..."
sleep 5

# Test the service
echo "Testing MCP Server..."
for i in {1..30}; do
    if curl -s http://localhost:${MCP_PORT}/health 2>/dev/null; then
        echo "MCP Server is ready!"
        break
    fi
    echo "Waiting for MCP Server to start... (attempt $i/30)"
    sleep 2
done

# Display status
echo "=========================================="
echo "MCP Server Setup Complete!"
echo "=========================================="
sudo systemctl status mcp-server --no-pager
echo ""
echo "Service is running on http://$(curl -s ifconfig.me):${MCP_PORT}"
echo "Test with: curl http://$(curl -s ifconfig.me):${MCP_PORT}/health"
echo "=========================================="
