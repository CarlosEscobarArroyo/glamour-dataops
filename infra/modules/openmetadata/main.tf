# VM para OpenMetadata. Terraform solo crea la máquina; Docker y OpenMetadata se
# instalan a mano por SSH. El acceso SSH entra a través de IAP.

resource "google_service_account" "vm" {
  account_id   = "sa-openmetadata-${var.ambiente}"
  display_name = "VM de OpenMetadata (catálogo de datos)"
}

resource "google_compute_address" "ip" {
  name   = "${var.prefijo}-ip-openmetadata"
  region = var.region
}

resource "google_compute_instance" "vm" {
  name         = "${var.prefijo}-vm-openmetadata"
  zone         = var.zona
  machine_type = var.tipo_maquina
  tags         = ["openmetadata"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = var.disco_gb # los 10 GB por defecto no alcanzan para las imágenes de Docker
    }
  }

  network_interface {
    subnetwork = var.subnet_id

    access_config {
      nat_ip = google_compute_address.ip.address
    }
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["cloud-platform"] # los permisos reales los da IAM
  }

  allow_stopping_for_update = true

  lifecycle {
    # Una imagen nueva de Ubuntu no debe recrear la VM.
    # Las claves SSH se gestionan fuera de Terraform.
    ignore_changes = [
      boot_disk[0].initialize_params[0].image,
      metadata["ssh-keys"],
    ]
  }
}

# SSH solo desde el rango de IAP: el puerto 22 no queda expuesto a internet.
resource "google_compute_firewall" "ssh_iap" {
  name          = "${var.prefijo}-fw-openmetadata-ssh-iap"
  network       = var.network_id
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["openmetadata"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

moved {
  from = google_compute_firewall.web
  to   = google_compute_firewall.web[0]
}

# Acceso HTTP directo para los entornos que conservan la regla pública.
resource "google_compute_firewall" "web" {
  count         = var.acceso_web_publico ? 1 : 0
  name          = "${var.prefijo}-fw-openmetadata-web"
  network       = var.network_id
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["openmetadata"]

  allow {
    protocol = "tcp"
    ports    = ["8585"]
  }
}
