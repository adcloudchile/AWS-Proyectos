provider "aws" {
  region = "us-east-1"
}

# 1. Bucket S3 (El Buzón de entrada)
resource "aws_s3_bucket" "buzon_auditoria" {
  bucket_prefix = "forense-hub-ingesta-" 
  force_destroy = true # Permite borrar el bucket aunque tenga archivos (útil para pruebas)
}

# 2. Notificación S3 -> EventBridge
resource "aws_s3_bucket_notification" "bucket_notify" {
  bucket      = aws_s3_bucket.buzon_auditoria.id
  eventbridge = true
}

# 3. Rol IAM para Step Functions
resource "aws_iam_role" "sfn_role" {
  name = "OrquestadorForenseRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "states.amazonaws.com" } }]
  })
}

# 4. Step Function (Orquestador Simple de Prueba)
resource "aws_sfn_state_machine" "orquestador" {
  name     = "FlujoAnalisisForense"
  role_arn = aws_iam_role.sfn_role.arn

  definition = <<EOF
{
  "Comment": "Pipeline de Auditoría Inicial",
  "StartAt": "EstadoPrueba",
  "States": {
    "EstadoPrueba": {
      "Type": "Pass",
      "Result": "El sistema funciona correctamente",
      "End": true
    }
  }
}
EOF
}

# 5. Output (Para saber cómo se llama tu bucket)
output "bucket_name" {
  value = aws_s3_bucket.buzon_auditoria.id
}