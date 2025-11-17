#!/bin/bash
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}=========================================="
echo "ACI Migrator POC - Zero-Touch Deployment"
echo -e "==========================================${NC}"
echo ""

# Function to print status messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI not found. Please install: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    log_success "gcloud CLI found"

    # Check terraform
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform not found. Please install: https://www.terraform.io/downloads"
        exit 1
    fi
    log_success "Terraform found"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.8+"
        exit 1
    fi
    log_success "Python 3 found"

    # Check if logged into gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "Not logged into gcloud. Run: gcloud auth login"
        exit 1
    fi
    log_success "Authenticated to gcloud"

    # Check for terraform.tfvars
    if [ ! -f "$SCRIPT_DIR/terraform/terraform.tfvars" ]; then
        log_warning "terraform.tfvars not found"
        log_info "Copying terraform.tfvars.example to terraform.tfvars"
        cp "$SCRIPT_DIR/terraform/terraform.tfvars.example" "$SCRIPT_DIR/terraform/terraform.tfvars"
        log_error "Please edit terraform/terraform.tfvars with your GCP project ID and settings"
        exit 1
    fi
    log_success "terraform.tfvars found"
}

# Prepare deployment files
prepare_files() {
    log_info "Preparing deployment files..."

    # Generate mock data
    log_info "Generating mock ACI data..."
    cd "$SCRIPT_DIR"
    python3 scripts/generate-mock-data.py > aci-config/test-data/mock_data.json
    log_success "Mock data generated"

    # Prepare setup scripts by embedding code
    log_info "Preparing setup scripts..."

    # Read mock APIC server code
    MOCK_APIC_CODE=$(cat mock-apic/server.py)
    MCP_SERVER_CODE=$(cat mcp-server/server.py)
    GENERATE_DATA_CODE=$(cat scripts/generate-mock-data.py)

    # Update setup-aci-simulator.sh with embedded code
    sed -e "/MOCK_APIC_PLACEHOLDER/r mock-apic/server.py" \
        -e "/MOCK_APIC_PLACEHOLDER/d" \
        -e "/GENERATE_DATA_PLACEHOLDER/r scripts/generate-mock-data.py" \
        -e "/GENERATE_DATA_PLACEHOLDER/d" \
        scripts/setup-aci-simulator.sh > scripts/setup-aci-simulator-final.sh

    # Update setup-mcp-server.sh with embedded code
    sed -e "/MCP_SERVER_PLACEHOLDER/r mcp-server/server.py" \
        -e "/MCP_SERVER_PLACEHOLDER/d" \
        scripts/setup-mcp-server.sh > scripts/setup-mcp-server-final.sh

    chmod +x scripts/setup-aci-simulator-final.sh
    chmod +x scripts/setup-mcp-server-final.sh

    # Copy final scripts to terraform directory for use
    cp scripts/setup-aci-simulator-final.sh scripts/setup-aci-simulator.sh
    cp scripts/setup-mcp-server-final.sh scripts/setup-mcp-server.sh

    log_success "Setup scripts prepared"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying GCP infrastructure with Terraform..."

    cd "$SCRIPT_DIR/terraform"

    # Initialize Terraform
    log_info "Initializing Terraform..."
    terraform init

    # Plan
    log_info "Creating Terraform plan..."
    terraform plan -out=tfplan

    # Ask for confirmation
    echo ""
    read -p "Deploy infrastructure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_warning "Deployment cancelled"
        exit 0
    fi

    # Apply
    log_info "Applying Terraform configuration..."
    terraform apply tfplan

    log_success "Infrastructure deployed"

    # Save outputs
    terraform output -json > "$SCRIPT_DIR/terraform-outputs.json"

    cd "$SCRIPT_DIR"
}

# Wait for VMs to be ready
wait_for_vms() {
    log_info "Waiting for VMs to be ready..."

    # Get VM names from Terraform
    ACI_VM=$(terraform -chdir=terraform output -raw ssh_aci_simulator | awk '{print $4}')
    MCP_VM=$(terraform -chdir=terraform output -raw ssh_mcp_server | awk '{print $4}')
    ZONE=$(terraform -chdir=terraform output -json | jq -r '.ssh_aci_simulator.value' | awk '{print $5}' | sed 's/--zone=//')

    log_info "Waiting for VMs to accept SSH connections..."

    # Wait for ACI simulator VM
    log_info "Checking ACI Simulator VM..."
    for i in {1..30}; do
        if gcloud compute ssh "$ACI_VM" --zone="$ZONE" --command="echo 'VM ready'" &> /dev/null; then
            log_success "ACI Simulator VM is ready"
            break
        fi
        echo -n "."
        sleep 10
    done

    # Wait for MCP server VM
    log_info "Checking MCP Server VM..."
    for i in {1..30}; do
        if gcloud compute ssh "$MCP_VM" --zone="$ZONE" --command="echo 'VM ready'" &> /dev/null; then
            log_success "MCP Server VM is ready"
            break
        fi
        echo -n "."
        sleep 10
    done

    log_success "All VMs are ready"
}

