output "network_id" {
  value = google_compute_network.vpc.id
}

output "subnet_id" {
  value = google_compute_subnetwork.jobs.id
}

output "nat_ip" {
  value = google_compute_address.nat_ip.address
}
