from flask import Flask, request, jsonify
import requests
from difflib import SequenceMatcher
from flask_cors import CORS
from supabase import create_client
import os
import re


app = Flask(__name__)
CORS(app, origins=["https://b2rprojetos.flutterflow.app"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)


def limpar_texto(texto):
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9çáéíóúãõâêîôûàèìòù\s]', '', texto)  # remove pontuação e caracteres especiais
    texto = re.sub(r'\s+', ' ', texto)  # remove espaços extras
    return texto.strip()


def similaridade_boost(a, b):
    a_clean = limpar_texto(a)
    b_clean = limpar_texto(b)
    base_score = SequenceMatcher(None, a_clean, b_clean).ratio()

    termos = a_clean.split()
    if all(t in b_clean for t in termos):
        base_score += 0.2  # boost se todos os termos estiverem no título

    return min(base_score, 1.0)


@app.route('/buscar_amazon', methods=['GET'])
def buscar_amazon():
    id_projeto = request.args.get("id_projeto")
    if not id_projeto:
        print("[ERRO] id_projeto não fornecido.")
        return jsonify({"erro": "Parâmetro 'id_projeto' ausente."}), 400

    print(f"[INÍCIO] Buscando produtos para id_projeto: {id_projeto}")

    headers_supabase = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/tab_orcamento?select=id_orcamento,descricao_orcamento,amazon&id_projeto=eq.{id_projeto}",
        headers=headers_supabase
    )

    if r.status_code != 200:
        print(f"[ERRO] Falha ao buscar do Supabase: {r.status_code} - {r.text}")
        return jsonify({"erro": "Erro ao buscar dados do Supabase", "status_code": r.status_code, "resposta": r.text}), 500

    itens = r.json()
    print(f"[INFO] {len(itens)} itens encontrados para o projeto.")

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
            print(f"[SKIP] Item {id_item} já processado (amazon=True). Pulando...")
            continue

        print(f"[PROCESSANDO] Item {id_item} - '{descricao}'")

        busca = requests.get(
            "https://real-time-amazon-data.p.rapidapi.com/search",
            headers=headers_amazon,
            params={"query": descricao, "country": "BR"}
        )

        titulo, foto, url, preco = "Não encontrado", "", "Produto não localizado", 0

        if busca.status_code == 200:
            produtos = busca.json().get("data", {}).get("products", [])
            print(f"[AMAZON] {len(produtos)} produtos encontrados para '{descricao}'")

            maior_sim = 0
            melhor_produto = None

            for produto in produtos:
                titulo_busca = produto.get("product_title", "")
                sim = similaridade_boost(descricao, titulo_busca)
                print(f"[SIMILARIDADE] '{descricao}' x '{titulo_busca}' = {sim:.2f}")

                if sim > maior_sim and sim >= 0.4:
                    maior_sim = sim
                    melhor_produto = produto

            if melhor_produto:
                titulo = melhor_produto.get("product_title", "Não encontrado")
                foto = melhor_produto.get("product_photo", "")
                url = melhor_produto.get("product_url", "")
                preco_str = melhor_produto.get("product_price", "")
                if preco_str:
                    preco_str = preco_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    try:
                        preco = float(preco_str)
                    except:
                        preco = 0
        else:
            print(f"[ERRO] Erro na API Amazon: {busca.status_code} - {busca.text}")

        update = {
            "titulo_amazon": titulo,
            "foto_produto": foto,
            "url_produto": url,
            "valor_amazon": preco,
            "amazon": True
        }

        print(f"[ATUALIZANDO] id_orcamento: {id_item}, título: {titulo}, valor: {preco}")
        r2 = requests.patch(
            f"{SUPABASE_URL}/rest/v1/tab_orcamento?id_orcamento=eq.{id_item}",
            headers=headers_supabase,
            json=update
        )

        if r2.status_code not in (200, 204):
            print(f"[ERRO] Falha ao atualizar item {id_item}: {r2.status_code} - {r2.text}")

        atualizados.append({
            "id_item": id_item,
            "descricao": descricao,
            "resultado": titulo,
            "valor_amazon": preco
        })

    print(f"[FINALIZADO] {len(atualizados)} itens atualizados.")
    return jsonify({
        "status": "ok",
        "id_projeto": id_projeto,
        "itens_atualizados": atualizados
    })


if __name__ == '__main__':
    app.run()

