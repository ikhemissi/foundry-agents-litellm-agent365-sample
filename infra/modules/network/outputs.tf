output "virtual_network_id" {
  value = azurerm_virtual_network.main.id
}

output "subnet_ids" {
  description = "Subnet ids by subnet name."
  value       = { for name, subnet in azurerm_subnet.main : name => subnet.id }
}

output "private_dns_zone_ids" {
  description = "Private DNS zone ids by zone name."
  value       = { for name, zone in azurerm_private_dns_zone.main : name => zone.id }
}
