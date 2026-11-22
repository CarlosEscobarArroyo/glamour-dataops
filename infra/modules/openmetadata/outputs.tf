output "nombre" {
  value = google_compute_instance.vm.name
}

output "zona" {
  value = google_compute_instance.vm.zone
}

output "ip" {
  value = google_compute_address.ip.address
}
