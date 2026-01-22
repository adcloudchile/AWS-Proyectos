import json


def agente_analista(event, context):
    """
    AGENTE 2: Recibe datos crudos, detecta anomalías.
    """
    print("🕵️‍♂️ [Agente 2] Iniciando análisis forense...")

    # En un caso real, aquí leeríamos el JSON de S3.
    # Por ahora, simulamos el hallazgo.

    reporte = {
        "estado": "ANOMALIAS_DETECTADAS",
        "hallazgos": [
            {
                "id": "SEC-01",
                "riesgo": "ALTO",
                "desc": "Puerto SSH abierto a 0.0.0.0/0",
            },
            {"id": "COST-99", "riesgo": "MEDIO", "desc": "Instancia grande sin uso"},
        ],
    }
    return reporte


def agente_estratega(event, context):
    """
    AGENTE 3: Recibe hallazgos, decide qué hacer.
    """
    print("🧠 [Agente 3] Diseñando estrategia...")

    input_data = event  # Lo que devolvió el Agente 2
    hallazgos = input_data.get("hallazgos", [])

    plan = []
    for h in hallazgos:
        if h["riesgo"] == "ALTO":
            plan.append(f"REMEDIAR INMEDIATO: {h['desc']}")
        else:
            plan.append(f"NOTIFICAR: {h['desc']}")

    return {"plan_accion": plan}


def agente_generador(event, context):
    """
    AGENTE 4: Genera los scripts finales.
    """
    print("👷 [Agente 4] Escribiendo código de remediación...")

    input_data = event  # Lo que devolvió el Agente 3
    plan = input_data.get("plan_accion", [])

    script_final = "# Script generado automáticamente\n"
    for paso in plan:
        script_final += f"echo '{paso}'\n"

    return {"resultado": "EXITO", "script_generado": script_final}
