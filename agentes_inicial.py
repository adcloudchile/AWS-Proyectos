import json
import boto3
import os
import urllib.request
import urllib.error
import time

s3_client = boto3.client("s3")

# --- CLAVE MANUAL ---
API_KEY_MANUAL = "AIzaSyDsckFJBiX_5mtPHXPUgAudGbO0LDUvFkQ"  # <--- Tu clave real


def invocar_gemini(prompt, intentos=3):
    """Cliente Gemini Flash Latest (Estable)"""
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
        except Exception as e:
            time.sleep(2)
            continue

    return "Error: Se agotaron los reintentos con IA."


# --- AGENTE 2: ANALISTA (ADAPTADO AL NUEVO JSON) ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Leyendo reporte Deep Dive del cliente...")
    try:
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        # Leer el JSON que subió el cliente
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))

        # --- CAMBIO IMPORTANTE: Adaptarse a la nueva estructura ---
        hallazgos = datos.get("hallazgos_criticos", {})

        # Extraer logs gigantes
        logs_criticos = []
        for log in hallazgos.get("top_log_consumers", []):
            logs_criticos.append(f"{log['name']} ({log['size_gb']} GB)")

        # Extraer configs ECS
        ecs_issues = []
        for issue in hallazgos.get("ecs_misconfigurations", []):
            ecs_issues.append(
                f"Cluster: {issue['cluster']} | Svc: {issue['service']} | Config: {issue['bad_config']}"
            )

        # Si no hay datos nuevos, buscar formato antiguo (retro-compatibilidad)
        if not logs_criticos and not ecs_issues:
            aws_data = datos.get("aws_data", {})
            logs_criticos = [
                f"Legacy Costo: {k} ${v}"
                for k, v in aws_data.get("last_month_costs", {}).items()
                if v > 50
            ]

        print(
            f"   > Datos extraídos: {len(logs_criticos)} logs críticos, {len(ecs_issues)} issues ECS."
        )

        return {
            "status": "OK",
            "logs_gigantes": logs_criticos,
            "ecs_problemas": ecs_issues,
            "tipo_analisis": datos.get("analisis_tipo", "Desconocido"),
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# --- AGENTE 3: ESTRATEGA ---
def agente_estratega(event, context):
    print("🧠 [Agente 3] Analizando estrategia de remediación...")

    logs = event.get("logs_gigantes", [])
    ecs = event.get("ecs_problemas", [])
    tipo = event.get("tipo_analisis", "General")

    prompt = f"""
    Eres un Arquitecto AWS Senior analizando un reporte de tipo: {tipo}.
    
    HALLAZGOS:
    1. Logs con Volumen Crítico: {logs}
    2. Malas Configuraciones ECS (Debug/Trace): {ecs}
    
    OBJETIVO:
    Genera un plan técnico de 3 pasos para:
    - Reducir costos de almacenamiento de logs inmediatamente.
    - Corregir configuraciones de nivel de log en aplicaciones.
    - Prevenir reincidencia.
    
    Responde SOLO con la lista de pasos numerada.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Programando solución...")

    plan = event.get("plan_maestro", "")

    prompt = f"""
    Eres un experto DevOps Python (Boto3).
    Escribe un script para ejecutar este plan:
    {plan}
    
    REGLAS:
    1. Si hay logs gigantes, genera código para ponerles retención de 7 días (put_retention_policy).
    2. Si hay ECS en DEBUG, genera código (comentado o simulado) de cómo se actualizaría la Task Definition.
    3. NO incluyas markdown. Solo código.
    """

    script = invocar_gemini(prompt)
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini Flash Latest",
        "script_generado": script_limpio,
    }
