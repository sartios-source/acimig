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

echo -e "${RED}=========================================="
echo "ACI Migrator POC - Destroy Infrastructure"
echo -e "==========================================${NC}"
echo ""

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

# Display current resources
display_resources() {
    log_info "Current resources:"
    cd "$SCRIPT_DIR/terraform"

    if [ -f "terraform.tfstate" ]; then
        terraform show
    else
        log_warning "No Terraform state found"
        exit 0
    fi

    cd "$SCRIPT_DIR"
}

# Destroy infrastructure
destroy_infrastructure() {
    log_warning "This will destroy all GCP resources created by Terraform"
    log_warning "This action cannot be undone!"
    echo ""

    read -p "Are you sure you want to destroy all resources? (type 'yes' to confirm): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Destroy cancelled"
        exit 0
    fi

    echo ""
    read -p "Final confirmation - destroy everything? (type 'destroy' to confirm): " final_confirm

    if [ "$final_confirm" != "destroy" ]; then
        log_info "Destroy cancelled"
        exit 0
    fi

    log_info "Destroying infrastructure..."
    cd "$SCRIPT_DIR/terraform"

    terraform destroy -auto-approve

    log_success "Infrastructure destroyed"

    cd "$SCRIPT_DIR"
}

# Cleanup local files
cleanup_files() {
    log_info "Cleaning up local files..."

    # Remove generated files
    rm -f "$SCRIPT_DIR/terraform-outputs.json"
    rm -f "$SCRIPT_DIR/scripts/setup-aci-simulator-final.sh"
    rm -f "$SCRIPT_DIR/scripts/setup-mcp-server-final.sh"
    rm -f "$SCRIPT_DIR/aci-config/test-data/mock_data.json"

    log_success "Local files cleaned up"
}

# Display summary
display_summary() {
    echo ""
    echo -e "${GREEN}=========================================="
    echo "Cleanup Complete!"
    echo -e "==========================================${NC}"
    echo ""
    log_success "All GCP resources have been destroyed"
    log_success "Local files have been cleaned up"
    echo ""
    log_info "To deploy again, run: ./deploy.sh"
    echo ""
}

# Main execution
main() {
    display_resources
    destroy_infrastructure
    cleanup_files
    display_summary
}

# Run main function
main "$@"
