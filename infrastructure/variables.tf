variable "do_token" {
  default = ""
}

variable "project_name" {
  default = "NTC Labs"
}

variable "region" {
  default = "nyc3"
}

variable "k8s_size" {
  default = "s-2vcpu-4gb"
}

variable "k8s_clustername" {
  default = "nautobot"
}

variable "k8s_version" {
  # Grab the latest version slug from `doctl kubernetes options versions`
  default = "1.30.2-do.0"
}

variable "k8s_poolname" {
  default = "worker-pool"
}

variable "k8s_count" {
  default = "4"
}

variable "kubeconfig_path" {
  description = "The path to save the kubeconfig to"
  default     = "~/.kube/"
}

