# ACI Migration Ansible Playbooks

This directory contains Ansible playbooks for automating ACI to EVPN/VXLAN migration tasks.

## Overview

These playbooks automate various aspects of the migration process:
- Pre-migration validation
- Configuration deployment
- Post-migration verification
- Rollback procedures

## Prerequisites

```bash
# Install Ansible
pip install ansible

# Install required collections
ansible-galaxy collection install cisco.nxos
ansible-galaxy collection install arista.eos
ansible-galaxy collection install junipernetworks.junos
```

## Directory Structure

```
playbooks/
├── README.md                 # This file
├── inventory/
│   ├── hosts.ini            # Inventory file
│   └── group_vars/          # Group variables
├── playbooks/
│   ├── 01_pre_migration_check.yml
│   ├── 02_backup_configs.yml
│   ├── 03_deploy_spine_configs.yml
│   ├── 04_deploy_leaf_configs.yml
│   ├── 05_deploy_border_leaf_configs.yml
│   ├── 06_verify_evpn.yml
│   └── 99_rollback.yml
├── roles/
│   ├── evpn_spine/
│   ├── evpn_leaf/
│   └── evpn_border_leaf/
└── templates/
    ├── nxos_spine.j2
    ├── nxos_leaf.j2
    ├── eos_spine.j2
    └── eos_leaf.j2
```

## Usage

### 1. Configure Inventory

Edit `inventory/hosts.ini` with your device information:

```ini
[spines]
spine-01 ansible_host=10.1.1.1
spine-02 ansible_host=10.1.1.2

[leafs]
leaf-101 ansible_host=10.1.1.101
leaf-102 ansible_host=10.1.1.102

[border_leafs]
border-leaf-201 ansible_host=10.1.1.201
```

### 2. Configure Variables

Edit `inventory/group_vars/all.yml` with your fabric settings.

### 3. Run Playbooks in Order

```bash
# 1. Pre-migration checks
ansible-playbook -i inventory/hosts.ini playbooks/01_pre_migration_check.yml

# 2. Backup all configurations
ansible-playbook -i inventory/hosts.ini playbooks/02_backup_configs.yml

# 3. Deploy spine configurations
ansible-playbook -i inventory/hosts.ini playbooks/03_deploy_spine_configs.yml

# 4. Deploy leaf configurations
ansible-playbook -i inventory/hosts.ini playbooks/04_deploy_leaf_configs.yml

# 5. Deploy border leaf configurations
ansible-playbook -i inventory/hosts.ini playbooks/05_deploy_border_leaf_configs.yml

# 6. Verify EVPN deployment
ansible-playbook -i inventory/hosts.ini playbooks/06_verify_evpn.yml
```

### Rollback

If issues occur, use the rollback playbook:

```bash
ansible-playbook -i inventory/hosts.ini playbooks/99_rollback.yml
```

## Playbook Descriptions

### 01_pre_migration_check.yml
- Validates connectivity to all devices
- Checks software versions
- Verifies current state
- Generates pre-migration report

### 02_backup_configs.yml
- Backs up all device configurations
- Stores backups in timestamped directories
- Validates backup integrity

### 03_deploy_spine_configs.yml
- Deploys EVPN spine configurations
- Configures BGP route reflectors
- Sets up EVPN address families

### 04_deploy_leaf_configs.yml
- Deploys EVPN leaf configurations
- Configures VTEPs
- Sets up BGP peering
- Configures VNI/VLAN mappings

### 05_deploy_border_leaf_configs.yml
- Deploys border leaf configurations
- Configures external BGP peering
- Sets up L3Out equivalents

### 06_verify_evpn.yml
- Verifies BGP sessions
- Checks EVPN routes
- Validates VNI status
- Tests connectivity

### 99_rollback.yml
- Restores previous configurations
- Validates rollback success
- Generates rollback report

## Variables

Key variables to configure in `inventory/group_vars/all.yml`:

```yaml
# BGP Configuration
bgp_asn: 65001
evpn_route_reflector_clients: true

# VXLAN Configuration
vxlan_udp_port: 4789
anycast_gateway_mac: 0000.2222.3333

# Management
snmp_community: public
ntp_servers:
  - 10.0.0.1
  - 10.0.0.2
```

## Safety Features

All playbooks include:
- Pre-flight checks
- Dry-run mode support
- Configuration backups
- Rollback capabilities
- Detailed logging

## Best Practices

1. **Always run pre-migration checks first**
2. **Test in lab environment before production**
3. **Review generated configurations**
4. **Have rollback plan ready**
5. **Monitor during deployment**
6. **Verify after each stage**

## Support

For issues or questions:
- Check playbook logs in `logs/` directory
- Review Ansible verbose output (`-vvv` flag)
- Consult ACI Migrator documentation

## License

Internal use only. Not for distribution.
