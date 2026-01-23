import urllib.request
import json

# PEGA TU CLAVE AQUÍ EXACTAMENTE COMO LA TIENES
API_KEY = "AIzaSyDsckFJBiX_5mtPHXPUgAudGbO0LDUvFkQ"

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
headers = {"Content-Type": "application/json"}
data = {
    "contents": [{"parts": [{"text": "Di 'Hola, la clave funciona correctamente'"}]}]
}

try:
    print(f"📡 Conectando a Google con clave: {API_KEY[:5]}...*****")
    req = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST"
    )

    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode("utf-8"))
        print("\n✅ ¡ÉXITO TOTAL! Google respondió:")
        print(res["candidates"][0]["content"]["parts"][0]["text"])

except urllib.error.HTTPError as e:
    print(f"\n❌ ERROR DE GOOGLE ({e.code}):")
    print(e.read().decode("utf-8"))
    print(
        "\n💡 PISTA: Si dice 'API not enabled', debes ir a Google Console y habilitar 'Generative Language API'."
    )
except Exception as e:
    print(f"\n❌ Error Local: {e}")
