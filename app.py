from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_socketio import SocketIO
from datetime import datetime
import os
import json

app = Flask(__name__)
socketio = SocketIO(app)

# --- Funções Auxiliares para JSON ---
def carregar_json(caminho_arquivo, default_value=None):
    if not os.path.exists(caminho_arquivo):
        print(f"Aviso: Arquivo '{caminho_arquivo}' não encontrado. Usando valor padrão.")
        return default_value
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Erro: Arquivo '{caminho_arquivo}' contém JSON inválido. Usando valor padrão.")
        return default_value
    except Exception as e:
        print(f"Erro ao carregar '{caminho_arquivo}': {e}. Usando valor padrão.")
        return default_value

def salvar_json(caminho_arquivo, data):
    try:
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar '{caminho_arquivo}': {e}")
        return False
# --- Fim Funções Auxiliares ---

# --- Carregamento Inicial dos Dados ---
ESTOQUE_JSON_PATH = 'estoque.json'
estoque_data = carregar_json(ESTOQUE_JSON_PATH, [])

# Variaveis globais para armazenar o estoque de duas formas para busca eficiente
estoque_por_codigo = {item['codigo']: item for item in estoque_data}
estoque_por_nome = {item['nome'].lower(): item for item in estoque_data}

estoque = estoque_por_codigo

CARTOES_RFID_JSON_PATH = 'cartoes_rfid.json'
cartoes_autorizados = carregar_json(CARTOES_RFID_JSON_PATH, {})

historico = []

status_carrinho = {
    "estado": "Fechado",
    "ultimo_acesso": None,
    "responsavel": None
}
# --- Fim Carregamento Inicial ---

# --- NOVA FUNÇÃO AUXILIAR PARA ADICIONAR ITEM (com tipo) ---
def _add_item_to_estoque(codigo, nome, quantidade_str, tipo):
    """
    Função auxiliar para adicionar um item ao estoque.
    Retorna (True, mensagem de sucesso) ou (False, mensagem de erro).
    """
    # Validações dos campos
    if not codigo or not nome or not quantidade_str or not tipo:
        return False, "Todos os campos do novo item (código, nome, quantidade, tipo) são obrigatórios."

    try:
        quantidade = int(quantidade_str)
        if quantidade < 0:
            return False, "Quantidade não pode ser negativa."
    except ValueError:
        return False, "Quantidade deve ser um número inteiro válido."

    if codigo in estoque_por_codigo:
        return False, f"O código '{codigo}' já existe no estoque. Use um código diferente."
    if nome.lower() in estoque_por_nome:
        return False, f"O nome '{nome}' (ou uma variação) já existe no estoque. Use um nome diferente."

    novo_item = {
        "codigo": codigo,
        "nome": nome,
        "quantidade": quantidade,
        "tipo": tipo # Inclui o novo campo 'tipo'
    }

    # Adiciona o item às estruturas de dados em memória
    estoque_por_codigo[codigo] = novo_item
    estoque_por_nome[nome.lower()] = novo_item

    # Salva no arquivo JSON
    if salvar_json(ESTOQUE_JSON_PATH, list(estoque_por_codigo.values())):
        return True, f"Item '{nome}' adicionado com sucesso ao estoque."
    else:
        # Reverte a adição em memória se falhar ao salvar no JSON
        del estoque_por_codigo[codigo]
        del estoque_por_nome[nome.lower()]
        return False, "Erro ao salvar o item no arquivo de estoque."
# --- FIM FUNÇÃO AUXILIAR ---


@app.route("/")
def add_usado():
    return render_template("adicionar_usado.html", historico=historico, status=status_carrinho)

@app.route("/estoque")
def ver_estoque():
    estoque_lista = list(estoque_por_codigo.values())
    # Captura mensagens de sucesso/erro dos parâmetros da URL
    success_message = request.args.get('success_message')
    error_message = request.args.get('error_message')
    return render_template("estoque.html", estoque=estoque_lista, status=status_carrinho,
                           success_message=success_message, error_message=error_message)

