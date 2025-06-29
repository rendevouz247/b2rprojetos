from flask import Flask, request, jsonify
import requests
from difflib import SequenceMatcher

app = Flask(__name__)

# CONFIGURAÇÕES 🔧
RAPIDAPI_KEY = '47fd75997bmsh1ae1de830d5e64ap1db9dajsndfdb31d381d4'
SUPABASE_URL = 'https://bqmipbbutfqfbbhxzrgq.supabase.co'
SUPABASE_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...zheQ'  # corta a parte sensível se for público

def similaridade(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

@app.route('/buscar_amazon', methods=['GET'])
def buscar_amazon():
    id_projeto = request.args.get("id_projeto")
    if not id_projeto:
        return jsonify({"erro": "Parâmetro 'id_projeto' ausente."}), 400

    headers_supabase = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Buscar todos os itens do projeto com o campo amazon
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/tab_orcamento"
        f"?select=id_orcamento,descricao_orcamento,amazon"
        f"&id_projeto=eq.{id_projeto}",
        headers=headers_supabase
    )

    if r.status_code != 200:
        return jsonify({"erro": "Erro ao buscar dados do Supabase", "status_code": r.status_code, "resposta": r.text}), 500

    itens = r.json()
    if not itens:
        return jsonify({"mensagem": "Nenhum item encontrado para esse id_projeto."}), 200

    headers_amazon = {
        "x-rapidapi-host": "real-time-amazon-data.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    atualizados = []

    for item in itens:
        id_item = item["id_orcamento"]
        descricao = item.get("descricao_orcamento", "").strip()
        ja_foi = item.get("amazon")

        if ja_foi is True:
            continue  # pula se já foi processado

        # Buscar na Amazon
        busca = requests.get(
            "https://real-time-amazon-data.p.rapidapi.com/search",
            headers=headers_amazon,
            params={"query": descricao, "country": "BR"}
        )

        titulo, foto, url, preco = "Não encontrado", "", "Produto não localizado", 0

        if busca.status_code == 200:
            produtos = busca.json().get("data", {}).get("products", [])
            if produtos:
                produto = produtos[0]
                titulo_busca = produto.get("product_title", "")
                if similaridade(descricao, titulo_busca) >= 0.4:
                    titulo = titulo_busca
                    foto = produto.get("product_photo", "")
                    url = produto.get("product_url", "")
                    preco_str = produto.get("product_price", "")
                    if preco_str:
                        preco_str = preco_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
                        try:
                            preco = float(preco_str)
                        except:
                            preco = 0

        # Atualizar o item no Supabase, seja com dados válidos ou 'não encontrado'
        update = {
            "titulo_amazon": titulo,
            "foto_produto": foto,
            "url_produto": url,
            "valor_amazon": preco,
            "amazon": True
        }

        r2 = requests.patch(
            f"{SUPABASE_URL}/rest/v1/tab_orcamento?id_orcamento=eq.{id_item}",
            headers=headers_supabase,
            json=update
        )

        if r2.status_code not in (200, 204):
            print(f"Erro ao atualizar item {id_item}: {r2.status_code} - {r2.text}")

        atualizados.append({
            "id_item": id_item,
            "descricao": descricao,
            "resultado": titulo,
            "valor_amazon": preco
        })

    return jsonify({
        "status": "ok",
        "id_projeto": id_projeto,
        "itens_atualizados": atualizados
    })

if __name__ == '__main__':
    app.run()

