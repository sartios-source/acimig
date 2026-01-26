# ACI Migrator POC - Zero-Touch GCP Deployment

Note: This GCP deployment is optional. For local MCP testing without VMs, run the MCP server in mock mode from the repo root.

Complete automation for deploying a Cisco ACI Simulator with MCP server integration on Google Cloud Platform for ACI Migrator testing.

## Overview

This deployment creates a complete testing environment with:

- **Mock APIC Server**: Simulates Cisco APIC REST API with realistic test data
- **MCP Server**: Middleware server that queries ACI data and transforms it for ACI Migrator
- **Automated Infrastructure**: Terraform-managed GCP resources
- **Zero-Touch Deployment**: Single command deployment from start to finish

## Architecture

```
Internet
    |
    v
[GCP VPC - 10.0.1.0/24]
    |
    +-- [Mock APIC VM] (n1-standard-4: 4 vCPU, 15GB RAM)
    |       |
    |       +-- Python Flask Mock APIC (HTTPS:443)
    |       +-- Sample ACI Configuration
    |       |   - 2 Spines, 4 Leafs, 8 FEX
    |       |   - 3 Tenants (prod, dev, mgmt)
    |       |   - 20+ EPGs with realistic configs
    |       +-- SSL Certificate (self-signed)
    |
    +-- [MCP Server VM] (n1-standard-2: 2 vCPU, 7.5GB RAM)
    |       |
    |       +-- Python MCP Server (HTTP:5000)
    |       +-- ACI REST API Client
    |       +-- Data Transformer
    |       +-- Analysis Engine
    |
    +-- [Your Local Machine]
            |
            +-- ACI Migrator Application
            +-- MCP Client Integration
```

## Prerequisites

### Required Tools

1. **Google Cloud SDK** (`gcloud`)
   ```bash
   # Install: https://cloud.google.com/sdk/docs/install
   gcloud --version  # Verify installation
   ```

2. **Terraform** (>= 1.0)
   ```bash
   # Install: https://www.terraform.io/downloads
   terraform --version  # Verify installation
   ```

3. **Python 3.8+**
   ```bash
   python3 --version  # Verify installation
   ```

4. **jq** (for JSON processing)
   ```bash
   # macOS: brew install jq
   # Ubuntu: apt-get install jq
   # Windows: choco install jq
   ```

### GCP Setup

1. **GCP Account**: Active Google Cloud account
2. **Project**: Create or use existing GCP project
3. **Billing**: Billing enabled on project
4. **Authentication**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

5. **APIs**: Enable required APIs
   ```bash
   gcloud services enable compute.googleapis.com
   gcloud services enable servicenetworking.googleapis.com
   ```

## Quick Start

### 1. Clone and Configure

```bash
cd gcp-deployment

# Copy example config
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# Edit with your settings
nano terraform/terraform.tfvars
```

**Required Configuration:**
```hcl
# terraform/terraform.tfvars
project_id = "your-gcp-project-id"
region     = "us-central1"
zone       = "us-central1-a"

# IMPORTANT: Restrict to your IP for security
# Find your IP: curl ifconfig.me
allowed_source_ips = ["YOUR.IP.ADDRESS/32"]
```

### 2. Deploy Everything

```bash
# Make deployment script executable
chmod +x deploy.sh

# Run zero-touch deployment
./deploy.sh
```

The script will:
1. Validate prerequisites
2. Generate mock ACI data
3. Deploy GCP infrastructure with Terraform
4. Wait for VMs to boot
5. Install and configure Mock APIC server
6. Install and configure MCP server
7. Test all components
8. Display connection information

**Deployment Time**: 10-15 minutes

### 3. Verify Deployment

After deployment completes, test the services:

```bash
# Get connection info
cd terraform
terraform output connection_info

# Test Mock APIC
APIC_IP=$(terraform output -raw aci_simulator_external_ip)
curl -k https://$APIC_IP/health

# Test MCP Server
MCP_IP=$(terraform output -raw mcp_server_external_ip)
curl http://$MCP_IP:5000/health

# Get migrator data
curl http://$MCP_IP:5000/api/migrator/data | jq .
```

## Using with ACI Migrator

### Method 1: Via Web UI (Recommended)