@app.route("/api/itens_nomes")
def get_itens_nomes():
    nomes = sorted(list(estoque_por_nome.keys()))
    return jsonify(nomes)

@app.route("/scan", methods=["POST"])
def scan():
    identificador = request.form.get("codigo")
    paciente = request.form.get("paciente")
    tipo_saida = request.form.get("tipo") # NOVO: Captura o tipo enviado do frontend

    if not identificador:
        return jsonify(success=False, mensagem="O campo do item está vazio.")

    item_encontrado = None

    if identificador in estoque_por_codigo:
        item_encontrado = estoque_por_codigo[identificador]
    elif identificador.lower() in estoque_por_nome:
        item_encontrado = estoque_por_nome[identificador.lower()]

    if item_encontrado:
        registro = {
            "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "item": item_encontrado["nome"],
            "tipo": tipo_saida, # NOVO: Usa o tipo recebido do formulário
            "paciente": paciente if paciente else "N/A"
        }
        historico.append(registro)
        return jsonify(success=True, **registro) # Retorna o tipo no JSON de resposta
    
    return jsonify(success=False, mensagem="Item não encontrado. Verifique o código ou nome.")

# Rota para adicionar item via AJAX (usado em adicionar_usado.html) - NÃO FOI ALTERADA, MAS MANTIDA PARA CONTEXTO
@app.route("/add_item", methods=["POST"])
def add_item():
    novo_codigo = request.form.get("novo_codigo").strip().upper()
    novo_nome = request.form.get("novo_nome").strip()
    nova_quantidade_str = request.form.get("nova_quantidade").strip()
    novo_tipo = request.form.get("novo_tipo").strip()

    success, message = _add_item_to_estoque(novo_codigo, novo_nome, nova_quantidade_str, novo_tipo)
    return jsonify(success=success, mensagem=message)

# NOVA ROTA: Para adicionar item via POST direto (usado em estoque.html)
@app.route("/adicionar_estoque", methods=["POST"])
def adicionar_estoque():
    codigo = request.form.get("codigo").strip().upper()
    nome = request.form.get("nome").strip()
    quantidade_str = request.form.get("quantidade").strip()
    tipo = request.form.get("tipo").strip() # Captura o novo campo 'tipo' do formulário

    success, message = _add_item_to_estoque(codigo, nome, quantidade_str, tipo)

    if success:
        # Redireciona para a página de estoque com mensagem de sucesso
        return redirect(url_for('ver_estoque', success_message=message))
    else:
        # Redireciona para a página de estoque com mensagem de erro
        return redirect(url_for('ver_estoque', error_message=message))


@app.route("/alerta", methods=["POST"])
def alerta():
    data = request.get_json()
    uid = data.get("uid")
    nome = cartoes_autorizados.get(uid, f"Cartão {uid}")

    status_carrinho["estado"] = "Aberto"
    status_carrinho["ultimo_acesso"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    status_carrinho["responsavel"] = nome

    socketio.emit("carrinho_aberto", {
        "responsavel": nome,
        "hora": status_carrinho["ultimo_acesso"]
    })

    return jsonify(status="ok")

@app.route("/gerar_relatorio", methods=["POST"])
def gerar_relatorio():
    if not historico:
        return jsonify(success=False, mensagem="Nenhum item registrado ainda.")

    relatorio_linhas = []
    for item in historico:
        paciente_info = f" - Paciente: {item['paciente']}" if item.get('paciente') else ""
        tipo_info = f" - Tipo: {item['tipo']}" if item.get('tipo') else "" # Adiciona o tipo ao relatório
        relatorio_linhas.append(f"{item['hora']} - {item['item']}{tipo_info}{paciente_info}")
    relatorio = "\n".join(relatorio_linhas)

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
    socketio.run(app, debug=True)