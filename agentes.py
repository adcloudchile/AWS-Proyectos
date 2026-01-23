import json
import boto3
import os
import urllib.request
import urllib.error
import time
import random

s3_client = boto3.client("s3")

# --- CLAVE MANUAL ---
API_KEY_MANUAL = "AIzaSyDsckFJBiX_5mtPHXPUgAudGbO0LDUvFkQ"


def invocar_gemini(prompt, intentos=6):  # <--- AUMENTADO A 6 INTENTOS
    """
    Cliente Gemini en 'Modo Tanque'.
    Si Google da error de cuota, espera 30 segundos reales.
    """
    api_key = API_KEY_MANUAL.strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

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
            # ESTRATEGIA DE ESPERA AGRESIVA
            if e.code == 429:  # Too Many Requests
                print(
                    f"🛑 CUOTA LLENA (Intento {i+1}/{intentos}). Pausando 30 segundos para enfriar..."
                )
                time.sleep(30)  # Espera larga obligatoria
                continue

            # Otros errores (500, 503)
            wait_time = (2**i) + random.uniform(0, 1)
            print(f"⚠️ Error Google {e.code}. Reintentando en {wait_time:.1f}s...")
            time.sleep(wait_time)
            continue

        except Exception as e:
            print(f"❌ Error conexión: {e}. Reintentando...")
            time.sleep(5)
            continue

    return "Error Fatal: Google sigue saturado tras 6 intentos largos."


# --- AGENTE 2: ANALISTA ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Procesando reporte...")
    try:
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))

        hallazgos = datos.get("hallazgos_criticos", {})

        logs_criticos = []
        for log in hallazgos.get("top_log_consumers", []):
            logs_criticos.append(f"LOG: {log['name']} ({log['size_gb']} GB)")

        ecs_issues = []
        for issue in hallazgos.get("ecs_misconfigurations", []):
            ecs_issues.append(f"ECS: {issue['service']} config {issue['bad_config']}")

        # Fallback
        if not logs_criticos and not ecs_issues:
            aws_data = datos.get("aws_data", {})
            logs_criticos = [
                f"Legacy: {k} ${v}"
                for k, v in aws_data.get("last_month_costs", {}).items()
                if v > 50
            ]

        print(f"   > Datos: {len(logs_criticos)} Logs | {len(ecs_issues)} ECS.")

        return {
            "status": "OK",
            "logs_gigantes": logs_criticos,
            "ecs_problemas": ecs_issues,
            "tipo_analisis": datos.get("analisis_tipo", "General"),
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# --- AGENTE 3: ESTRATEGA ---
def agente_estratega(event, context):
    print("🧠 [Agente 3] Pensando estrategia...")

    logs = event.get("logs_gigantes", [])
    ecs = event.get("ecs_problemas", [])

    prompt = f"""
    Eres Arquitecto AWS. Analiza:
    1. LOGS GIGANTES: {logs}
    2. APPS MAL CONFIGURADAS: {ecs}
    
    Genera un plan de 3 pasos numerados para:
    1. Reducir retención de logs (7 días).
    2. Corregir Log Level en apps.
    3. Crear alarma de costos.
    
    Responde SOLO con la lista.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Programando...")

    plan = event.get("plan_maestro", "")

    if "Error Fatal" in plan:
        return {"resultado": "FALLO_PREVIO", "mensaje": plan}

    prompt = f"""
    Eres experto Python Boto3. Escribe script para:
    {plan}
    
    REGLAS:
    1. Usa 'boto3'.
    2. Implementa 'put_retention_policy' (7 días) para los logs detectados.
    3. Implementa 'put_metric_alarm'.
    4. SOLO CÓDIGO. Sin markdown.
    """

    script = invocar_gemini(prompt)
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini Flash Latest",
        "script_generado": script_limpio,
    }
