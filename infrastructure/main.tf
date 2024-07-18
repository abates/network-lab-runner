terraform {
  backend "local" {
    path = ".terraform_state/terraform.tfstate"
  }
  required_providers {
    kubectl = {
      source  = "alekc/kubectl"
    }
    kubernetes = {}
  }
}

provider "digitalocean"{
  token = var.do_token
}

data "digitalocean_project" "nautobot_project" {
  name = var.project_name
}

data "http" "static-routes-request" {
  url = "https://raw.githubusercontent.com/digitalocean/k8s-staticroute-operator/main/releases/v1/k8s-staticroute-operator-v1.0.0.yaml"
}

data "kubectl_file_documents" "static-routes-manifest" {
    content = data.http.static-routes-request.response_body
}

resource "digitalocean_kubernetes_cluster" "nautobot_cluster" {
  name   = var.k8s_clustername
  region = var.region
  # Grab the latest version slug from `doctl kubernetes options versions`
  version = var.k8s_version

  node_pool {
    name       = var.k8s_poolname
    size       = var.k8s_size
    node_count = var.k8s_count
  }

  provisioner "local-exec" {
    command = "doctl kubernetes cluster kubeconfig save $K8S_CLUSTER_NAME"
    environment = {
      K8S_CLUSTER_NAME = var.k8s_clustername
    }
  }

  provisioner "local-exec" {
    command = "doctl kubernetes cluster kubeconfig remove $K8S_CLUSTER_NAME"
    when = destroy
    environment = {
      K8S_CLUSTER_NAME = self.name
    }
  }
}

provider "kubernetes" {
  host = digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.host

  client_certificate     = digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.client_certificate
  client_key             = digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.client_key
  token                  = digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.token
  cluster_ca_certificate = base64decode(digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.cluster_ca_certificate)
}

provider "kubectl" {
  host                   = digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.host
  cluster_ca_certificate = base64decode(digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.cluster_ca_certificate)
  token                  = digitalocean_kubernetes_cluster.nautobot_cluster.kube_config.0.token
  load_config_file       = false
}

data "digitalocean_droplet_snapshot" "containerlab-snapshot" {
  name_regex  = "^containerlab-latest"
  region      = "nyc3"
  most_recent = true
}

resource "digitalocean_droplet" "containerlab-droplet" {
  image  = data.digitalocean_droplet_snapshot.containerlab-snapshot.id
  name   = "containerlab"
  region = "nyc3"
  size   = "s-4vcpu-16gb-amd"
}

resource "digitalocean_project_resources" "nautobot_project" {
  project = data.digitalocean_project.nautobot_project.id
  resources = [
    digitalocean_kubernetes_cluster.nautobot_cluster.urn,
    digitalocean_droplet.containerlab-droplet.urn,
  ]
}

resource "kubectl_manifest" "static-routes-operator" {
    depends_on = [digitalocean_kubernetes_cluster.nautobot_cluster]
    wait = true
    for_each  = data.kubectl_file_documents.static-routes-manifest.manifests
    yaml_body = each.value
    override_namespace = "static-routes"
}

resource "kubectl_manifest" "static-routes" {
  depends_on = [kubectl_manifest.static-routes-operator]
  wait = true
  yaml_body = <<_EOF
apiVersion: networking.digitalocean.com/v1
kind: StaticRoute
metadata:
  name: static-routes
spec:
  destinations: 
    - "172.20.20.0/24"
  gateway: "${ digitalocean_droplet.containerlab-droplet.ipv4_address_private }"
_EOF
}
