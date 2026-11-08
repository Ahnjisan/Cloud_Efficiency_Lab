variable "generation" {
  type = number
}

resource "terraform_data" "replace_first" {
  input            = sensitive("fixture-only-sensitive-value")
  triggers_replace = var.generation
}

resource "terraform_data" "create_first" {
  input            = "public-fixture-value"
  triggers_replace = var.generation

  lifecycle {
    create_before_destroy = true
  }
}
