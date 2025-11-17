output "aci_simulator_external_ip" {
  description = "External IP address of ACI Simulator"
  value       = google_compute_address.aci_simulator_ip.address
}

output "mcp_server_external_ip" {
  description = "External IP address of MCP Server"
  value       = google_compute_address.mcp_server_ip.address
}

output "aci_simulator_internal_ip" {
  description = "Internal IP address of ACI Simulator"
  value       = google_compute_instance.aci_simulator.network_interface[0].network_ip
}

output "mcp_server_internal_ip" {
  description = "Internal IP address of MCP Server"
  value       = google_compute_instance.mcp_server.network_interface[0].network_ip
}

output "apic_url" {
  description = "URL to access APIC simulator"
  value       = "https://${google_compute_address.aci_simulator_ip.address}"
}

output "mcp_server_url" {
  description = "URL to access MCP server"
  value       = "http://${google_compute_address.mcp_server_ip.address}:${var.mcp_port}"
}

output "ssh_aci_simulator" {
  description = "SSH command for ACI Simulator"
  value       = "gcloud compute ssh ${google_compute_instance.aci_simulator.name} --zone=${var.zone}"
}

output "ssh_mcp_server" {
  description = "SSH command for MCP Server"
  value       = "gcloud compute ssh ${google_compute_instance.mcp_server.name} --zone=${var.zone}"
}

output "connection_info" {
  description = "Connection information"
  value = <<-EOT
    ==========================================
    ACI Migrator POC - Connection Information
    ==========================================

    ACI Simulator (Mock APIC):
      URL: https://${google_compute_address.aci_simulator_ip.address}
      Username: admin
      Password: ${var.apic_admin_password}
      SSH: gcloud compute ssh ${google_compute_instance.aci_simulator.name} --zone=${var.zone}

    MCP Server:
      URL: http://${google_compute_address.mcp_server_ip.address}:${var.mcp_port}
      Health: http://${google_compute_address.mcp_server_ip.address}:${var.mcp_port}/health
      SSH: gcloud compute ssh ${google_compute_instance.mcp_server.name} --zone=${var.zone}

    Network:
      VPC: ${google_compute_network.aci_vpc.name}
      Subnet: ${google_compute_subnetwork.aci_subnet.name}
      CIDR: ${var.subnet_cidr}

    Next Steps:
      1. Wait 5-10 minutes for startup scripts to complete
      2. Test APIC: curl -k https://${google_compute_address.aci_simulator_ip.address}/api/aaaLogin.json
      3. Test MCP: curl http://${google_compute_address.mcp_server_ip.address}:${var.mcp_port}/health
      4. Use MCP client in ACI Migrator to import data

    ==========================================
  EOT
  sensitive = true
}
