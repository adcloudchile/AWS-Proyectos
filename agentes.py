import json
import boto3
import os
import urllib.request
import urllib.error
import time

s3_client = boto3.client("s3")


def invocar_gemini(prompt, intentos=3):
    """
    Cliente para Google Gemini usando el alias 'gemini-flash-latest'
    que garantiza mejor disponibilidad en capa gratuita.
    """
    # 1. Limpieza de API Key
    raw_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = raw_key.strip().replace("'", "").replace('"', "")

    if not api_key:
        return "ERROR: La variable GEMINI_API_KEY está vacía."

    # --- CAMBIO CLAVE: Usamos el alias estable ---
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    json_data = json.dumps(data).encode("utf-8")

    # Lógica de reintento simple
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
            if e.code == 429:  # Too Many Requests
                print(
                    f"⚠️ Cuota excedida (Intento {i+1}/{intentos}). Esperando 5 seg..."
                )
                time.sleep(5)  # Esperar antes de reintentar
                continue
            else:
                error_body = e.read().decode("utf-8")
                return f"Error Google ({e.code}): {error_body}"
        except Exception as e:
            return f"Error Script: {str(e)}"

    return "Error: Se agotaron los reintentos con la IA."


# --- AGENTE 2: ANALISTA ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Analizando datos...")
    try:
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))
        aws_data = datos.get("aws_data", {})

        # Filtros
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
    print("🧠 [Agente 3] Consultando Gemini...")

    costos = event.get("costos", [])
    seguridad = event.get("seguridad", [])

    prompt = f"""
    Eres un Arquitecto AWS. Analiza:
    COSTOS ALTOS: {costos}
    VULNERABILIDADES: {seguridad}
    
    Dame 3 acciones de remediación técnicas y breves.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Generando código Python...")

    plan = event.get("plan_maestro", "")

    prompt = f"""
    Eres experto en Python Boto3.
    Crea un script para:
    {plan}
    
    SOLO código Python puro. Sin markdown.
    """

    script = invocar_gemini(prompt)
    script_limpio = script.replace("```python", "").replace("```", "")

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini Flash Latest",
        "script_generado": script_limpio,
    }
