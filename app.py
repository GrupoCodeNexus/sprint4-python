from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import os

app = Flask(__name__)

# Estoque inicial
estoque = {
    '123456': {'nome': 'Paracetamol', 'quantidade': 20},
    '789012': {'nome': 'Dipirona', 'quantidade': 15},
    '345678': {'nome': 'Ataduras', 'quantidade': 30},
}

# Histórico dos itens baixados
historico = []

@app.route("/")
def dar_baixa():
    return render_template("baixa.html", itens=historico)

@app.route("/estoque")
def ver_estoque():
    estoque_lista = [
        {"codigo": codigo, "nome": dados["nome"], "quantidade": dados["quantidade"]}
        for codigo, dados in estoque.items()
    ]
    return render_template("estoque.html", estoque=estoque_lista)

@app.route("/scan", methods=["POST"])
def scan():
    codigo = request.form.get("codigo")
    if not codigo:
        return jsonify(success=False, mensagem="Código vazio.")

    if codigo in estoque:
        if estoque[codigo]["quantidade"] > 0:
            estoque[codigo]["quantidade"] -= 1
            registro = {
                "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "item": estoque[codigo]["nome"]
            }
            historico.append(registro)
            return jsonify(success=True, **registro)
        else:
            return jsonify(success=False, mensagem="Item esgotado.")
    return jsonify(success=False, mensagem="Item não encontrado.")

@app.route("/gerar_relatorio", methods=["POST"])
def gerar_relatorio():
    if not historico:
        return jsonify(success=False, mensagem="Nenhum item registrado ainda.")

    relatorio = "\n".join(f"{item['hora']} - {item['item']}" for item in historico)

    with open("relatorio_saida.txt", "w", encoding="utf-8") as f:
        f.write("Relatório de Itens Retirados\n")
        f.write("=" * 40 + "\n")
        f.write(relatorio)

    return jsonify(success=True)

@app.route("/baixar_relatorio", methods=["GET"])
def baixar_relatorio():
    caminho = "relatorio_saida.txt"
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    return "Relatório não encontrado", 404

if __name__ == "__main__":
    app.run(debug=True)