1. Start ACI Migrator application
2. Navigate to Upload page
3. Look for "Import from MCP Server" section
4. Enter MCP Server URL: `http://MCP_IP:5000`
5. Click "Test Connection"
6. Enter fabric name and click "Import"

### Method 2: Via API

```bash
# Test MCP connection
curl -X POST http://localhost:5000/api/mcp/test \
  -H "Content-Type: application/json" \
  -d '{"mcp_url": "http://MCP_IP:5000"}'

# Import data
curl -X POST http://localhost:5000/api/mcp/import \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_url": "http://MCP_IP:5000",
    "fabric_name": "gcp-poc-fabric"
  }'
```

### Method 3: Python Client

```python
from mcp_client import MCPClient

# Connect to MCP server
client = MCPClient('http://MCP_IP:5000')

# Test connection
health = client.health_check()
print(f"Server status: {health['status']}")

# Get migrator data
data = client.get_migrator_data()
print(f"Devices: {len(data['devices'])}")
print(f"EPGs: {len(data['epg_mappings'])}")

# Run analysis
analysis = client.analyze_fabric()
print(f"Recommendations: {len(analysis['recommendations'])}")
```

## Test Data

The deployment includes comprehensive test data:

### Fabric Topology
- **Spines**: 2 x N9K-C9364C
- **Leafs**: 4 x N9K-C93180YC-FX
- **FEX**: 8 x N2K-C2248TP (48 ports each)

### Tenants

1. **Production**
   - VRF: prod-vrf
   - BDs: web-bd, app-bd, db-bd
   - EPGs: web-epg (4 paths), app-epg (6 paths), db-epg (2 paths)
   - VLANs: 100, 101, 200, 201, 300

2. **Development**
   - VRF: dev-vrf
   - BDs: dev-bd
   - EPGs: dev-epg (4 paths)
   - VLANs: 500

3. **Management**
   - VRF: mgmt-vrf
   - BDs: mgmt-bd
   - EPGs: mgmt-epg (4 paths, one per leaf)
   - VLANs: 999

### Test Scenarios

The data is designed to test:

1. **High Coupling**: EPGs spanning multiple devices
2. **FEX Consolidation**: Underutilized FEX devices
3. **VLAN Analysis**: VLAN distribution and overlaps
4. **Multi-path EPGs**: EPGs with multiple paths
5. **Tenant Segmentation**: Multiple tenant configurations

## Management

### SSH Access

```bash
# SSH to Mock APIC VM
gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a

# SSH to MCP Server VM
gcloud compute ssh aci-migrator-poc-mcp-server --zone=us-central1-a
```

### Service Management

```bash
# On Mock APIC VM
sudo systemctl status mock-apic
sudo systemctl restart mock-apic
sudo journalctl -u mock-apic -f  # View logs

# On MCP Server VM
sudo systemctl status mcp-server
sudo systemctl restart mcp-server
sudo journalctl -u mcp-server -f  # View logs
```

### Update Configuration

```bash
# Update Mock APIC data
ssh aci-vm
sudo nano /opt/mock-apic/mock_data.json
sudo systemctl restart mock-apic

# Update MCP Server config
ssh mcp-vm
sudo nano /opt/mcp-server/.env
sudo systemctl restart mcp-server
```

### View Logs

```bash
# Mock APIC logs
gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a \
  --command="sudo journalctl -u mock-apic -f"

# MCP Server logs
gcloud compute ssh aci-migrator-poc-mcp-server --zone=us-central1-a \
  --command="sudo journalctl -u mcp-server -f"
```

## Troubleshooting

### Services Not Starting

```bash
# Check VM startup script status
gcloud compute instances get-serial-port-output INSTANCE_NAME \
  --zone=us-central1-a

# SSH and check logs
gcloud compute ssh INSTANCE_NAME --zone=us-central1-a
sudo journalctl -xe
```

### Connection Refused

```bash
# Check firewall rules
gcloud compute firewall-rules list | grep aci-migrator-poc

# Verify your IP is allowed
curl ifconfig.me  # Should match allowed_source_ips in terraform.tfvars

# Update firewall if needed
gcloud compute firewall-rules update aci-migrator-poc-allow-mcp \
  --source-ranges="YOUR.NEW.IP/32"
```

### Mock APIC Not Responding

