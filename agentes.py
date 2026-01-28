import json
import boto3
import os
import urllib.request
import urllib.error
import time
import random

s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")

# Variable global para cachear la llave
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
        secret_dict = json.loads(secret_string)

        raw_key = secret_dict["api_key"]
        CACHED_API_KEY = raw_key.strip()

        return CACHED_API_KEY
    except Exception as e:
        print(f"❌ Error crítico obteniendo secreto: {str(e)}")
        raise e


def invocar_gemini(prompt, intentos=3):
    """
    Cliente Gemini 2.0 Flash.
    """
    try:
        api_key = obtener_api_key()
    except Exception:
        return "Error Fatal: No se pudo obtener la API Key."

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
            print(f"⚠️ Intento {i+1} fallido. Código HTTP: {e.code}")
            try:
                print(f"   Respuesta Google: {e.read().decode('utf-8')[:200]}")
            except:
                pass

            if e.code == 429:
                print(f"🛑 Rate Limit. Esperando 5s...")
                time.sleep(5)
                continue
            if e.code == 403:
                return f"Error 403: Acceso Denegado."

            time.sleep(2)
            continue

        except Exception as e:
            print(f"❌ Error conexión no HTTP: {str(e)}")
            time.sleep(2)
            continue

    return f"Error Fatal: Google no respondió correctamente tras {intentos} intentos."


# --- NUEVO: API PRESIGNER (El Portero) ---
def api_presigner(event, context):
    """
    Genera URLs firmadas para que el Frontend pueda subir (PUT) o bajar (GET) archivos de S3.
    """
    print("🔑 Generando URL firmada...")
    try:
        body = json.loads(event.get("body", "{}"))
        accion = body.get("accion", "subir")  # 'subir' o 'bajar'
        nombre_archivo = body.get("archivo", f"reporte_{int(time.time())}.json")
        bucket_name = os.environ.get("BUCKET_NOMBRE")

        if accion == "subir":
            # URL para subir el reporte JSON
            url = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": bucket_name,
                    "Key": nombre_archivo,
                    "ContentType": "application/json",
                },
                ExpiresIn=300,
            )
        else:
            # URL para descargar el script Python generado
            # Asumimos que el script se guarda en la carpeta 'resultados/'
            key_resultado = f"resultados/{nombre_archivo}"
            url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket_name, "Key": key_resultado},
                ExpiresIn=300,
            )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",  # CORS para la web
            },
            "body": json.dumps({"url": url, "archivo": nombre_archivo}),
        }

    except Exception as e:
        print(f"❌ Error generando URL: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# --- AGENTE 2: ANALISTA ---
def agente_analista(event, context):
    print("🕵️‍♂️ [Agente 2] Procesando reporte...")
    try:
        if "detail" in event:
            bucket_name = event["detail"]["bucket"]["name"]
            file_key = event["detail"]["object"]["key"]

            # Ignorar si es un archivo de resultados para evitar bucles infinitos
            if file_key.startswith("resultados/"):
                return {"status": "SKIP", "razon": "Es un archivo de salida"}
        else:
            return {"status": "SKIP", "razon": "Evento no es S3 Put"}

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        datos = json.loads(response["Body"].read().decode("utf-8"))

        hallazgos = datos.get("hallazgos_criticos", {})

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
            "bucket_origen": bucket_name,  # Pasamos el nombre del bucket para usarlo después
            "archivo_origen": file_key,
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
    bucket = event.get("bucket_origen")
    archivo = event.get("archivo_origen")

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

    # Pasamos los datos del bucket al siguiente paso
    return {"plan_maestro": plan, "bucket_origen": bucket, "archivo_origen": archivo}


# --- AGENTE 4: GENERADOR ---
def agente_generador(event, context):
    print("👷 [Agente 4] Programando y Guardando...")

    plan = event.get("plan_maestro", "")
    bucket_name = event.get("bucket_origen")
    archivo_origen = event.get("archivo_origen")  # ej: reporte.json

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
    script_limpio = script.replace("```python", "").replace("```", "").strip()

    # --- NUEVO: GUARDAR RESULTADO EN S3 ---
    # Si el archivo original era 'reporte.json', el resultado será 'resultados/reporte.py'
    try:
        if bucket_name and archivo_origen:
            nombre_base = os.path.basename(archivo_origen).replace(".json", "")
            key_destino = f"resultados/{nombre_base}.py"

            s3_client.put_object(
                Bucket=bucket_name,
                Key=key_destino,
                Body=script_limpio,
                ContentType="text/x-python",
            )
            print(f"💾 Script guardado en s3://{bucket_name}/{key_destino}")

            return {
                "resultado": "EXITO",
                "script_s3_key": key_destino,
                "ia_usada": "Gemini 2.0 Flash",
                "script_generado": script_limpio,
            }
    except Exception as e:
        print(f"⚠️ Error guardando en S3: {e}")
        # Retornamos el script igual aunque falle el guardado
        return {
            "resultado": "EXITO_SIN_GUARDAR",
            "error_s3": str(e),
            "script_generado": script_limpio,
        }

    return {
        "resultado": "EXITO",
        "ia_usada": "Gemini 2.0 Flash",
        "script_generado": script_limpio,
    }
