import json
import boto3

s3_client = boto3.client("s3")


def agente_analista(event, context):
    """
    AGENTE 2: Analista Financiero y de Seguridad.
    Lee el JSON de S3 y detecta anomalías en Costos y Vulnerabilidades.
    NO se conecta a la cuenta del cliente.
    """
    print("🕵️‍♂️ [Agente 2] Iniciando análisis del JSON del cliente...")

    try:
        # 1. Obtener el archivo desde S3 (Trigger de EventBridge)
        detail = event.get("detail", {})
        bucket_name = detail["bucket"]["name"]
        file_key = detail["object"]["key"]

        print(f"📂 Descargando input: s3://{bucket_name}/{file_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        content = response["Body"].read().decode("utf-8")
        datos_cliente = json.loads(content)

        aws_data = datos_cliente.get("aws_data", {})

        # --- A. ANÁLISIS DE COSTOS ---
        costos = aws_data.get("last_month_costs", {})
        hallazgos_costos = []

        # Umbral de alerta (ej: Servicios que gastan más de $100 USD)
        UMBRAL_COSTO = 100.0

        for servicio, monto in costos.items():
            if monto > UMBRAL_COSTO:
                hallazgos_costos.append(
                    {
                        "servicio": servicio,
                        "gasto": monto,
                        "mensaje": f"Gasto elevado en {servicio}: ${monto} USD",
                    }
                )

        # --- B. ANÁLISIS DE SEGURIDAD (CVEs) ---
        vulns = aws_data.get("critical_security_issues", [])
        hallazgos_seguridad = []

        for v in vulns:
            # Extraemos lo vital del JSON
            hallazgos_seguridad.append(
                {
                    "id": v.get("Title", "Unknown"),
                    "recurso": v.get("Resource", "Unknown"),
                    "descripcion": v.get("Description", "")[:100]
                    + "...",  # Cortamos para no saturar
                }
            )

        # Retornamos el diagnóstico estructurado para el Agente 3
        reporte_analista = {
            "status": "OK",
            "resumen_costos": hallazgos_costos,
            "resumen_seguridad": hallazgos_seguridad,
            "total_vulns": len(hallazgos_seguridad),
        }

        print(
            f"✅ Análisis listo. {len(hallazgos_costos)} alertas de costo, {len(hallazgos_seguridad)} CVEs."
        )
        return reporte_analista

    except Exception as e:
        print(f"❌ Error procesando el JSON: {str(e)}")
        return {"status": "ERROR", "error": str(e)}


def agente_estratega(event, context):
    """
    AGENTE 3: Estratega.
    Recibe el reporte del Agente 2 y decide QUÉ hacer.
    Genera un plan de remediación en texto plano.
    """
    print("🧠 [Agente 3] Diseñando estrategia de remediación...")

    analisis = event  # Input del Agente 2

    if analisis.get("status") == "ERROR":
        return {"plan": ["Error en etapa previa. Revisar formato JSON."]}

    plan_accion = []

    # 1. Estrategia de Costos
    costos_altos = analisis.get("resumen_costos", [])
    if costos_altos:
        plan_accion.append("--- 💰 OPTIMIZACIÓN DE COSTOS ---")
        for c in costos_altos:
            if "CloudTrail" in c["servicio"]:
                plan_accion.append(
                    f"⚠️ {c['servicio']} (${c['gasto']}): Revisar si hay 'Data Events' activados innecesariamente en todos los buckets."
                )
            elif "RDS" in c["servicio"]:
                plan_accion.append(
                    f"⚠️ {c['servicio']} (${c['gasto']}): Evaluar compra de Reserved Instances o apagar instancias de desarrollo fuera de horario."
                )
            else:
                plan_accion.append(
                    f"⚠️ {c['servicio']} (${c['gasto']}): Revisar recursos ociosos o sobredimensionados."
                )

    # 2. Estrategia de Seguridad
    vulns = analisis.get("resumen_seguridad", [])
    if vulns:
        plan_accion.append("\n--- 🛡️ PARCHADO DE SEGURIDAD ---")
        for v in vulns:
            if "Tomcat" in v["id"]:
                plan_accion.append(
                    f"🚨 CRÍTICO {v['id']}: Actualizar Apache Tomcat inmediatamente en el recurso {v['recurso']}."
                )
            elif "SnakeYaml" in v["id"]:
                plan_accion.append(
                    f"🚨 CRÍTICO {v['id']}: Actualizar librería SnakeYaml a versión 2.0+ para evitar RCE."
                )
            else:
                plan_accion.append(
                    f"🔸 {v['id']}: Revisar y aplicar parches de seguridad del proveedor."
                )

    return {"plan_final": plan_accion}


def agente_generador(event, context):
    """
    AGENTE 4: Redactor.
    Toma el plan y genera el reporte final para el cliente.
    """
    print("👷 [Agente 4] Generando entregable final...")

    plan = event.get("plan_final", [])

    # Convertimos la lista en un texto bonito
    texto_reporte = "\n".join(plan)

    # Aquí podrías guardar este reporte en otro bucket de "Salida" para que el cliente lo descargue
    # Por ahora, lo retornamos como final de la Step Function

    return {"resultado": "EXITO", "recomendaciones_cliente": texto_reporte}