```bash
# SSH to VM
gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a

# Check service status
sudo systemctl status mock-apic

# Check if running
sudo netstat -tlnp | grep 443

# Restart service
sudo systemctl restart mock-apic
```

### MCP Server Errors

```bash
# SSH to VM
gcloud compute ssh aci-migrator-poc-mcp-server --zone=us-central1-a

# Check logs
sudo journalctl -u mcp-server -n 100

# Test APIC connectivity
APIC_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/attributes/aci_simulator_ip -H "Metadata-Flavor: Google")
curl -k https://$APIC_IP/health
```

### Terraform Issues

```bash
# Refresh state
cd terraform
terraform refresh

# Check state
terraform show

# Re-apply if needed
terraform plan
terraform apply
```

## Cost Management

### Estimated Costs

See [COST_ESTIMATE.md](COST_ESTIMATE.md) for detailed breakdown.

**Summary:**
- Mock APIC VM: ~$0.15/hour ($3.60/day)
- MCP Server VM: ~$0.08/hour ($1.92/day)
- Networking: ~$0.05/day
- **Total: ~$5.50/day** or **~$165/month**

### Cost Optimization

1. **Stop VMs when not in use:**
   ```bash
   gcloud compute instances stop aci-migrator-poc-aci-simulator --zone=us-central1-a
   gcloud compute instances stop aci-migrator-poc-mcp-server --zone=us-central1-a
   ```

2. **Use smaller instance types:**
   ```hcl
   # In terraform.tfvars
   aci_simulator_machine_type = "n1-standard-2"  # Instead of n1-standard-4
   mcp_server_machine_type    = "n1-standard-1"  # Instead of n1-standard-2
   ```

3. **Delete when done:**
   ```bash
   ./destroy.sh
   ```

## Cleanup

### Full Cleanup

```bash
# Run destroy script
./destroy.sh

# Verify everything is deleted
cd terraform
terraform show
```

### Manual Cleanup

```bash
cd terraform
terraform destroy -auto-approve
```

## Security Considerations

1. **Firewall Rules**: Restrict `allowed_source_ips` to your IP only
2. **SSL Certificates**: Mock APIC uses self-signed cert (for POC only)
3. **Passwords**: Change default APIC password in production
4. **Service Accounts**: Uses minimal required permissions
5. **Network**: Private VPC with controlled ingress

## Advanced Usage

### Custom Test Data

1. **Edit topology:**
   ```bash
   nano aci-config/sample-topology.json
   ```

2. **Regenerate data:**
   ```bash
   python3 scripts/generate-mock-data.py > aci-config/test-data/mock_data.json
   ```

3. **Upload to Mock APIC:**
   ```bash
   gcloud compute scp aci-config/test-data/mock_data.json \
     aci-migrator-poc-aci-simulator:/opt/mock-apic/mock_data.json \
     --zone=us-central1-a

   gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a \
     --command="sudo systemctl restart mock-apic"
   ```

### Integration Testing

```bash
# Run integration tests
python3 scripts/test-mcp-integration.py \
  --mcp-url http://MCP_IP:5000 \
  --apic-url https://APIC_IP \
  --output test-results.json

# Analyze test data
python3 scripts/configure-aci-data.py \
  --input aci-config/sample-topology.json \
  --analyze \
  --output analysis.json
```

### Multi-Region Deployment

Deploy to multiple regions for testing:

```bash
# Deploy to us-central1
terraform apply -var="region=us-central1"

# Deploy to europe-west1
terraform apply -var="region=europe-west1"
```

## Support and Contribution

### Getting Help

1. Check troubleshooting section
2. Review logs from VMs
3. Check GCP Console for resource status
4. Verify network connectivity

### Contributing

Improvements welcome! Areas for contribution:
- Additional test scenarios
- More realistic ACI configurations
- Enhanced MCP server features
- Cost optimization strategies

## References

- [Cisco ACI Documentation](https://www.cisco.com/c/en/us/support/cloud-systems-management/application-policy-infrastructure-controller-apic/tsd-products-support-series-home.html)
- [GCP Compute Engine](https://cloud.google.com/compute/docs)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [ACI Migrator Documentation](../README.md)

## License

This deployment automation is part of the ACI Migrator project.

---

**Ready to deploy?** Run `./deploy.sh` to get started!
