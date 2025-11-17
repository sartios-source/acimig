terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# VPC Network
resource "google_compute_network" "aci_vpc" {
  name                    = "${var.prefix}-vpc"
  auto_create_subnetworks = false
  description             = "VPC for ACI Migrator POC"
}

# Subnet
resource "google_compute_subnetwork" "aci_subnet" {
  name          = "${var.prefix}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.aci_vpc.id
  description   = "Subnet for ACI Migrator POC"
}

# Firewall Rules
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.prefix}-allow-ssh"
  network = google_compute_network.aci_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.allowed_source_ips
  target_tags   = ["aci-poc"]
  description   = "Allow SSH access"
}

resource "google_compute_firewall" "allow_apic" {
  name    = "${var.prefix}-allow-apic"
  network = google_compute_network.aci_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["443", "80"]
  }

  source_ranges = var.allowed_source_ips
  target_tags   = ["aci-simulator"]
  description   = "Allow APIC web interface and API access"
}

resource "google_compute_firewall" "allow_mcp" {
  name    = "${var.prefix}-allow-mcp"
  network = google_compute_network.aci_vpc.name

  allow {
    protocol = "tcp"
    ports    = [var.mcp_port]
  }

  source_ranges = var.allowed_source_ips
  target_tags   = ["mcp-server"]
  description   = "Allow MCP server access"
}

resource "google_compute_firewall" "allow_internal" {
  name    = "${var.prefix}-allow-internal"
  network = google_compute_network.aci_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]
  target_tags   = ["aci-poc"]
  description   = "Allow internal communication"
}

# Service Account
resource "google_service_account" "aci_sa" {
  account_id   = "${var.prefix}-sa"
  display_name = "ACI Migrator POC Service Account"
  description  = "Service account for ACI Migrator POC VMs"
}

# Static External IP for ACI Simulator
resource "google_compute_address" "aci_simulator_ip" {
  name         = "${var.prefix}-simulator-ip"
  address_type = "EXTERNAL"
  region       = var.region
  description  = "Static IP for ACI Simulator"
}

# Static External IP for MCP Server
resource "google_compute_address" "mcp_server_ip" {
  name         = "${var.prefix}-mcp-ip"
  address_type = "EXTERNAL"
  region       = var.region
  description  = "Static IP for MCP Server"
}

# Startup script for ACI Simulator
data "template_file" "aci_simulator_startup" {
  template = file("${path.module}/../scripts/setup-aci-simulator.sh")
}

# Startup script for MCP Server
data "template_file" "mcp_server_startup" {
  template = file("${path.module}/../scripts/setup-mcp-server.sh")
}

# ACI Simulator VM
resource "google_compute_instance" "aci_simulator" {
  name         = "${var.prefix}-aci-simulator"
  machine_type = var.aci_simulator_machine_type
  zone         = var.zone
  tags         = ["aci-poc", "aci-simulator"]

  boot_disk {
    initialize_params {
      image = var.vm_image
      size  = var.aci_simulator_disk_size
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.aci_subnet.id
    access_config {
      nat_ip = google_compute_address.aci_simulator_ip.address
    }
  }

  service_account {
    email  = google_service_account.aci_sa.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
    startup-script = data.template_file.aci_simulator_startup.rendered
  }

  labels = {
    environment = "poc"
    component   = "aci-simulator"
  }

  allow_stopping_for_update = true
}

# MCP Server VM
resource "google_compute_instance" "mcp_server" {
  name         = "${var.prefix}-mcp-server"
  machine_type = var.mcp_server_machine_type
  zone         = var.zone
  tags         = ["aci-poc", "mcp-server"]

  boot_disk {
    initialize_params {
      image = var.vm_image
      size  = var.mcp_server_disk_size
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.aci_subnet.id
    access_config {
      nat_ip = google_compute_address.mcp_server_ip.address
    }
  }

  service_account {
    email  = google_service_account.aci_sa.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
    startup-script = data.template_file.mcp_server_startup.rendered
    aci_simulator_ip = google_compute_address.aci_simulator_ip.address
    mcp_port = var.mcp_port
  }

  labels = {
    environment = "poc"
    component   = "mcp-server"
  }

  allow_stopping_for_update = true
  depends_on                = [google_compute_instance.aci_simulator]
}
