variable "do_dns_token" {
  default = ""
}

variable "lab_domain" {
    default = ""
}

variable "nautobot_hostname" {
    default = "nautobot-nyc3"
}

variable "cert_manager_contact" {
  default = ""
}

variable "nautobot_image_registry" {
  default = "ghcr.io"
}

variable "nautobot_image_repository" {
  default = "nautobot/nautobot"
}

variable "nautobot_image_tag" {
  default = "latest"
}
