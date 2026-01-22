provider "aws" {
  region = "us-east-1"
}

# --- 1. EMPAQUETADO DEL CÓDIGO (NUEVO) ---
data "archive_file" "codigo_agentes" {
  type        = "zip"
  source_file = "agentes.py"
  output_path = "agentes.zip"
}

# --- 2. ROLES Y PERMISOS LAMBDA (NUEVO) ---
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

# Permiso básico para escribir Logs en CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.iam_para_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- 3. LAS LAMBDAS (NUEVO) ---

resource "aws_lambda_function" "agente_analista" {
  function_name = "Agente2_Analista"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.agente_analista" # Archivo.Funcion
  runtime       = "python3.9"
  filename      = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout       = 10
}

resource "aws_lambda_function" "agente_estratega" {
  function_name = "Agente3_Estratega"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.agente_estratega"
  runtime       = "python3.9"
  filename      = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout       = 10
}

resource "aws_lambda_function" "agente_generador" {
  function_name = "Agente4_Generador"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.agente_generador"
  runtime       = "python3.9"
  filename      = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout       = 10
}

# --- 4. STEP FUNCTION (ACTUALIZADO) ---
# Rol para que la Step Function pueda invocar Lambdas
resource "aws_iam_role" "sfn_role" {
  name = "OrquestadorForenseRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "states.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "sfn_policy" {
  name = "PermisoInvocarLambdas"
  role = aws_iam_role.sfn_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Action = "lambda:InvokeFunction", Effect = "Allow", Resource = "*" }]
  })
}

resource "aws_sfn_state_machine" "orquestador" {
  name     = "FlujoAnalisisForense"
  role_arn = aws_iam_role.sfn_role.arn

  definition = <<EOF
{
  "Comment": "Orquestación de Agentes Forenses",
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

# --- 5. BUCKET (SE MANTIENE IGUAL) ---
resource "aws_s3_bucket" "buzon_auditoria" {
  bucket_prefix = "forense-hub-ingesta-" 
  force_destroy = true
}