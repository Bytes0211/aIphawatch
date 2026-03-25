terraform {
  backend "s3" {
    bucket         = "alphawatch-terraform-state"
    key            = "staging/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "alphawatch-terraform-locks"
    encrypt        = true
  }
}
