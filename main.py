from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# CONFIGURAÇÕES 🔧
RAPIDAPI_KEY = '47fd75997bmsh1ae1de830d5e64ap1db9dajsndfdb31d381d4'
SUPABASE_URL = 'https://bqmipbbutfqfbbhxzrgq.supabase.co'  # seu projeto Supabase
SUPABASE_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJxbWlwYmJ1dGZxZmJiaHh6cmdxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODAxMzcwMiwiZXhwIjoyMDYzNTg5NzAyfQ.LToADPdvVbpsYAh6kr_pNXSXOp8RN52bFTXNb2yZheQ'  # sua chave service_role

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

    # Buscar os itens da tab_orcamento com o id_projeto informado
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/tab_orcamento?select=id_orcamento,descricao_orcamento&id_projeto=eq.{id_projeto}",
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
        descricao = item["descricao_orcamento"]

        # Buscar na Amazon
        busca = requests.get(
            "https://real-time-amazon-data.p.rapidapi.com/search",
            headers=headers_amazon,
            params={"query": descricao, "country": "BR"}
        )

        if busca.status_code == 200:
            busca_json = busca.json()
            resultados = busca_json.get("data")

            # Verifica se "data" existe e tem pelo menos um resultado
            if resultados and isinstance(resultados, list) and len(resultados) > 0:
                produto = resultados[0]
                titulo = produto.get("title", "")
                foto = produto.get("product_photo", "")
                url = produto.get("product_url", "")
                preco = produto.get("price", {}).get("current_price", None)

                # Atualizar no Supabase
                update = {
                    "titulo_amazon": titulo,
                    "foto_produto": foto,
                    "url_produto": url,
                    "valor_amazon": preco
                }

                r2 = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/tab_orcamento?id_orcamento=eq.{id_item}",
                    headers=headers_supabase,
                    json=update
                )

                if r2.status_code not in (200, 204):
                    # Pode registrar log aqui se quiser
                    print(f"Erro ao atualizar item {id_item}: {r2.status_code} - {r2.text}")

                atualizados.append({
                    "id_item": id_item,
                    "descricao": descricao,
                    "titulo": titulo,
                    "valor_amazon": preco
                })

            else:
                print(f"Nenhum resultado para a busca: '{descricao}'")
        else:
            print(f"Erro na requisição Amazon: {busca.status_code} para descrição: '{descricao}'")

    return jsonify({
        "status": "ok",
        "id_projeto": id_projeto,
        "itens_atualizados": atualizados
    })


if __name__ == '__main__':
    app.run()

