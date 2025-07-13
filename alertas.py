from fastapi import FastAPI
from datetime import datetime
import requests
import os
import uuid
import time
from supabase import create_client

app = Flask(__name__)


# ================= CONFIG ====================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "alertas_comunitarios"

TWITTER_USERNAME = "OndeTemTiroteio"  # pode alterar aqui
TWITTER_BEARER = os.getenv("TWITTER_BEARER_TOKEN")

supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# ================= ROTAS =====================
@app.get("/coletar-alertas")
def coletar_alertas():
    print("🚀 Iniciando coleta integrada de alertas")

    resultados = []

    try:
        resultados.append(coleta_inmet())
    except Exception as e:
        print(f"Erro INMET: {e}")

    try:
        resultados.append(coleta_twitter())
    except Exception as e:
        print(f"Erro Twitter: {e}")

    return {"status": "ok", "resultados": resultados}

# =============== INMET ======================
def coleta_inmet():
    print("🌩️ Coletando alertas do INMET")
    url = "https://apiprevmet3.inmet.gov.br/alerta/"
    r = requests.get(url)
    alertas = r.json()
    adicionados = 0

    for alerta in alertas:
        if alerta.get("UF") != "RJ":
            continue

        titulo = alerta.get("tipo")
        descricao = alerta.get("descricao")
        data_alerta = alerta.get("dataInicio")
        lat = alerta.get("latitude", -22.9)
        lon = alerta.get("longitude", -43.2)
        gravidade = "moderada"
        bairro = alerta.get("municipios", ["Desconhecido"])[0]

        alerta_obj = {
            "id": str(uuid.uuid4()),
            "titulo": titulo,
            "descricao": descricao,
            "origem": "INMET",
            "data_alerta": data_alerta,
            "gravidade": gravidade,
            "latitude": lat,
            "longitude": lon,
            "bairro": bairro,
            "rua": None,
            "enviado_para_moradores": False,
            "predio_id": None,
            "criado_em": datetime.utcnow().isoformat()
        }

        print("📥 Gravando alerta INMET:", titulo)
        grava_supabase(alerta_obj)
        adicionados += 1

    return f"INMET: {adicionados} alertas adicionados"

# =============== TWITTER ======================
def coleta_twitter():
    print("🐦 Coletando tweets do OTT-RJ")
    url = f"https://api.twitter.com/2/tweets/search/recent?query=from:{TWITTER_USERNAME}&tweet.fields=created_at&max_results=5"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
    r = requests.get(url, headers=headers)
    tweets = r.json().get("data", [])

    adicionados = 0
    for tweet in tweets:
        texto = tweet["text"]
        data_alerta = tweet["created_at"]

        bairro = extrair_bairro(texto)
        coords = geocodificar_bairro(bairro)

        alerta_obj = {
            "id": str(uuid.uuid4()),
            "titulo": "Tiroteio Reportado",
            "descricao": texto,
            "origem": "TIROTEIO",
            "data_alerta": data_alerta,
            "gravidade": "grave",
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "bairro": bairro,
            "rua": None,
            "enviado_para_moradores": False,
            "predio_id": None,
            "criado_em": datetime.utcnow().isoformat()
        }

        print("📥 Gravando alerta TIROTEIO:", texto[:40], "...")
        grava_supabase(alerta_obj)
        adicionados += 1

    return f"Twitter: {adicionados} tweets processados"

# ========== GEOLOCALIZAÇÃO ============
def geocodificar_bairro(bairro):
    print(f"📍 Geocodificando bairro: {bairro}")
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={bairro},Rio de Janeiro,Brasil&format=json"
        r = requests.get(url, headers={"User-Agent": "alerta-bot"})
        data = r.json()
        if data:
            return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    except:
        pass
    return {"lat": -22.9, "lon": -43.2}  # fallback para centro do RJ

# ========== EXTRAI BAIRRO ============
def extrair_bairro(texto):
    palavras_chave = [
        "Maré", "Rocinha", "Jacaré", "Bonsucesso", "Complexo", "São Carlos", "Lins", "Penha",
        "Acari", "Caju", "Cascadura", "Pavuna", "Vila Isabel", "Méier", "Engenho Novo", "Praça Seca"
    ]
    for bairro in palavras_chave:
        if bairro.lower() in texto.lower():
            return bairro
    return "Desconhecido"

# ============ GRAVAR NO SUPABASE ============
def grava_supabase(dados):
    print("🧱 Gravando no Supabase...")
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
                          headers={**HEADERS_SUPABASE, "Content-Type": "application/json"},
                          json=dados)
        print("✅ Sucesso! Status:", r.status_code)
        print(r.text)
    except Exception as e:
        print("❌ Erro ao gravar no Supabase:", e)

if __name__ == '__main__':
    app.run()
