"""Full backend to generate and store `objetivo_geral_ia` using Groq and Supabase.
Environment variables required:
  GROQ_API_KEY   –  key from https://console.groq.com
  SUPABASE_URL   –  e.g. https://xxxx.supabase.co
  SUPABASE_KEY   –  service‑role key (backend‑only)
Optionally set PORT (Render sets automatically) and HOST.
Run with: gunicorn main:app
"""

import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client

# ────────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    raise RuntimeError("Missing one or more required environment variables: GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

PROMPT_TEMPLATE = (
    "Com base nas informações abaixo, elabore o objetivo geral do projeto utilizando uma linguagem técnica, clara e objetiva, "
    "adequada para apresentação a uma comissão avaliadora.\n\n"
    "O texto deve responder às seguintes perguntas‑chave:\n"
    "- O que se pretende alcançar com o projeto, de forma ampla?\n"
    "- Que transformação ou contribuição relevante à realidade social, esportiva ou cultural o projeto proporcionará?\n\n"
    "A redação do objetivo deve incluir o que será feito, onde será feito e por quanto tempo será feito, de forma concisa e precisa.\n\n"
    "O texto não deve ultrapassar 600 caracteres com espaços.\n\n"
    "Texto base: {texto_usuario}"
)

GROQ_URL = "https://api.groq.com/v1/chat/completions"
GROQ_MODEL = "mixtral-8x7b-32768"  # escolha qualquer modelo habilitado na sua conta

# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────

def gerar_texto_groq(texto_usuario: str) -> str:
    """Envia prompt à Groq e devolve texto final (máx 600 caracteres)."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": PROMPT_TEMPLATE.format(texto_usuario=texto_usuario)}
        ],
        "temperature": 0.3,
        "max_tokens": 700,  # 600 chars ≅ 130‑150 tokens, margem de segurança
    }
    response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    texto = response.json()["choices"][0]["message"]["content"].strip()
    return texto[:600]  # corte defensivo

# ────────────────────────────────────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────────────────────────────────────

@app.route("/gerar_objetivo_geral", methods=["POST"])
def gerar_objetivo_route():
    """Payload esperado:
    {
      "projeto_id": "<uuid ou int>",
      "objetivo_geral": "texto do usuário"
    }
    """
    data = request.get_json(force=True)
    projeto_id = data.get("projeto_id")
    texto_usuario = data.get("objetivo_geral", "").strip()

    if not projeto_id or not texto_usuario:
        return jsonify({"error": "projeto_id e objetivo_geral são obrigatórios"}), 400

    try:
        texto_ia = gerar_texto_groq(texto_usuario)
    except requests.HTTPError as e:
        return jsonify({"error": f"Falha na Groq API: {e}"}), 500

    # Atualiza Supabase
    update_resp = supabase.table("tab_projeto").update({"objetivo_geral_ia": texto_ia}).eq("id", projeto_id).execute()
    if update_resp.get("status") not in (200, 201):
        return jsonify({"error": "Falha ao gravar no Supabase", "supabase_response": update_resp}), 500

    return jsonify({"objetivo_geral_ia": texto_ia})

# ────────────────────────────────────────────────────────────────────────────────
# Health‑check
# ────────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

# ────────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)