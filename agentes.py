import json
import boto3
import os
import urllib.request
import urllib.error
import time
import random

s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")

# Variable global para cachear la llave y no llamar a Secrets Manager en cada ejecución
CACHED_API_KEY = None


def obtener_api_key():
    """
    Recupera la API Key desde AWS Secrets Manager de forma segura.
    """
    global CACHED_API_KEY
    if CACHED_API_KEY:
        return CACHED_API_KEY

    secret_name = os.environ.get("SECRETS_MANAGER_KEY")
    if not secret_name:
        raise ValueError("❌ Error: Falta la variable de entorno SECRETS_MANAGER_KEY")

    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_string = response["SecretString"]
        # Terraform guardó esto como JSON: {"api_key": "..."}
        secret_dict = json.loads(secret_string)
        CACHED_API_KEY = secret_dict["api_key"]
        return CACHED_API_KEY
    except Exception as e:
        print(f"❌ Error crítico obteniendo secreto: {str(e)}")
        raise e


def invocar_gemini(prompt, intentos=3):
    """
    Cliente Gemini usando credenciales seguras.
    """
    try:
        api_key = obtener_api_key()
    except Exception:
        return "Error Fatal: No se pudo obtener la API Key."

    # Usamos el modelo estable 1.5 en lugar de 'latest' para evitar errores 404
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    json_data = json.dumps(data).encode("utf-8")

    for i in range(intentos):
        try:
            req = urllib.request.Request(
                url, data=json_data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                try:
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    return f"Respuesta inesperada: {json.dumps(result)}"

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"🛑 Rate Limit (429). Esperando 5s...")
                time.sleep(5)
                continue
            if e.code == 403:
                return f"Error 403: La API Key no tiene permisos o facturación activa. Revisa Google Cloud."

            print(f"⚠️ Error Google {e.code}. Reintentando...")
            time.sleep(2)
            continue

        except Exception as e:
            print(f"❌ Error conexión: {e}. Reintentando...")
            time.sleep(2)
            continue

    return "Error Fatal: Google no respondió tras varios intentos."


# --- AGENTE 2: ANALISTA ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Procesando reporte...")
    try:
        # Lógica para soportar invocación directa o vía EventBridge/S3
        if "detail" in event:
            bucket_name = event["detail"]["bucket"]["name"]
            file_key = event["detail"]["object"]["key"]
        else:
            # Fallback para pruebas manuales si el evento es distinto
            print("⚠️ Evento no estándar, buscando datos simulados...")
            return {"status": "SKIP", "razon": "Evento no es S3 Put"}

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))

        hallazgos = datos.get("hallazgos_criticos", {})

        # Extracción segura de datos
        logs_criticos = []
        if "top_log_consumers" in hallazgos:
            for log in hallazgos["top_log_consumers"]:
                logs_criticos.append(
                    f"LOG: {log.get('name')} ({log.get('size_gb')} GB)"
                )

        ecs_issues = []
        if "ecs_misconfigurations" in hallazgos:
            for issue in hallazgos["ecs_misconfigurations"]:
                ecs_issues.append(
                    f"ECS: {issue.get('service')} config {issue.get('bad_config')}"
                )

        print(f"   > Datos: {len(logs_criticos)} Logs | {len(ecs_issues)} ECS.")

        return {
            "status": "OK",
            "logs_gigantes": logs_criticos,
            "ecs_problemas": ecs_issues,
            "tipo_analisis": datos.get("analisis_tipo", "General"),
        }
    except Exception as e:
        print(f"❌ Error en Analista: {str(e)}")
        return {"status": "ERROR", "error": str(e)}


# --- AGENTE 3: ESTRATEGA ---
def agente_estratega(event, context):
    print("🧠 [Agente 3] Pensando estrategia...")

    logs = event.get("logs_gigantes", [])
    ecs = event.get("ecs_problemas", [])

    if not logs and not ecs:
        return {"plan_maestro": "Nada que reportar. Sistema saludable."}

    prompt = f"""
    Eres Arquitecto AWS. Analiza:
    1. LOGS GIGANTES: {logs}
    2. APPS MAL CONFIGURADAS: {ecs}
    
    Genera un plan de 3 pasos numerados para solucionar esto.
    Responde SOLO con la lista.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Programando...")

    plan = event.get("plan_maestro", "")

    if "Error" in plan or "Nada que reportar" in plan:
        return {"resultado": "OMITIDO", "mensaje": plan}

    prompt = f"""
    Eres experto Python Boto3. Escribe script para:
    {plan}
    
    REGLAS:
    1. Usa 'boto3'.
    2. Maneja excepciones.
    3. SOLO CÓDIGO. Sin markdown ni explicaciones.
    """

    script = invocar_gemini(prompt)
    # Limpieza básica de markdown
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini 1.5 Flash",
        "script_generado": script_limpio,
    }
