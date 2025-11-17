# GCP Cost Estimate - ACI Migrator POC

Detailed cost breakdown for running the ACI Migrator POC environment on Google Cloud Platform.

## Summary

| Component | Cost/Hour | Cost/Day | Cost/Month |
|-----------|-----------|----------|------------|
| Mock APIC VM (n1-standard-4) | $0.15 | $3.60 | $108.00 |
| MCP Server VM (n1-standard-2) | $0.08 | $1.92 | $57.60 |
| Static IPs (2) | $0.02 | $0.48 | $14.40 |
| Persistent Disks (70GB) | $0.01 | $0.24 | $7.20 |
| Network Egress (~1GB/day) | $0.00 | $0.05 | $1.50 |
| **Total** | **$0.26** | **$6.24** | **$188.70** |

*Prices based on us-central1 region as of 2024. Actual costs may vary.*

## Detailed Breakdown

### Compute Instances

#### Mock APIC VM (n1-standard-4)

**Configuration:**
- Machine Type: n1-standard-4 (4 vCPU, 15GB RAM)
- Disk: 50GB standard persistent disk
- Region: us-central1
- Purpose: Run Mock APIC server (Python Flask app)

**Costs:**
- Instance: $0.1900/hour
- Disk (50GB): $0.002/hour
- **Subtotal: $0.192/hour ($4.61/day, $138.24/month)**

**Why this size?**
- APIC simulator needs memory for holding topology data
- Flask application + mock data handling
- Room for expansion with more test data

**Cost Optimization:**
- Can reduce to n1-standard-2 for basic testing ($0.095/hour)
- Use preemptible instance: Save 80% ($0.038/hour)
  - Note: Will be terminated after 24 hours max
  - Good for short-term testing only

#### MCP Server VM (n1-standard-2)

**Configuration:**
- Machine Type: n1-standard-2 (2 vCPU, 7.5GB RAM)
- Disk: 20GB standard persistent disk
- Region: us-central1
- Purpose: Run MCP server, query APIC, transform data

**Costs:**
- Instance: $0.0950/hour
- Disk (20GB): $0.0008/hour
- **Subtotal: $0.0958/hour ($2.30/day, $69.00/month)**

**Why this size?**
- Async HTTP operations with aiohttp
- Data transformation and caching
- API serving

**Cost Optimization:**
- Can reduce to n1-standard-1 for light testing ($0.0475/hour)
- Use preemptible: $0.019/hour
- Or use f1-micro for minimal testing: $0.0035/hour

### Networking

#### Static External IPs

**Configuration:**
- 2 static external IPs (one per VM)
- Reserved but attached to running instances

**Costs:**
- Static IP (in use): $0.01/hour per IP
- **Subtotal: $0.02/hour ($0.48/day, $14.40/month)**

**Cost Optimization:**
- Use ephemeral IPs: FREE
  - IP will change if VM restarts
  - Need to update firewall rules manually
  - Recommended for short-term testing

#### Egress Traffic

**Estimated Usage:**
- API calls from local machine: ~100MB/day
- MCP data transfers: ~50MB/day
- SSH/management: ~10MB/day
- **Total: ~160MB/day (~5GB/month)**

**Costs:**
- First 1GB/month: FREE
- 1-10GB/month: $0.12/GB
- **Subtotal: ~$0.05/day ($1.50/month)**

**Cost Optimization:**
- Minimize data transfers
- Use gcloud SSH instead of external tools
- Compress data transfers
- Most API calls are small, so actual costs typically lower

### Storage

#### Persistent Disks

**Configuration:**
- Mock APIC: 50GB standard persistent disk
- MCP Server: 20GB standard persistent disk
- **Total: 70GB**

**Costs:**
- Standard PD: $0.040/GB/month
- **Subtotal: $2.80/month ($0.09/day)**

**Cost Optimization:**
- Use smaller disks (20GB each): $1.60/month
- Delete snapshots promptly
- Standard PD is already the cheapest option

### VPC and Firewall

**Configuration:**
- 1 VPC network
- 1 subnet (10.0.1.0/24)
- 4 firewall rules

