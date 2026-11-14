# Red de salida del extractor: todo su tráfico sale por Cloud NAT con una IP fija,
# que es la que el proveedor autoriza en el firewall de MariaDB.

resource "google_compute_network" "vpc" {
  name                    = "${var.prefijo}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "jobs" {
  name                     = "${var.prefijo}-jobs"
  network                  = google_compute_network.vpc.id
  region                   = var.region
  ip_cidr_range            = var.cidr
  private_ip_google_access = true # BigQuery y Storage sin salir a internet
}

resource "google_compute_router" "router" {
  name    = "${var.prefijo}-router"
  network = google_compute_network.vpc.id
  region  = var.region
}

resource "google_compute_address" "nat_ip" {
  name   = "${var.prefijo}-nat-ip"
  region = var.region

  lifecycle {
    prevent_destroy = true # si cambia, hay que volver a pedir la autorización en MariaDB
  }
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.prefijo}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = [google_compute_address.nat_ip.self_link]
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.jobs.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