# Monitor startup scripts
monitor_startup() {
    log_info "Monitoring startup script execution..."
    log_info "This may take 5-10 minutes..."

    # Get connection info
    ACI_IP=$(terraform -chdir=terraform output -raw aci_simulator_external_ip)
    MCP_IP=$(terraform -chdir=terraform output -raw mcp_server_external_ip)
    MCP_PORT=$(terraform -chdir=terraform output -json | jq -r '.mcp_server_url.value' | sed 's/.*://' | sed 's/\/$//')

    # Wait for Mock APIC
    log_info "Waiting for Mock APIC to start..."
    for i in {1..60}; do
        if curl -k -s https://$ACI_IP/health &> /dev/null; then
            log_success "Mock APIC is running"
            break
        fi
        echo -n "."
        sleep 5
    done

    # Wait for MCP Server
    log_info "Waiting for MCP Server to start..."
    for i in {1..60}; do
        if curl -s http://$MCP_IP:$MCP_PORT/health &> /dev/null; then
            log_success "MCP Server is running"
            break
        fi
        echo -n "."
        sleep 5
    done

    log_success "All services are running"
}

# Test the deployment
test_deployment() {
    log_info "Testing deployment..."

    ACI_IP=$(terraform -chdir=terraform output -raw aci_simulator_external_ip)
    MCP_IP=$(terraform -chdir=terraform output -raw mcp_server_external_ip)
    MCP_PORT=$(terraform -chdir=terraform output -json | jq -r '.mcp_server_url.value' | sed 's/.*://')

    # Test Mock APIC
    log_info "Testing Mock APIC..."
    APIC_RESPONSE=$(curl -k -s https://$ACI_IP/health)
    if echo "$APIC_RESPONSE" | jq -e '.status == "healthy"' &> /dev/null; then
        log_success "Mock APIC health check passed"
    else
        log_warning "Mock APIC health check failed"
    fi

    # Test MCP Server
    log_info "Testing MCP Server..."
    MCP_RESPONSE=$(curl -s http://$MCP_IP:$MCP_PORT/health)
    if echo "$MCP_RESPONSE" | jq -e '.status == "healthy"' &> /dev/null; then
        log_success "MCP Server health check passed"
    else
        log_warning "MCP Server health check failed"
    fi

    # Test MCP data retrieval
    log_info "Testing MCP data retrieval..."
    DATA_RESPONSE=$(curl -s http://$MCP_IP:$MCP_PORT/api/migrator/data)
    if echo "$DATA_RESPONSE" | jq -e '.fabric_name' &> /dev/null; then
        EPG_COUNT=$(echo "$DATA_RESPONSE" | jq '.epg_mappings | length')
        DEVICE_COUNT=$(echo "$DATA_RESPONSE" | jq '.devices | length')
        log_success "MCP data retrieval successful: $EPG_COUNT EPGs, $DEVICE_COUNT devices"
    else
        log_warning "MCP data retrieval failed"
    fi
}

# Display connection information
display_info() {
    echo ""
    echo -e "${GREEN}=========================================="
    echo "Deployment Complete!"
    echo -e "==========================================${NC}"
    echo ""

    # Display Terraform outputs
    terraform -chdir=terraform output connection_info

    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Wait 2-3 minutes for all services to fully initialize"
    echo "2. Test APIC: curl -k https://\$(terraform -chdir=terraform output -raw aci_simulator_external_ip)/health"
    echo "3. Test MCP: curl http://\$(terraform -chdir=terraform output -raw mcp_server_external_ip):5000/health"
    echo "4. Use MCP client in ACI Migrator to import data"
    echo ""
    echo -e "${YELLOW}Important:${NC}"
    echo "- Monitor GCP costs: https://console.cloud.google.com/billing"
    echo "- When done testing, run: ./destroy.sh"
    echo "- Estimated cost: ~\$3-5/day"
    echo ""
    echo -e "${GREEN}Connection details saved to: terraform-outputs.json${NC}"
    echo ""
}

# Main execution
main() {
    check_prerequisites
    prepare_files
    deploy_infrastructure
    wait_for_vms
    monitor_startup
    test_deployment
    display_info

    log_success "Zero-touch deployment complete!"
}

# Run main function
main "$@"