**Costs:**
- VPC: FREE
- Subnets: FREE
- Firewall rules: FREE
- **Subtotal: $0.00**

## Cost Scenarios

### Scenario 1: Always-On Production POC

**Use Case:** Continuous availability for team testing

**Configuration:**
- Both VMs running 24/7
- Static IPs
- Standard persistent disks

**Monthly Cost:**
```
Compute: $207.24
IPs: $14.40
Disk: $7.20
Network: $1.50
──────────────
Total: $230.34/month
```

### Scenario 2: Business Hours Only (8hrs/day, 22 days/month)

**Use Case:** Testing during work hours only

**Configuration:**
- VMs running 176 hours/month (8 × 22)
- Static IPs reserved
- Standard persistent disks

**Monthly Cost:**
```
Compute: $50.61 (176 hours)
IPs: $14.40 (always on)
Disk: $7.20 (always on)
Network: $0.50 (less usage)
──────────────
Total: $72.71/month
```

**Savings: 68% ($157.63/month)**

### Scenario 3: Preemptible VMs (Testing Only)

**Use Case:** Short-term testing, can handle interruptions

**Configuration:**
- Preemptible VMs (80% discount)
- Ephemeral IPs
- Standard persistent disks
- Run when needed (10 hours/week)

**Monthly Cost:**
```
Compute: $10.02 (40 hours @ 80% off)
IPs: $0.00 (ephemeral)
Disk: $7.20 (always on)
Network: $0.20 (minimal)
──────────────
Total: $17.42/month
```

**Savings: 92% ($212.92/month)**

### Scenario 4: Minimal Configuration

**Use Case:** One-time testing or demo

**Configuration:**
- n1-standard-2 for APIC
- n1-standard-1 for MCP
- Ephemeral IPs
- 20GB disks each
- Run 4 hours

**Cost for 4 hours:**
```
APIC VM: $0.38
MCP VM: $0.19
Disk: $0.01
Network: $0.00
──────────────
Total: $0.58 for 4 hours
```

## Cost Management Strategies

### 1. Stop VMs When Not in Use

```bash
# Stop both VMs
gcloud compute instances stop aci-migrator-poc-aci-simulator --zone=us-central1-a
gcloud compute instances stop aci-migrator-poc-mcp-server --zone=us-central1-a

# Costs while stopped:
# - Compute: $0
# - IPs: $0.02/hour (if static)
# - Disk: $0.01/hour
# Total: ~$0.03/hour ($0.72/day)
```

### 2. Use Scheduled Instances

Create a schedule to automatically start/stop VMs:

```bash
# Start at 8 AM weekdays
gcloud compute resource-policies create instance-schedule weekday-schedule \
    --region us-central1 \
    --vm-start-schedule '0 8 * * 1-5' \
    --vm-stop-schedule '0 18 * * 1-5' \
    --timezone 'America/Los_Angeles'

# Attach to instances
gcloud compute instances add-resource-policies aci-migrator-poc-aci-simulator \
    --resource-policies weekday-schedule \
    --zone us-central1-a
```

### 3. Use Budget Alerts

Set up budget alerts to avoid surprises:

```bash
# Create budget (via Console or gcloud)
# Set alert at 50%, 75%, 90%, 100% of $50/month
```

**In GCP Console:**
1. Go to Billing → Budgets & alerts
2. Create budget
3. Set amount: $50/month
4. Set alerts: 50%, 75%, 90%, 100%
5. Add email notification

### 4. Committed Use Discounts

For long-term usage (1-3 years):
- 1 year commitment: 25% discount
- 3 year commitment: 52% discount

**Example: 1-year commitment**
```
Monthly cost with 25% discount: ~$141/month
Annual cost: $1,692 (vs $2,256 on-demand)
Savings: $564/year
```

### 5. Use Smallest Viable Configuration

**Recommended for POC:**
```hcl
# terraform.tfvars
aci_simulator_machine_type = "n1-standard-2"  # Instead of n1-standard-4
mcp_server_machine_type    = "n1-standard-1"  # Instead of n1-standard-2
aci_simulator_disk_size    = 20               # Instead of 50GB
mcp_server_disk_size       = 10               # Instead of 20GB
```

