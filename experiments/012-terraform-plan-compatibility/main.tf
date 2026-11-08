terraform {
  required_version = "= 1.13.5"
}

variable "generation" {
  type    = number
  default = 1
}

module "fixture" {
  source     = "./fixture"
  generation = var.generation
}
