import json
import boto3
import os

# Clientes AWS
s3_client = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def invocar_claude(prompt):
    """Función auxiliar para consultar a Claude 3 Haiku"""
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.1,  # Creatividad baja para que sea preciso con el código
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0", body=body
        )
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]
    except Exception as e:
        print(f"❌ Error invocando Bedrock: {e}")
        return f"Error generando respuesta IA: {str(e)}"


def agente_analista(event, context):
    """
    AGENTE 2 (LÓGICO): Lee JSON de S3, extrae costos y CVEs.
    No usa IA, usa lógica determinista para ahorrar dinero y ser rápido.
    """
    print("🕵️‍♂️ [Agente 2] Analizando datos crudos del cliente...")

    try:
        # 1. Leer archivo de S3
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        print(f"📂 Descargando: s3://{bucket_name}/{file_key}")
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        content = response["Body"].read().decode("utf-8")
        datos_cliente = json.loads(content)
        aws_data = datos_cliente.get("aws_data", {})

        # 2. Filtrar Costos Altos (> $50 USD)
        costos = aws_data.get("last_month_costs", {})
        hallazgos_costos = []
        for servicio, monto in costos.items():
            if monto > 50.0:
                hallazgos_costos.append(f"{servicio}: ${monto} USD")

        # 3. Filtrar CVEs
        vulns = aws_data.get("critical_security_issues", [])
        hallazgos_seguridad = []
        for v in vulns:
            hallazgos_seguridad.append(f"{v.get('Title')} en {v.get('Resource')}")

        # Pasamos el resumen limpio al Agente 3
        return {
            "status": "OK",
            "contexto_cliente": {
                "region": datos_cliente.get("account_region", "us-east-1"),
                "fecha": datos_cliente.get("timestamp"),
            },
            "problemas_costo": hallazgos_costos,
            "problemas_seguridad": hallazgos_seguridad,
        }

    except Exception as e:
        print(f"❌ Error leyendo S3: {e}")
        return {"status": "ERROR", "error": str(e)}


def agente_estratega(event, context):
    """
    AGENTE 3 (IA): Recibe la lista de problemas y prioriza.
    """
    print("🧠 [Agente 3] Estratega pensando con Bedrock...")

    if event.get("status") == "ERROR":
        return {"estrategia": "No se puede generar estrategia por error previo."}

    costos = event.get("problemas_costo", [])
    seguridad = event.get("problemas_seguridad", [])

    prompt = f"""
    Actúa como un Arquitecto de Soluciones AWS Senior.
    Tengo un cliente con los siguientes problemas detectados:
    
    COSTOS ELEVADOS:
    {json.dumps(costos, indent=2)}
    
    VULNERABILIDADES CRÍTICAS:
    {json.dumps(seguridad, indent=2)}
    
    Tu tarea:
    1. Selecciona las top 3 prioridades (mezcla de costo y seguridad).
    2. Define una acción técnica concreta para cada una.
    3. Devuelve SOLO un texto plano con formato de lista. NO uses Markdown.
    """

    estrategia_ia = invocar_claude(prompt)
    return {"plan_maestro": estrategia_ia, "raw_data": event}


def agente_generador(event, context):
    """
    AGENTE 4 (IA): El Programador.
    Genera el script de Python final para el cliente.
    """
    print("👷 [Agente 4] Escribiendo código de remediación...")

    plan = event.get("plan_maestro", "")

    prompt = f"""
    Eres un experto Desarrollador DevOps en Python (Boto3).
    Basado en este plan de remediación:
    {plan}
    
    Genera UN SOLO script de Python completo, listo para copiar y pegar, que:
    1. Use 'boto3' para listar los recursos afectados mencionados.
    2. Imprima por consola recomendaciones de remediación específicas para esos recursos.
    3. Si el plan menciona Security Groups o EC2, incluye funciones para auditar esos recursos.
    
    REGLAS:
    - El código debe ser robusto (try/except).
    - Incluye comentarios en español.
    - NO expliques nada antes ni después. SOLO devuelve el bloque de código Python.
    """

    script_python = invocar_claude(prompt)

    return {
        "resultado": "EXITO",
        "recomendaciones_texto": plan,
        "script_generado": script_python,
    }