**New monthly cost: ~$95/month** (50% savings)

### 6. Delete When Done

Most important cost control:

```bash
# Destroy everything when not needed
./destroy.sh

# Cost while deleted: $0
```

## Monitoring Costs

### View Current Costs

```bash
# Via gcloud
gcloud billing accounts list
gcloud billing accounts projects link YOUR_PROJECT \
    --billing-account=YOUR_BILLING_ACCOUNT

# View current month costs (via Console)
# Go to: https://console.cloud.google.com/billing
```

### Set Up Cost Tracking

1. **Enable detailed billing export:**
   - Go to Billing → Billing export
   - Export to BigQuery
   - Analyze with SQL

2. **Use labels for tracking:**
   ```hcl
   # In terraform
   labels = {
     environment = "poc"
     project     = "aci-migrator"
     cost-center = "engineering"
   }
   ```

3. **Cost breakdown by label:**
   - View in GCP Console → Billing
   - Filter by labels
   - Track per-project costs

## Free Tier Benefits

**GCP Free Tier (first 90 days):**
- $300 credit for new accounts
- Can run this POC for ~48 days FREE

**Always Free:**
- First 1GB network egress/month
- Some minimal compute (f1-micro in select regions)
  - Not applicable to this deployment (need larger VMs)

## Regional Cost Differences

Costs vary by region:

| Region | Cost Multiplier | Example Monthly Cost |
|--------|-----------------|---------------------|
| us-central1 | 1.00× | $188.70 |
| us-east1 | 1.00× | $188.70 |
| us-west1 | 1.00× | $188.70 |
| europe-west1 | 1.06× | $200.00 |
| asia-southeast1 | 1.13× | $213.00 |

**Recommendation:** Use us-central1 for lowest cost

## Hidden Costs to Watch

1. **Snapshots:** $0.026/GB/month
   - Terraform doesn't create snapshots by default
   - Delete manual snapshots when done

2. **Images:** $0.050/GB/month
   - Custom images cost more
   - Use standard images (included in deployment)

3. **Load Balancers:** $18/month minimum
   - Not used in this deployment

4. **Cloud NAT:** $0.045/hour
   - Not needed for this deployment

5. **VPN Tunnels:** $0.05/hour
   - Not needed for this deployment

## Cost Comparison

### Alternative: Run Locally

**Local Setup:**
- Cost: $0
- Pros: No cloud costs
- Cons:
  - Need local resources
  - No external access
  - Manual setup

**When to use local:**
- One-time testing
- No external access needed
- Sufficient local resources

**When to use GCP:**
- Team access needed
- Long-term testing
- Production-like environment
- CI/CD integration

### Alternative: Docker on Local

**Docker Compose Setup:**
- Cost: $0
- Pros: Easy setup, portable
- Cons:
  - Local resources only
  - No external access without port forwarding
  - Less realistic network environment

## Summary and Recommendations

### For Short-Term Testing (< 1 week)

**Recommendation:** Minimal configuration, stop when not in use
- **Estimated cost:** $10-20 total
- Configuration: n1-standard-2 + n1-standard-1
- Usage pattern: 4-8 hours/day

### For Team POC (1-4 weeks)

**Recommendation:** Business hours schedule
- **Estimated cost:** $70-150/month
- Configuration: Standard as deployed
- Usage pattern: 8 hours/day, weekdays
- Use scheduled start/stop

### For Extended Testing (1-3 months)

**Recommendation:** Committed use discount
- **Estimated cost:** $120-140/month with 1-year commit
- Configuration: Optimized sizes
- Usage pattern: 12-16 hours/day
- Set budget alerts at $150/month

### For Production Demo Environment

**Recommendation:** Always-on with monitoring
- **Estimated cost:** $180-200/month
- Configuration: Full spec as deployed
- Usage pattern: 24/7
- Use budget alerts
- Regular cost reviews

---

**Remember:** Always run `./destroy.sh` when done testing to avoid unnecessary costs!

**Cost tracking:** Set up billing alerts in GCP Console → Billing → Budgets & alerts
