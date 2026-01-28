import urllib.request
import json

# --- PON TU API KEY AQUÍ ---
API_KEY = "AIzaSyDfsmcK0FdfDs3ZzWn2sUINYqpEFEwCHlo"

print("📡 Consultando catálogo de modelos disponibles para tu clave...")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode("utf-8"))

        print("\n✅ CONEXIÓN EXITOSA. Estos son los modelos que TU clave puede ver:\n")
        encontrados = []
        for model in data.get("models", []):
            # Filtramos solo los que sirven para generar texto (generateContent)
            if "generateContent" in model.get("supportedGenerationMethods", []):
                print(f"🔹 {model['name']}")
                encontrados.append(model["name"])

        if not encontrados:
            print(
                "\n⚠️ RARO: Tu clave funciona, pero no tiene modelos de generación de texto habilitados."
            )
        else:
            print(
                "\n💡 COPIA UNO DE LOS NOMBRES DE ARRIBA (ej: models/gemini-pro) PARA USARLO EN EL SCRIPT."
            )

except urllib.error.HTTPError as e:
    print(f"\n❌ Error HTTP {e.code}: {e.read().decode('utf-8')}")
    if e.code == 400:
        print("👉 Tu API Key podría ser inválida.")
except Exception as e:
    print(f"\n❌ Error: {e}")
