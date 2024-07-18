terraform {
  backend "local" {
    path = ".terraform_state/terraform.tfstate"
  }
  required_providers {
    kubectl = {
      source  = "alekc/kubectl"
    }
    kubernetes = {}
    helm = {}
  }
}

provider helm {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

provider "kubernetes" {
  config_path    = "~/.kube/config"
}

provider "kubectl" {
  config_path    = "~/.kube/config"
}

resource "kubernetes_namespace" "namespaces" {
  for_each = toset(["cert-manager", "traefik", "external-dns", "nautobot"])
  metadata {
    name = each.value
  }
}

resource "helm_release" "cert-manager" {
  name  = "cert-manager"
  namespace = "cert-manager"
  chart = "cert-manager"
  repository = "https://charts.jetstack.io"

  set {
    name  = "crds.enabled"
    value = true
  }
}

resource "kubectl_manifest" "cert-manager-issuer" {
    depends_on = [helm_release.cert-manager]
    wait = true
    yaml_body = <<_EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    email: ${var.cert_manager_contact}
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: lets-encrypt
    solvers:
      - http01:
          ingress:
            class: traefik
_EOF
}

resource "kubernetes_secret" "external-dns-token" {
    metadata {
        name = "external-dns-token"
        namespace = "external-dns"
    }
    data = {
        "digitalocean_api_token" = var.do_dns_token
    }
    type = "generic"
}

resource "helm_release" "external-dns" {
  name  = "external-dns"
  namespace = "external-dns"
  depends_on = [kubernetes_secret.external-dns-token]
  chart = "external-dns"
  repository = "https://charts.bitnami.com/bitnami"

  set {
    name  = "provider"
    value = "digitalocean"
  }

  set_list {
    name  = "sources"
    value = ["ingress"]
  }

  set_list {
    name  = "domainFilters"
    value = [var.lab_domain]
  }

  set {
    name  = "digitalocean.secretName"
    value = "external-dns-token"
  }
}

resource "helm_release" "traefik" {
  name  = "traefik"
  namespace = "traefik"
  depends_on = [helm_release.external-dns, helm_release.cert-manager]
  chart = "traefik"
  repository = "https://helm.traefik.io/traefik"

  set {
    name  = "providers.kubernetesIngress.publishedService.enabled"
    value = true
  }
}

resource "kubectl_manifest" "redirect-middleware" {
    depends_on = [helm_release.traefik]
    wait = true
    yaml_body = <<_EOF
apiVersion: "traefik.io/v1alpha1"
kind: "Middleware"
metadata:
    name: "redirect-https"
    namespace: "traefik"
spec:
    redirectScheme:
        scheme: "https"
        permanent: true
_EOF
}

resource "helm_release" "nautobot" {
    name  = "nautobot"
    namespace = "nautobot"
    depends_on = [helm_release.cert-manager, helm_release.external-dns, helm_release.traefik]
    chart = "nautobot"
    repository = "https://nautobot.github.io/helm-charts/"
    timeout = 1200

    set {
        name = "nautobot.image.registry"
        value = var.nautobot_image_registry
    }

    set {
        name = "nautobot.db.engine"
        value = "django.db.backends.postgresql"
    }

    set {
        name = "nautobot.image.repository"
        value = var.nautobot_image_repository
    }

    set {
        name = "nautobot.image.tag"
        value = var.nautobot_image_tag
    }

    set {
        name = "ingress.enabled"
        value = true
    }

    set {
        name = "ingress.hostname"
        value = "${var.nautobot_hostname}.${var.lab_domain}"
    }

    set {
        name = "ingress.tls"
        value = true
    }

    set {
        name = "ingress.backendProtocol"
        value = "http"
    }

    set {
        name = "ingress.annotations.cert-manager\\.io/cluster-issuer"
        value = "letsencrypt"
    }

    set {
        name = "ingress.annotations.kubernetes\\.io/ingress\\.class"
        value = "traefik"
    }

    set {
        name = "ingress.annotations.traefik\\.ingress\\.kubernetes\\.io/router\\.middlewares"
        value = "traefik-redirect-https@kubernetescrd"
    }

    set {
      name = "nautobot.livenessProbe.initialDelaySeconds"
      value = 90
    }

    set {
      name = "nautobot.livenessProbe.timeoutSeconds"
      value = 60
    }

    set {
      name = "nautobot.readinessProbe.initialDelaySeconds"
      value = 90
    }

    set {
      name = "nautobot.sidecars[0].name"
      value = "ops-tools"
    }

    set {
      name = "nautobot.sidecars[0].image"
      value = "nicolaka/netshoot"
    }

    set {
      name = "nautobot.sidecars[0].command[0]"
      value = "/bin/bash"
    }

    set_list {
      name = "nautobot.sidecars[0].args"
      value = ["-c", "while true; do ping -c 5 localhost; sleep 60;done"]
    }

    set {
      name = "nautobot.extraVars[0].name"
      value = "NAUTOBOT_NAPALM_USERNAME"
    }

    set {
      name = "nautobot.extraVars[0].value"
      value = "nautobot"
    }

    set {
      name = "nautobot.extraVars[1].name"
      value = "NAUTOBOT_NAPALM_PASSWORD"
    }

    set {
      name = "nautobot.extraVars[1].value"
      value = "nautobot"
    }
}
