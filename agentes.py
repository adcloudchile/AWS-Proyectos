import json
import boto3
import os
import urllib.request
import urllib.error

s3_client = boto3.client("s3")


def invocar_gemini(prompt):
    """
    Función que conecta AWS Lambda con Google Gemini vía API REST.
    No requiere librerías externas.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: No se configuró la API Key de Gemini."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}

    # Payload exacto que pide Google
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        req = urllib.request.Request(
            url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            # Extraer el texto de la respuesta de Google
            return result["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        print(f"❌ Error conectando con Gemini: {e}")
        return f"Error IA: {str(e)}"


# --- AGENTE 2: ANALISTA (Sin IA, extrae datos) ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Analizando datos...")
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


# --- AGENTE 3: ESTRATEGA (Con GEMINI) ---
def agente_estratega(event, context):
    print("🧠 [Agente 3] Consultando a Google Gemini...")

    prompt = f"""
    Eres un Arquitecto de Soluciones AWS experto.
    Analiza estos problemas de un cliente:
    COSTOS ALTOS: {event.get('costos')}
    VULNERABILIDADES: {event.get('seguridad')}
    
    Prioriza 3 acciones técnicas de remediación. Responde solo con la lista de acciones.
    """

    plan = invocar_gemini(prompt)
    return {"plan_maestro": plan}


# --- AGENTE 4: GENERADOR (Con GEMINI) ---
def agente_generador(event, context):
    print("👷 [Agente 4] Gemini generando código Python...")

    plan = event.get("plan_maestro", "")

    prompt = f"""
    Eres un programador experto en Python y Boto3.
    Escribe un script de Python completo para realizar estas tareas de remediación AWS:
    {plan}
    
    Requisitos:
    1. Usa la librería 'boto3'.
    2. Incluye manejo de errores (try/except).
    3. NO uses Markdown. NO incluyas explicaciones. SOLO EL CÓDIGO PYTHON PURO.
    """

    script = invocar_gemini(prompt)

    # Limpieza: A veces la IA devuelve ```python ... ```, lo limpiamos
    script_limpio = script.replace("```python", "").replace("```", "")

    return {
        "resultado": "EXITO",
        "ia_usada": "Google Gemini 1.5 Flash",
        "script_generado": script_limpio,
    }
