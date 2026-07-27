terraform {
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

resource "helm_release" "flexetrader" {
  name       = "flexetrader"
  namespace  = "flexetrader"
  chart      = "${path.module}/../helm"
  create_namespace = true
  timeout    = 300
  wait       = true

  set {
    name  = "image.repository"
    value = var.app_image
  }

  set {
    name  = "image.tag"
    value = var.app_tag
  }
}

variable "app_image" {
  default = "flexetrader-app"
}

variable "app_tag" {
  default = "latest"
}

output "app_url" {
  value = "http://<node-ip>:30800"
}

output "rabbitmq_url" {
  value = "http://<node-ip>:31672"
}

output "grafana_url" {
  value = "http://<node-ip>:30300"
}
