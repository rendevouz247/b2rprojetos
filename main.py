from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Configurações da RapidAPI e Supabase
RAPIDAPI_KEY = '47fd75997bmsh1ae1de830d5e64ap1db9dajsndfdb31d381d4'
SUPABASE_URL = 'https://SEU-PROJETO.supabase.co'
SUPABASE_API_KEY = 'SUA_SUPABASE_SERVICE_KEY'

@app.route('/buscar_amazon', methods=['POST'])
def buscar_amazon():
    data = request.get_json()
    id_projeto = data.get("id_projeto")

    if not id_projeto:
        return jsonify({"erro": "id_projeto ausente"}), 400

    headers_supabase = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Buscar todos os itens do projeto
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/tab_orcamento?select=id,descricao_orcamento&id_projeto=eq.{id_projeto}",
        headers=headers_supabase
    )

    if r.status_code != 200:
        return jsonify({"erro": "Erro ao buscar itens do Supabase"}), 500

    itens = r.json()
    headers_amazon = {
        "x-rapidapi-host": "real-time-amazon-data.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    resultados = []

    for item in itens:
        id_item = item.get("id")
        descricao = item.get("descricao_orcamento")

        # Buscar na Amazon
        res_amazon = requests.get(
            "https://real-time-amazon-data.p.rapidapi.com/search",
            headers=headers_amazon,
            params={"query": descricao, "country": "US"}
        )

        if res_amazon.status_code == 200:
            dados = res_amazon.json().get("data", [])
            if dados:
                produto = dados[0]
                titulo = produto.get("title", "")
                imagem = produto.get("product_photo", "")
                link = produto.get("product_url", "")
                preco = produto.get("price", {}).get("current_price", None)

                # Atualizar o item no Supabase
                patch = {
                    "titulo_amazon": titulo,
                    "foto_produto": imagem,
                    "url_produto": link,
                    "valor_amazon": preco
                }

                r_patch = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/tab_orcamento?id=eq.{id_item}",
                    headers=headers_supabase,
                    json=patch
                )

                resultados.append({
                    "id_item": id_item,
                    "descricao": descricao,
                    "titulo_amazon": titulo,
                    "valor_amazon": preco
                })

    return jsonify({"status": "concluido", "atualizados": resultados})

if __name__ == '__main__':
    app.run()


