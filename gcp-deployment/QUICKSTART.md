# Quick Start Guide - 5 Minute Setup

Get your ACI Migrator POC environment running in 5 minutes!

Optional: For local MCP testing without VMs, run `python gcp-deployment/mcp-server/server.py --mock-data data/samples/sample_aci.json` with `MCP_PORT=5001`.

## Prerequisites Check (2 minutes)

```bash
# Check if you have required tools
gcloud --version    # Need: Google Cloud SDK
terraform --version # Need: Terraform >= 1.0
python3 --version   # Need: Python 3.8+
jq --version        # Need: jq for JSON processing

# Login to GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Don't have these? See [Prerequisites Setup](#prerequisites-setup) below.

## Deploy (3 minutes)

```bash
# 1. Navigate to deployment directory
cd gcp-deployment

# 2. Configure (REQUIRED)
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
nano terraform/terraform.tfvars

# Edit these lines:
#   project_id = "your-actual-project-id"
#   allowed_source_ips = ["YOUR.IP.HERE/32"]  # Get IP: curl ifconfig.me

# 3. Deploy everything!
chmod +x deploy.sh
./deploy.sh
```

The script will:
- ✓ Validate prerequisites
- ✓ Deploy GCP infrastructure (2 VMs, networking)
- ✓ Install Mock APIC server
- ✓ Install MCP server
- ✓ Test all components
- ✓ Display connection info

## Verify (30 seconds)

```bash
# Get your server IPs
cd terraform
APIC_IP=$(terraform output -raw aci_simulator_external_ip)
MCP_IP=$(terraform output -raw mcp_server_external_ip)

# Test Mock APIC
curl -k https://$APIC_IP/health

# Test MCP Server
curl http://$MCP_IP:5000/health

# Get sample data
curl http://$MCP_IP:5000/api/migrator/data | jq .statistics
```

Expected output:
```json
{
  "total_nodes": 7,
  "total_tenants": 3,
  "total_epgs": 4,
  "total_paths": 12
}
```

## Use with ACI Migrator

### Option 1: Web UI

1. Start ACI Migrator:
   ```bash
   cd /path/to/aciv2
   python app.py
   ```

2. Open browser: http://localhost:5000

3. Go to "Upload" page

4. In "Import from MCP Server" section:
   - MCP URL: `http://MCP_IP:5000`
   - Click "Test Connection"
   - Fabric name: `gcp-poc-fabric`
   - Click "Import"

5. Go to "Analyze" page to see your data!

### Option 2: API

```bash
# Test connection
curl -X POST http://localhost:5000/api/mcp/test \
  -H "Content-Type: application/json" \
  -d "{\"mcp_url\": \"http://$MCP_IP:5000\"}"

# Import data
curl -X POST http://localhost:5000/api/mcp/import \
  -H "Content-Type: application/json" \
  -d "{
    \"mcp_url\": \"http://$MCP_IP:5000\",
    \"fabric_name\": \"gcp-poc-fabric\"
  }"
```

## What You Get

Your deployment includes:

**Fabric Topology:**
- 2 Spine switches
- 4 Leaf switches
- 8 FEX devices (48 ports each)

**Test Data:**
- 3 Tenants (production, development, management)
- 20+ EPGs with various configurations
- Multiple test scenarios for migration analysis

**Servers:**
- Mock APIC: https://APIC_IP
- MCP Server: http://MCP_IP:5000

## Common Tasks

### View Logs

```bash
# Mock APIC logs
gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a \
  --command="sudo journalctl -u mock-apic -f"

# MCP Server logs
gcloud compute ssh aci-migrator-poc-mcp-server --zone=us-central1-a \
  --command="sudo journalctl -u mcp-server -f"
```

### Restart Services

```bash
# Restart Mock APIC
gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a \
  --command="sudo systemctl restart mock-apic"

# Restart MCP Server
gcloud compute ssh aci-migrator-poc-mcp-server --zone=us-central1-a \
  --command="sudo systemctl restart mcp-server"
```

### Stop VMs (Save Money)

```bash
# Stop both VMs when not in use
gcloud compute instances stop aci-migrator-poc-aci-simulator --zone=us-central1-a
gcloud compute instances stop aci-migrator-poc-mcp-server --zone=us-central1-a

# Start them again
gcloud compute instances start aci-migrator-poc-aci-simulator --zone=us-central1-a
gcloud compute instances start aci-migrator-poc-mcp-server --zone=us-central1-a
```

### Cleanup Everything

```bash
cd gcp-deployment
./destroy.sh
```

## Troubleshooting

### "Connection refused" errors

**Problem:** Can't connect to servers

**Solution:**
```bash
# 1. Check if VMs are running
gcloud compute instances list | grep aci-migrator-poc

# 2. Verify your IP is allowed
curl ifconfig.me  # Compare to allowed_source_ips in terraform.tfvars

# 3. Update firewall if your IP changed
gcloud compute firewall-rules update aci-migrator-poc-allow-mcp \
  --source-ranges="$(curl -s ifconfig.me)/32"
```

### Services not starting

**Problem:** Health checks fail

**Solution:**
```bash
# Wait 2-3 more minutes for startup scripts to complete

# Check startup script progress
gcloud compute instances get-serial-port-output aci-migrator-poc-aci-simulator \
  --zone=us-central1-a | tail -50

# SSH and check manually
gcloud compute ssh aci-migrator-poc-aci-simulator --zone=us-central1-a
sudo systemctl status mock-apic
sudo journalctl -u mock-apic -n 50
```

### Terraform errors

**Problem:** Terraform fails during deployment

**Solution:**
```bash
# Common issue: wrong project ID
gcloud config get-value project  # Verify project ID

# Re-run deployment
cd terraform
terraform destroy -auto-approve  # Clean up partial deployment
cd ..
./deploy.sh
```

## Cost Management

**Current cost:** ~$6/day (~$180/month) if running 24/7

**Save money:**

1. **Stop when not in use:**
   ```bash
   gcloud compute instances stop aci-migrator-poc-* --zone=us-central1-a
   ```
   Cost while stopped: ~$0.70/day (disk storage only)

2. **Use smaller VMs:**
   Edit `terraform.tfvars`:
   ```hcl
   aci_simulator_machine_type = "n1-standard-2"
   mcp_server_machine_type    = "n1-standard-1"
   ```
   Cost: ~$3/day

3. **Delete when done:**
   ```bash
   ./destroy.sh
   ```
   Cost: $0

See [COST_ESTIMATE.md](COST_ESTIMATE.md) for detailed breakdown.

## Next Steps

1. **Import more data**: Customize test data in `aci-config/sample-topology.json`
2. **Run analysis**: Use ACI Migrator analysis features
3. **Generate reports**: Export migration plans and reports
4. **Integration testing**: Test full workflow end-to-end

## Prerequisites Setup

### Install Google Cloud SDK

**macOS:**
```bash
brew install --cask google-cloud-sdk
```

**Ubuntu/Debian:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows:**
Download from https://cloud.google.com/sdk/docs/install

### Install Terraform

**macOS:**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Ubuntu/Debian:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Windows:**
Download from https://www.terraform.io/downloads

### Install jq

**macOS:**
```bash
brew install jq
```

**Ubuntu/Debian:**
```bash
sudo apt-get install jq
```

**Windows:**
```bash
choco install jq
```

## Support

- Full documentation: [README.md](README.md)
- Cost details: [COST_ESTIMATE.md](COST_ESTIMATE.md)
- Issues: Check GCP Console and VM logs

---

**Ready to deploy?** Just run `./deploy.sh`!

**Questions?** See full [README.md](README.md) for detailed information.
