# --- 1. CONFIGURACIÓN DE MEMORIA (BACKEND) ---
terraform {
  backend "s3" {
    # ⚠️ REEMPLAZA ESTO CON TU BUCKET DE ESTADO REAL (El que creaste a mano)
    bucket = "adcloudchile-backend" 
    key    = "agentes-forenses/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}

# --- 2. EMPAQUETADO DEL CÓDIGO PYTHON ---
data "archive_file" "codigo_agentes" {
  type        = "zip"
  source_file = "agentes.py"
  output_path = "agentes.zip"
}

# --- 3. ROLES Y PERMISOS PARA LAMBDAS ---
resource "aws_iam_role" "iam_para_lambda" {
  name = "AgentesForenseRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Permiso para escribir Logs en CloudWatch (Vital para debug)
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.iam_para_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- 4. LOS 3 AGENTES (LAMBDAS CON PYTHON 3.12) ---

resource "aws_lambda_function" "agente_analista" {
  function_name    = "Agente2_Analista"
  role             = aws_iam_role.iam_para_lambda.arn
  handler          = "agentes.agente_analista"
  runtime          = "python3.12"  # Actualizado
  filename         = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout          = 30
}

resource "aws_lambda_function" "agente_estratega" {
  function_name    = "Agente3_Estratega"
  role             = aws_iam_role.iam_para_lambda.arn
  handler          = "agentes.agente_estratega"
  runtime          = "python3.12"  # Actualizado
  filename         = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout          = 30
}

resource "aws_lambda_function" "agente_generador" {
  function_name    = "Agente4_Generador"
  role             = aws_iam_role.iam_para_lambda.arn
  handler          = "agentes.agente_generador"
  runtime          = "python3.12"  # Actualizado
  filename         = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout          = 30
}

# --- 5. ROLES PARA STEP FUNCTIONS ---
resource "aws_iam_role" "sfn_role" {
  name = "OrquestadorForenseRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "states.amazonaws.com" } }]
  })
}

# Permiso para que Step Function invoque a las Lambdas
resource "aws_iam_role_policy" "sfn_policy" {
  name = "PermisoInvocarLambdas"
  role = aws_iam_role.sfn_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Action = "lambda:InvokeFunction", Effect = "Allow", Resource = "*" }]
  })
}

# --- 6. EL ORQUESTADOR (STEP FUNCTION) ---
resource "aws_sfn_state_machine" "orquestador" {
  name     = "FlujoAnalisisForense"
  role_arn = aws_iam_role.sfn_role.arn

  definition = <<EOF
{
  "Comment": "Orquestación de Agentes Forenses con IA",
  "StartAt": "AgenteAnalista",
  "States": {
    "AgenteAnalista": {
      "Type": "Task",
      "Resource": "${aws_lambda_function.agente_analista.arn}",
      "Next": "AgenteEstratega"
    },
    "AgenteEstratega": {
      "Type": "Task",
      "Resource": "${aws_lambda_function.agente_estratega.arn}",
      "Next": "AgenteGenerador"
    },
    "AgenteGenerador": {
      "Type": "Task",
      "Resource": "${aws_lambda_function.agente_generador.arn}",
      "End": true
    }
  }
}
EOF
}

# --- 7. BUCKET DE INGESTA (BUZÓN) ---
resource "aws_s3_bucket" "buzon_auditoria" {
  bucket_prefix = "forense-hub-ingesta-" 
  force_destroy = true
}

# Habilitar notificación a EventBridge (Para uso futuro)
resource "aws_s3_bucket_notification" "bucket_notify" {
  bucket      = aws_s3_bucket.buzon_auditoria.id
  eventbridge = true
}

# Output para ver el nombre del bucket al final
output "bucket_ingesta_nombre" {
  value = aws_s3_bucket.buzon_auditoria.id
}