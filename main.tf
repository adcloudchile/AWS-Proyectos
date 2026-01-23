terraform {
  backend "s3" {
    bucket = "adcloudchile-backend"
    key    = "agentes-forenses/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}

# Empaquetado automático del código Python
data "archive_file" "codigo_agentes" {
  type        = "zip"
  source_file = "agentes.py"
  output_path = "agentes.zip"
}

# --- ROLES IAM ---
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

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.iam_para_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3_read" {
  name = "PermisoLecturaS3"
  role = aws_iam_role.iam_para_lambda.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = ["s3:GetObject"],
      Resource = [
        aws_s3_bucket.buzon_auditoria.arn,
        "${aws_s3_bucket.buzon_auditoria.arn}/*"
      ]
    }]
  })
}

# --- LAMBDAS ---

# Agente 2: Rápido, solo lee S3
resource "aws_lambda_function" "agente_analista" {
  function_name    = "Agente2_Analista"
  role             = aws_iam_role.iam_para_lambda.arn
  handler          = "agentes.agente_analista"
  runtime          = "python3.12"
  filename         = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout          = 30 
}

# Agente 3: Lento, habla con IA (Timeout 5 min para reintentos)
resource "aws_lambda_function" "agente_estratega" {
  function_name    = "Agente3_Estratega"
  role             = aws_iam_role.iam_para_lambda.arn
  handler          = "agentes.agente_estratega"
  runtime          = "python3.12"
  filename         = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout          = 300 

  environment {
    variables = {
      GEMINI_API_KEY = "PON_AQUI_TU_API_KEY_DE_GOOGLE"
    }
  }
}

# Agente 4: Lento, escribe código (Timeout 5 min para reintentos)
resource "aws_lambda_function" "agente_generador" {
  function_name    = "Agente4_Generador"
  role             = aws_iam_role.iam_para_lambda.arn
  handler          = "agentes.agente_generador"
  runtime          = "python3.12"
  filename         = "agentes.zip"
  source_code_hash = data.archive_file.codigo_agentes.output_base64sha256
  timeout          = 300 

  environment {
    variables = {
      GEMINI_API_KEY = "PON_AQUI_TU_API_KEY_DE_GOOGLE"
    }
  }
}

# --- STEP FUNCTIONS (Con Semáforos de Espera) ---
resource "aws_iam_role" "sfn_role" {
  name = "OrquestadorForenseRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = { Service = "states.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "sfn_policy" {
  name = "PermisoInvocarLambdas"
  role = aws_iam_role.sfn_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "lambda:InvokeFunction",
      Effect = "Allow",
      Resource = "*"
    }]
  })
}

resource "aws_sfn_state_machine" "orquestador" {
  name     = "FlujoAnalisisForense"
  role_arn = aws_iam_role.sfn_role.arn
  definition = <<EOF
{
  "Comment": "Orquestación con Semáforos para evitar Rate Limit de Google",
  "StartAt": "AgenteAnalista",
  "States": {
    "AgenteAnalista": {
      "Type": "Task",
      "Resource": "${aws_lambda_function.agente_analista.arn}",
      "Next": "EsperarEnfriamiento1"
    },
    "EsperarEnfriamiento1": {
      "Type": "Wait",
      "Seconds": 20,
      "Next": "AgenteEstratega"
    },
    "AgenteEstratega": {
      "Type": "Task",
      "Resource": "${aws_lambda_function.agente_estratega.arn}",
      "Next": "EsperarEnfriamiento2"
    },
    "EsperarEnfriamiento2": {
      "Type": "Wait",
      "Seconds": 20,
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

# --- S3 & EVENTBRIDGE ---
resource "aws_s3_bucket" "buzon_auditoria" {
  bucket_prefix = "forense-hub-ingesta-"
  force_destroy = true
}

resource "aws_s3_bucket_notification" "bucket_notify" {
  bucket      = aws_s3_bucket.buzon_auditoria.id
  eventbridge = true
}

resource "aws_iam_role" "eventbridge_role" {
  name = "EventBridgeInvokeSFNRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = { Service = "events.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_policy" {
  name = "PermitirEjecutarSFN"
  role = aws_iam_role.eventbridge_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "states:StartExecution",
      Effect = "Allow",
      Resource = aws_sfn_state_machine.orquestador.arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "s3_trigger_sfn" {
  name = "ReglaS3aStepFunction"
  event_pattern = jsonencode({
    source      = ["aws.s3"],
    detail-type = ["Object Created"],
    detail = {
      bucket = {
        name = [aws_s3_bucket.buzon_auditoria.id]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "target_sfn" {
  rule      = aws_cloudwatch_event_rule.s3_trigger_sfn.name
  target_id = "StepFunctionTarget"
  arn       = aws_sfn_state_machine.orquestador.arn
  role_arn  = aws_iam_role.eventbridge_role.arn
}

output "bucket_ingesta_nombre" {
  value = aws_s3_bucket.buzon_auditoria.id
}