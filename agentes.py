import json
import boto3
import os
import urllib.request
import urllib.error
import time

s3_client = boto3.client("s3")

# --- CONFIGURACIÓN MANUAL PARA EVITAR ERRORES DE TERRAFORM ---
# Pegamos la clave directa para asegurar que no haya comillas extra ni espacios
API_KEY_MANUAL = "AIzaSyDsckFJBiX_5mtPHXPUgAudGbO0LDUvFkQ"


def invocar_gemini(prompt, intentos=3):
    """
    Cliente directo usando la configuración que validamos localmente.
    """
    # Usamos la variable manual, ignoramos las variables de entorno por ahora
    api_key = API_KEY_MANUAL.strip()

    # Usamos el modelo EXACTO que funcionó en tu prueba local
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

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
                print(f"⚠️ Cuota (429). Esperando 5s...")
                time.sleep(5)
                continue
            error_body = e.read().decode("utf-8")
            print(f"❌ Error Google {e.code}: {error_body}")
            return f"Error Google ({e.code}): {error_body}"
        except Exception as e:
            return f"Error Script: {str(e)}"

    return "Error: Se agotaron los reintentos."


# --- AGENTE 2: ANALISTA ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Analizando...")
    try:
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))
        aws_data = datos.get("aws_data", {})

        costos = [
            f"{k}: ${v}"
            for k, v in aws_data.get("last_month_costs", {}).items()
            if v > 50
        ]
        vulns = [v.get("Title") for v in aws_data.get("critical_security_issues", [])]

        return {"status": "OK", "costos": costos, "seguridad": vulns}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# --- AGENTE 3: ESTRATEGA ---
def agente_estratega(event, context):
    print("🧠 [Agente 3] Consultando Gemini 2.0...")

    costos = event.get("costos", [])
    seguridad = event.get("seguridad", [])

    # Prompt mejorado para asegurar que la respuesta sea limpia
    prompt = f"""
    Eres un Arquitecto Cloud AWS.
    Analiza:
    - Costos Altos: {costos}
    - Vulnerabilidades: {seguridad}
    
    Genera un plan de 3 pasos técnicos concretos.
    Responde SOLO con la lista de pasos.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Escribiendo Script...")

    plan = event.get("plan_maestro", "")

    prompt = f"""
    Eres un experto DevOps Python.
    Escribe un script 'boto3' para ejecutar este plan:
    {plan}
    
    REGLAS ESTRICTAS:
    1. El script debe auditar los recursos mencionados.
    2. Debe imprimir alertas si encuentra problemas.
    3. NO incluyas explicaciones.
    4. NO uses bloques de código markdown (```). Devuelve SOLO el código raw.
    """

    script = invocar_gemini(prompt)
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini 2.0 Flash (Hardcoded)",
        "script_generado": script_limpio,
    }
