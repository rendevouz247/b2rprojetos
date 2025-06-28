from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

RAPIDAPI_KEY = '47fd75997bmsh1ae1de830d5e64ap1db9dajsndfdb31d381d4'
SUPABASE_URL = 'https://SEU-PROJETO.supabase.co'
SUPABASE_API_KEY = 'SUA_SUPABASE_SERVICE_KEY'

@app.route('/buscar_amazon', methods=['POST'])
def buscar_amazon():
    data = request.get_json()
    id_projeto = data.get("id_projeto")
    descricoes = data.get("itens", [])

    headers_amazon = {
        "x-rapidapi-host": "real-time-amazon-data.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    headers_supabase = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    for item in descricoes:
        id_item = item.get("id_item")
        descricao = item.get("descricao_orcamento")

        # Busca na Amazon
        r = requests.get(
            "https://real-time-amazon-data.p.rapidapi.com/search",
            headers=headers_amazon,
            params={"query": descricao, "country": "US"}
        )

        if r.status_code == 200:
            resultados = r.json().get("data", [])
            if resultados:
                produto = resultados[0]  # Primeiro resultado
                titulo = produto.get("title", "")
                imagem = produto.get("product_photo", "")
                link = produto.get("product_url", "")
                preco = produto.get("price", {}).get("current_price", None)

                # Atualizar no Supabase
                patch_data = {
                    "titulo_amazon": titulo,
                    "foto_produto": imagem,
                    "url_produto": link,
                    "valor_amazon": preco
                }

                supa_resp = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/tab_orcamento?id=eq.{id_item}",
                    headers=headers_supabase,
                    json=patch_data
                )

    return jsonify({"status": "concluido", "itens_processados": len(descricoes)})

if __name__ == '__main__':
    app.run()

