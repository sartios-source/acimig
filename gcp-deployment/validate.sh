#!/bin/bash
# Validation script for ACI Migrator POC deployment
# Checks that all required files and configurations are present

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERRORS=0
WARNINGS=0

echo -e "${BLUE}=========================================="
echo "ACI Migrator POC - Deployment Validation"
echo -e "==========================================${NC}\n"

check_file() {
    local file=$1
    local required=${2:-true}

    if [ -f "$SCRIPT_DIR/$file" ]; then
        echo -e "${GREEN}[OK]${NC} $file"
    else
        if [ "$required" = "true" ]; then
            echo -e "${RED}[ERROR]${NC} Missing required file: $file"
            ((ERRORS++))
        else
            echo -e "${YELLOW}[WARN]${NC} Optional file missing: $file"
            ((WARNINGS++))
        fi
    fi
}

check_executable() {
    local file=$1

    if [ -f "$SCRIPT_DIR/$file" ]; then
        if [ -x "$SCRIPT_DIR/$file" ]; then
            echo -e "${GREEN}[OK]${NC} $file (executable)"
        else
            echo -e "${YELLOW}[WARN]${NC} $file exists but not executable (run: chmod +x $file)"
            ((WARNINGS++))
        fi
    else
        echo -e "${RED}[ERROR]${NC} Missing executable: $file"
        ((ERRORS++))
    fi
}

echo "Checking deployment scripts..."
check_executable "deploy.sh"
check_executable "destroy.sh"

echo -e "\nChecking Terraform files..."
check_file "terraform/main.tf"
check_file "terraform/variables.tf"
check_file "terraform/outputs.tf"
check_file "terraform/terraform.tfvars.example"
check_file "terraform/terraform.tfvars" false

echo -e "\nChecking server implementations..."
check_file "mock-apic/server.py"
check_file "mcp-server/server.py"
check_file "mcp-server/requirements.txt"

echo -e "\nChecking automation scripts..."
check_file "scripts/setup-aci-simulator.sh"
check_file "scripts/setup-mcp-server.sh"
check_file "scripts/generate-mock-data.py"
check_file "scripts/configure-aci-data.py"
check_file "scripts/test-mcp-integration.py"

echo -e "\nChecking configuration files..."
check_file "aci-config/sample-topology.json"
check_file "config.yaml"

echo -e "\nChecking documentation..."
check_file "README.md"
check_file "QUICKSTART.md"
check_file "COST_ESTIMATE.md"
check_file "DEPLOYMENT_SUMMARY.md"

echo -e "\nChecking prerequisites..."

# Check gcloud
if command -v gcloud &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} gcloud CLI installed"
else
    echo -e "${YELLOW}[WARN]${NC} gcloud CLI not found (required for deployment)"
    ((WARNINGS++))
fi

# Check terraform
if command -v terraform &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} Terraform installed"
else
    echo -e "${YELLOW}[WARN]${NC} Terraform not found (required for deployment)"
    ((WARNINGS++))
fi

# Check python3
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} Python 3 installed"
else
    echo -e "${YELLOW}[WARN]${NC} Python 3 not found (required for deployment)"
    ((WARNINGS++))
fi

# Check jq
if command -v jq &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} jq installed"
else
    echo -e "${YELLOW}[WARN]${NC} jq not found (recommended for testing)"
    ((WARNINGS++))
fi

# Summary
echo -e "\n${BLUE}=========================================="
echo "Validation Summary"
echo -e "==========================================${NC}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "Ready to deploy."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}✓ All required files present${NC}"
    echo -e "${YELLOW}⚠ $WARNINGS warnings${NC}"
    echo "Deployment may work but some features may be limited."
    exit 0
else
    echo -e "${RED}✗ $ERRORS errors found${NC}"
    echo -e "${YELLOW}⚠ $WARNINGS warnings${NC}"
    echo "Please fix errors before deploying."
    exit 1
fi
