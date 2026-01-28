terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket         = "adcloudchile-backend"
    key            = "agentes-forenses/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = "us-east-1"
  
  default_tags {
    tags = {
      Project     = "AgentesForenses"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# --- SECRETS MANAGER ---
resource "aws_secretsmanager_secret" "gemini_api_key" {
  name                    = "gemini-api-key-${var.environment}"
  recovery_window_in_days = 7
  description             = "API Key para Google Gemini"
}

resource "aws_secretsmanager_secret_version" "gemini_api_key" {
  secret_id     = aws_secretsmanager_secret.gemini_api_key.id
  secret_string = jsonencode({
    api_key = var.gemini_api_key
  })
}

# --- S3 BUCKETS ---
resource "aws_s3_bucket" "buzon_auditoria" {
  bucket_prefix = "forense-hub-ingesta-${var.environment}-"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "buzon_auditoria" {
  bucket = aws_s3_bucket.buzon_auditoria.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "buzon_auditoria" {
  bucket = aws_s3_bucket.buzon_auditoria.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# --- NUEVO: CORS PARA S3 (Necesario para la Web App) ---
resource "aws_s3_bucket_cors_configuration" "buzon_cors" {
  bucket = aws_s3_bucket.buzon_auditoria.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = ["*"] # En producción, cambia esto por tu dominio real (ej: https://miweb.com)
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_notification" "bucket_notify" {
  bucket      = aws_s3_bucket.buzon_auditoria.id
  eventbridge = true
}

resource "aws_s3_bucket" "lambda_code" {
  bucket_prefix = "lambda-code-${var.environment}-"
}

resource "aws_s3_bucket_versioning" "lambda_code" {
  bucket = aws_s3_bucket.lambda_code.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --- EMPAQUETADO ---
data "archive_file" "codigo_agentes" {
  type        = "zip"
  source_file = "${path.module}/agentes.py"
  output_path = "${path.module}/agentes-${var.app_version}.zip"
}

resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.lambda_code.id
  key    = "agentes-${var.app_version}.zip"
  source = data.archive_file.codigo_agentes.output_path
  etag   = filemd5(data.archive_file.codigo_agentes.output_path)
}

# --- IAM ROLES ---
resource "aws_iam_role" "iam_para_lambda" {
  name               = "AgentesForenseRole-${var.environment}"
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
    Statement = [
      {
        Effect = "Allow",
        Action = ["s3:GetObject", "s3:PutObject"], # Agregado PutObject para guardar resultados
        Resource = [
          aws_s3_bucket.buzon_auditoria.arn,
          "${aws_s3_bucket.buzon_auditoria.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name = "LambdaSecretsAccess"
  role = aws_iam_role.iam_para_lambda.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "secretsmanager:GetSecretValue"
      ],
      Resource = aws_secretsmanager_secret.gemini_api_key.arn
    }]
  })
}

# --- LAMBDAS ---
# 1. Agente Analista
resource "aws_lambda_function" "agente_analista" {
  function_name = "Agente2_Analista-${var.environment}"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.agente_analista"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 256
  
  s3_bucket         = aws_s3_bucket.lambda_code.id
  s3_key            = aws_s3_object.lambda_zip.key
  source_code_hash  = data.archive_file.codigo_agentes.output_base64sha256
}

# 2. Agente Estratega
resource "aws_lambda_function" "agente_estratega" {
  function_name = "Agente3_Estratega-${var.environment}"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.agente_estratega"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 512
  
  s3_bucket         = aws_s3_bucket.lambda_code.id
  s3_key            = aws_s3_object.lambda_zip.key
  source_code_hash  = data.archive_file.codigo_agentes.output_base64sha256
  
  environment {
    variables = {
      SECRETS_MANAGER_KEY = aws_secretsmanager_secret.gemini_api_key.name
    }
  }
}

# 3. Agente Generador (Modificado para guardar en S3)
resource "aws_lambda_function" "agente_generador" {
  function_name = "Agente4_Generador-${var.environment}"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.agente_generador"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 512
  
  s3_bucket         = aws_s3_bucket.lambda_code.id
  s3_key            = aws_s3_object.lambda_zip.key
  source_code_hash  = data.archive_file.codigo_agentes.output_base64sha256
  
  environment {
    variables = {
      SECRETS_MANAGER_KEY = aws_secretsmanager_secret.gemini_api_key.name
      BUCKET_RESULTADOS   = aws_s3_bucket.buzon_auditoria.id
    }
  }
}

# 4. NUEVO: Agente Portero (API Presigner)
resource "aws_lambda_function" "api_presigner" {
  function_name = "API_Portero-${var.environment}"
  role          = aws_iam_role.iam_para_lambda.arn
  handler       = "agentes.api_presigner" # Nueva función en Python
  runtime       = "python3.12"
  timeout       = 10
  memory_size   = 128
  
  s3_bucket         = aws_s3_bucket.lambda_code.id
  s3_key            = aws_s3_object.lambda_zip.key
  source_code_hash  = data.archive_file.codigo_agentes.output_base64sha256
  
  environment {
    variables = {
      BUCKET_NOMBRE = aws_s3_bucket.buzon_auditoria.id
    }
  }
}

# --- API GATEWAY HTTP (NUEVO) ---
resource "aws_apigatewayv2_api" "api_gw" {
  name          = "AgentesAPI-${var.environment}"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "api_stage" {
  api_id      = aws_apigatewayv2_api.api_gw.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.api_gw.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.api_presigner.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ruta_firmar" {
  api_id    = aws_apigatewayv2_api.api_gw.id
  route_key = "POST /firmar-url"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_lambda_permission" "api_gw_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_presigner.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api_gw.execution_arn}/*/*"
}

# --- CLOUDWATCH LOGS ---
resource "aws_cloudwatch_log_group" "lambda_logs_analyst" {
  name              = "/aws/lambda/${aws_lambda_function.agente_analista.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "lambda_logs_strategist" {
  name              = "/aws/lambda/${aws_lambda_function.agente_estratega.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "lambda_logs_generator" {
  name              = "/aws/lambda/${aws_lambda_function.agente_generador.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "lambda_logs_presigner" {
  name              = "/aws/lambda/${aws_lambda_function.api_presigner.function_name}"
  retention_in_days = 30
}

# --- SNS PARA ALERTAS ---
resource "aws_sns_topic" "alertas" {
  name = "agentes-forenses-alertas-${var.environment}"
}

resource "aws_sns_topic_subscription" "alertas_email" {
  topic_arn = aws_sns_topic.alertas.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- STEP FUNCTIONS ---
resource "aws_iam_role" "sfn_role" {
  name = "OrquestadorForenseRole-${var.environment}"
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
    Statement = [
      {
        Action = "lambda:InvokeFunction",
        Effect = "Allow",
        Resource = "*"
      },
      {
        Action = "sns:Publish",
        Effect = "Allow",
        Resource = aws_sns_topic.alertas.arn
      }
    ]
  })
}

resource "aws_sfn_state_machine" "orquestador" {
  name     = "FlujoAnalisisForense-${var.environment}"
  role_arn = aws_iam_role.sfn_role.arn
  definition = <<EOF
{
  "Comment": "Orquestación con Resiliencia y Semáforos",
  "StartAt": "AgenteAnalista",
  "States": {
    "AgenteAnalista": {
      "Type": "Task",
      "Resource": "${aws_lambda_function.agente_analista.arn}",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "ErrorHandler"
        }
      ],
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
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 5,
          "MaxAttempts": 6,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "ErrorHandler"
        }
      ],
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
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 5,
          "MaxAttempts": 6,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "ErrorHandler"
        }
      ],
      "End": true
    },
    "ErrorHandler": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${aws_sns_topic.alertas.arn}",
        "Subject": "❌ Error en Agentes Forenses",
        "Message.$": "$"
      },
      "End": true
    }
  }
}
EOF
}

# --- EVENTBRIDGE ---
resource "aws_iam_role" "eventbridge_role" {
  name = "EventBridgeInvokeSFNRole-${var.environment}"
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
  name = "ReglaS3aStepFunction-${var.environment}"
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

# --- NUEVO: BUCKET PARA HOSTING WEB (FRONTEND) ---
resource "aws_s3_bucket" "web_hosting" {
  bucket_prefix = "forense-web-app-${var.environment}-"
  force_destroy = true # Para poder borrarlo fácil si quieres limpiar
}

# 1. Configurar como sitio web estático
resource "aws_s3_bucket_website_configuration" "web_config" {
  bucket = aws_s3_bucket.web_hosting.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html" # Importante para React Router
  }
}

# 2. Desbloquear acceso público (Necesario para una web pública)
resource "aws_s3_bucket_public_access_block" "web_public_access" {
  bucket = aws_s3_bucket.web_hosting.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# 3. Política de lectura pública (Cualquiera puede VER la web)
resource "aws_s3_bucket_policy" "web_policy" {
  bucket = aws_s3_bucket.web_hosting.id
  depends_on = [aws_s3_bucket_public_access_block.web_public_access]

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid       = "PublicReadGetObject",
        Effect    = "Allow",
        Principal = "*",
        Action    = "s3:GetObject",
        Resource  = "${aws_s3_bucket.web_hosting.arn}/*"
      }
    ]
  })
}

# --- AGREGAR A OUTPUTS ---
output "website_url" {
  value       = aws_s3_bucket_website_configuration.web_config.website_endpoint
  description = "URL pública de tu Web App"
}

output "website_bucket_name" {
  value       = aws_s3_bucket.web_hosting.id
  description = "Nombre del bucket del frontend"
}

# --- OUTPUTS ---
output "bucket_ingesta_nombre" {
  value       = aws_s3_bucket.buzon_auditoria.id
  description = "Nombre del bucket para subir reportes"
}

output "api_endpoint" {
  value       = "${aws_apigatewayv2_api.api_gw.api_endpoint}/firmar-url"
  description = "Endpoint público para subir y bajar archivos desde la Web"
}