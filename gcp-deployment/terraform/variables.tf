variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "us-central1-a"
}

variable "prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "aci-migrator-poc"
}

variable "subnet_cidr" {
  description = "CIDR block for subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "allowed_source_ips" {
  description = "List of IP addresses allowed to access the infrastructure"
  type        = list(string)
  default     = ["0.0.0.0/0"] # CHANGE THIS TO YOUR IP FOR PRODUCTION
}

variable "aci_simulator_machine_type" {
  description = "Machine type for ACI Simulator VM"
  type        = string
  default     = "n1-standard-4" # 4 vCPU, 15GB RAM
}

variable "aci_simulator_disk_size" {
  description = "Disk size for ACI Simulator VM in GB"
  type        = number
  default     = 50
}

variable "mcp_server_machine_type" {
  description = "Machine type for MCP Server VM"
  type        = string
  default     = "n1-standard-2" # 2 vCPU, 7.5GB RAM
}

variable "mcp_server_disk_size" {
  description = "Disk size for MCP Server VM in GB"
  type        = number
  default     = 20
}

variable "vm_image" {
  description = "VM image for instances"
  type        = string
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

variable "mcp_port" {
  description = "Port for MCP server"
  type        = string
  default     = "5000"
}

variable "apic_admin_password" {
  description = "Admin password for APIC simulator"
  type        = string
  default     = "C1sco12345"
  sensitive   = true
}
