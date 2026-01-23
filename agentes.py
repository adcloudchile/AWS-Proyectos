import json
import boto3
import os
import urllib.request
import urllib.error
import time

s3_client = boto3.client("s3")

# --- CLAVE MANUAL (Tu llave real) ---
API_KEY_MANUAL = "AIzaSyDsckFJBiX_5mtPHXPUgAudGbO0LDUvFkQ"


def invocar_gemini(prompt, intentos=3):
    """
    Cliente Gemini usando el alias 'gemini-flash-latest'.
    Este modelo es el estándar estable y tiene la cuota gratuita más generosa.
    """
    api_key = API_KEY_MANUAL.strip()

    # CAMBIO CRÍTICO: Usamos el alias de tu lista que apunta a la versión estable
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    json_data = json.dumps(data).encode("utf-8")

    ultimo_error = ""

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
                    return f"Respuesta inesperada de Google: {json.dumps(result)}"

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            ultimo_error = f"Error HTTP {e.code}: {error_msg}"

            if e.code == 429:  # Cuota excedida
                print(f"⚠️ Cuota llena (Intento {i+1}). Esperando 5s...")
                time.sleep(5)
                continue
            else:
                # Si es 400 o 404, no sirve reintentar
                return f"Error Fatal Google ({e.code}): {error_msg}"

        except Exception as e:
            ultimo_error = f"Excepción Script: {str(e)}"

    return f"Fallo tras {intentos} intentos. Causa: {ultimo_error}"


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
    print("🧠 [Agente 3] Consultando Gemini Flash Latest...")

    costos = event.get("costos", [])
    seguridad = event.get("seguridad", [])

    prompt = f"""
    Eres un Arquitecto AWS Senior.
    Analiza estos hallazgos críticos:
    - Costos Elevados: {costos}
    - Vulnerabilidades: {seguridad}
    
    Genera un plan de 3 pasos técnicos concretos para remediar esto.
    Responde SOLO con la lista de pasos.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Escribiendo Script...")

    plan = event.get("plan_maestro", "")

    # Si el Agente 3 falló, no intentamos generar script
    if "Error" in plan:
        return {"resultado": "FALLO_PREVIO", "mensaje": plan}

    prompt = f"""
    Eres un experto DevOps en Python y Boto3.
    Escribe un script de Python completo para ejecutar este plan:
    {plan}
    
    REGLAS:
    1. Usa la librería 'boto3'.
    2. Maneja excepciones try/except.
    3. NO incluyas explicaciones de texto.
    4. NO uses bloques markdown (```). Devuelve SOLO el código.
    """

    script = invocar_gemini(prompt)

    # Limpieza
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini Flash Latest",
        "script_generado": script_limpio,
    }
