import json
import boto3
import os
import urllib.request
import urllib.error
import time
import random

s3_client = boto3.client("s3")

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Usamos la clave manual para bypass de problemas de inyección de Terraform
API_KEY_MANUAL = "AIzaSyDsckFJBiX_5mtPHXPUgAudGbO0LDUvFkQ"


def invocar_gemini(prompt, intentos=3):
    """
    Cliente robusto para Gemini Flash Latest.
    Incluye 'Exponential Backoff' para evitar errores de cuota (429).
    """
    api_key = API_KEY_MANUAL.strip()
    # Usamos el alias 'latest' que apunta a la versión estable con mejor cuota gratuita
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
            # Estrategia de reintento exponencial con Jitter (ruido aleatorio)
            # Intento 1: espera ~2s | Intento 2: espera ~4s | Intento 3: espera ~8s
            wait_time = (2**i) + random.uniform(0, 1)
            print(
                f"⚠️ Alerta Google (Código {e.code}). Reintentando en {wait_time:.1f}s..."
            )
            time.sleep(wait_time)
            continue

        except Exception as e:
            print(f"❌ Error de conexión: {str(e)}. Reintentando...")
            time.sleep(2)
            continue

    return "Error Fatal: Se agotaron los reintentos con la IA. Google está saturado."


# --- AGENTE 2: ANALISTA (ADAPTADO A JSON 'DEEP DIVE') ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Procesando reporte forense...")
    try:
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        # 1. Leer archivo de S3
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))

        # 2. Extraer datos (Soporte para estructura nueva y vieja)
        hallazgos = datos.get("hallazgos_criticos", {})

        # A) Logs Gigantes
        logs_criticos = []
        for log in hallazgos.get("top_log_consumers", []):
            logs_criticos.append(
                f"LOG GROUP: {log['name']} | TAMAÑO: {log['size_gb']} GB"
            )

        # B) Configs ECS
        ecs_issues = []
        for issue in hallazgos.get("ecs_misconfigurations", []):
            ecs_issues.append(
                f"ECS SVC: {issue['service']} | CONFIG: {issue['bad_config']}"
            )

        # Fallback para JSON antiguo si el nuevo está vacío
        if not logs_criticos and not ecs_issues:
            aws_data = datos.get("aws_data", {})
            logs_criticos = [
                f"Legacy Costo: {k} ${v}"
                for k, v in aws_data.get("last_month_costs", {}).items()
                if v > 50
            ]

        print(
            f"   > Hallazgos: {len(logs_criticos)} Logs Críticos | {len(ecs_issues)} Configs ECS."
        )

        return {
            "status": "OK",
            "logs_gigantes": logs_criticos,
            "ecs_problemas": ecs_issues,
            "tipo_analisis": datos.get("analisis_tipo", "General"),
        }
    except Exception as e:
        print(f"❌ Error Agente 2: {str(e)}")
        return {"status": "ERROR", "error": str(e)}


# --- AGENTE 3: ESTRATEGA ---
def agente_estratega(event, context):
    print("🧠 [Agente 3] Diseñando estrategia de remediación...")

    logs = event.get("logs_gigantes", [])
    ecs = event.get("ecs_problemas", [])
    tipo = event.get("tipo_analisis", "General")

    # Prompt optimizado para ser conciso y ahorrar tokens
    prompt = f"""
    Eres un Arquitecto AWS Senior. Analiza este reporte de auditoría ({tipo}):
    
    1. LOGS CRÍTICOS (Consumen mucho almacenamiento):
    {logs}
    
    2. CONFIGURACIONES DE APLICACIÓN (Posible causa raíz):
    {ecs}
    
    OBJETIVO:
    Genera un plan técnico de 3 pasos numerados para:
    1. Limpiar el almacenamiento inmediatamente (Retention Policy).
    2. Corregir la causa raíz en la aplicación (Log Level).
    3. Prevenir futuros incidentes (Alarmas).
    
    Responde SOLO con la lista de pasos. Sé directo.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR DE CÓDIGO ---
def agente_generador(event, context):
    print("👷 [Agente 4] Escribiendo script de Python...")

    plan = event.get("plan_maestro", "")

    if "Error Fatal" in plan:
        return {"resultado": "FALLO_PREVIO", "mensaje": "El Agente 3 falló."}

    prompt = f"""
    Eres un experto DevOps en Python y Boto3.
    Escribe un script de Python COMPLETO Y LISTO PARA EJECUTAR que implemente este plan:
    {plan}
    
    REGLAS TÉCNICAS:
    1. Usa 'boto3'.
    2. Para los Logs Gigantes: Genera código que aplique 'put_retention_policy' (7 días).
    3. Para Alarmas: Genera código 'put_metric_alarm'.
    4. NO incluyas explicaciones de texto, SOLO EL CÓDIGO.
    5. NO uses bloques markdown (```). Devuelve el código puro.
    """

    script = invocar_gemini(prompt)

    # Limpieza final
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini Flash Latest",
        "script_generado": script_limpio,
    }
