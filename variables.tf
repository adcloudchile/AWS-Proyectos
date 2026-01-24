# variables.tf
variable "gemini_api_key" {
  description = "API Key de Google Gemini"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email para alertas"
  type        = string
}

variable "version" {
  description = "Versión del código"
  type        = string
  default     = "1.0.0"
}

variable "environment" {
  description = "Ambiente (dev, staging, prod)"
  type        = string
  default     = "prod"
}