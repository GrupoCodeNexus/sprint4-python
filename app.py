from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_socketio import SocketIO
from datetime import datetime
import os
import json
import uuid # Importa a biblioteca uuid para gerar IDs únicos

app = Flask(__name__)
socketio = SocketIO(app)

# --- Caminhos dos Arquivos JSON ---
ESTOQUE_JSON_PATH = 'estoque.json'
CARTOES_RFID_JSON_PATH = 'cartoes_rfid.json'
HISTORICO_JSON_PATH = 'historico.json' # Novo caminho para o histórico

# --- Funções Auxiliares para JSON ---
def carregar_json(caminho_arquivo, default_value=None):
    """
    Carrega dados de um arquivo JSON. Se o arquivo não existir ou for inválido,
    retorna um valor padrão.
    """
    if not os.path.exists(caminho_arquivo):
        print(f"Aviso: Arquivo '{caminho_arquivo}' não encontrado. Usando valor padrão.")
        return default_value
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Erro: Arquivo '{caminho_arquivo}' contém JSON inválido. Criando arquivo vazio.")
        # Se o JSON for inválido, podemos retornar o valor padrão ou um novo objeto
        # dependendo do comportamento desejado para evitar quebras futuras.
        # Aqui, optamos por retornar o default_value para que o sistema possa recriá-lo
        return default_value
    except Exception as e:
        print(f"Erro ao carregar '{caminho_arquivo}': {e}. Usando valor padrão.")
        return default_value

def salvar_json(caminho_arquivo, data):
    """
    Salva dados em um arquivo JSON.
    Retorna True em caso de sucesso, False em caso de erro.
    """
    try:
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar '{caminho_arquivo}': {e}")
        return False
# --- Fim Funções Auxiliares ---

# --- Carregamento Inicial dos Dados ---
# Carrega os dados do estoque
estoque_data = carregar_json(ESTOQUE_JSON_PATH, [])
estoque_por_codigo = {item['codigo']: item for item in estoque_data if 'codigo' in item}
estoque_por_nome = {item['nome'].lower(): item for item in estoque_data if 'nome' in item}

# Carrega os dados dos cartões RFID
cartoes_autorizados = carregar_json(CARTOES_RFID_JSON_PATH, {})

# Carrega os dados do histórico de saídas (novo)
historico = carregar_json(HISTORICO_JSON_PATH, [])

# Variável de status do carrinho
status_carrinho = {
    "estado": "Fechado",
    "ultimo_acesso": None,
    "responsavel": None
}
# --- Fim Carregamento Inicial ---

# --- Rota para remover item do estoque ---
@app.route("/remover_item", methods=["POST"])
def remover_item():
    """
    Remove um item do estoque baseado no código fornecido.
    """
    codigo = request.form.get("codigo")

    if not codigo:
        return redirect(url_for("ver_estoque", error_message="Código do item ausente."))

    if codigo not in estoque_por_codigo:
        return redirect(url_for("ver_estoque", error_message=f"Item com código '{codigo}' não encontrado."))

    # Remove da memória
    item_removido = estoque_por_codigo.pop(codigo)
    estoque_por_nome.pop(item_removido["nome"].lower(), None)

    # Salva no JSON
    if salvar_json(ESTOQUE_JSON_PATH, list(estoque_por_codigo.values())):
        return redirect(url_for("ver_estoque", success_message=f"Item '{item_removido['nome']}' removido com sucesso."))
    else:
        # Reverte a remoção se falhar o salvamento
        estoque_por_codigo[codigo] = item_removido
        estoque_por_nome[item_removido["nome"].lower()] = item_removido
        return redirect(url_for("ver_estoque", error_message="Erro ao salvar a remoção do item no arquivo."))


# --- NOVA FUNÇÃO AUXILIAR para adicionar/editar item no estoque ---
def _add_or_update_item_to_estoque(codigo, nome, quantidade_str, tipo, is_update=False, original_codigo=None):
    """
    Função auxiliar para adicionar ou atualizar um item no estoque.
    Retorna (True, mensagem de sucesso) ou (False, mensagem de erro).
    """
    if not codigo or not nome or not quantidade_str or not tipo:
        return False, "Todos os campos do item (código, nome, quantidade, tipo) são obrigatórios."

    try:
        quantidade = int(quantidade_str)
        if quantidade < 0:
            return False, "Quantidade não pode ser negativa."
    except ValueError:
        return False, "Quantidade deve ser um número inteiro válido."

    # Se for uma atualização e o código mudou, verifica conflito com código existente
    if is_update and original_codigo != codigo and codigo in estoque_por_codigo:
        return False, f"O novo código '{codigo}' já existe no estoque."
    # Se for uma adição ou o código não mudou, mas o código já existe (e não é o original)
    if not is_update and codigo in estoque_por_codigo:
         return False, f"O código '{codigo}' já existe no estoque. Use um código diferente."

    # Verifica conflito de nome (apenas se o nome foi alterado ou se for um novo item)
    if is_update:
        # Verifica se o nome foi alterado e se o novo nome já existe (excluindo o próprio item sendo editado)
        for item_cod, item_data in estoque_por_codigo.items():
            if item_cod != original_codigo and item_data['nome'].lower() == nome.lower():
                return False, f"O nome '{nome}' (ou uma variação) já existe no estoque."
    else: # Se for uma adição, verifica se o nome já existe
        if nome.lower() in estoque_por_nome:
            return False, f"O nome '{nome}' (ou uma variação) já existe no estoque. Use um nome diferente."


    if is_update:
        # Remove a entrada antiga se o código mudou ou apenas atualiza a existente
        if original_codigo != codigo:
            old_item = estoque_por_codigo.pop(original_codigo)
            estoque_por_nome.pop(old_item["nome"].lower(), None)
        else: # Se o código não mudou, remove a entrada de nome antiga caso o nome tenha sido alterado
            current_item = estoque_por_codigo[codigo]
            if current_item["nome"].lower() != nome.lower():
                estoque_por_nome.pop(current_item["nome"].lower(), None)

        # Atualiza o item existente ou adiciona com novo código
        estoque_por_codigo[codigo] = {
            "codigo": codigo,
            "nome": nome,
            "quantidade": quantidade,
            "tipo": tipo
        }
        estoque_por_nome[nome.lower()] = estoque_por_codigo[codigo] # Atualiza referência de nome
        
        message = f"Item '{nome}' atualizado com sucesso no estoque."
    else:
        # Adiciona o novo item
        novo_item = {
            "codigo": codigo,
            "nome": nome,
            "quantidade": quantidade,
            "tipo": tipo
        }
        estoque_por_codigo[codigo] = novo_item
        estoque_por_nome[nome.lower()] = novo_item
        message = f"Item '{nome}' adicionado com sucesso ao estoque."

    # Salva no arquivo JSON
    if salvar_json(ESTOQUE_JSON_PATH, list(estoque_por_codigo.values())):
        return True, message
    else:
        # Reverte as alterações em memória se falhar ao salvar no JSON
        if is_update:
            # Reverter a remoção/atualização
            if original_codigo != codigo:
                estoque_por_codigo[original_codigo] = old_item
                estoque_por_nome[old_item["nome"].lower()] = old_item
            else:
                 # Reverter apenas a atualização dos campos ou nome
                current_item = estoque_por_codigo[codigo]
                estoque_por_codigo[codigo] = old_item # Restore old item
                if current_item["nome"].lower() != nome.lower():
                    estoque_por_nome[current_item["nome"].lower()] = current_item # Restore old name entry
        else:
            del estoque_por_codigo[codigo]
            del estoque_por_nome[nome.lower()]
        return False, "Erro ao salvar o item no arquivo de estoque."


@app.route("/")
def adicionar_usado(): # Renomeado de 'index' para 'adicionar_usado' para clareza
    """
    Renderiza a página principal para registrar saídas (adicionar_usado.html).
    """
    return render_template("adicionar_usado.html", historico=historico, status=status_carrinho) # Atualizado para adicionar_usado.html

@app.route("/estoque")
def ver_estoque():
    """
    Renderiza a página para visualizar e gerenciar o estoque.
    """
    estoque_lista = list(estoque_por_codigo.values())
    success_message = request.args.get('success_message')
    error_message = request.args.get('error_message')
    return render_template("estoque.html", estoque=estoque_lista, status=status_carrinho,
                           success_message=success_message, error_message=error_message)

@app.route("/api/itens_nomes")
def get_itens_nomes():
    """
    Retorna uma lista de nomes de itens do estoque para autocompletar.
    """
    nomes = sorted([item['nome'] for item in estoque_por_codigo.values()])
    return jsonify(nomes)

@app.route("/scan", methods=["POST"])
def scan():
    """
    Registra a saída de um item do estoque para um paciente.
    """
    identificador = request.form.get("codigo")
    paciente = request.form.get("paciente")
    tipo_saida = request.form.get("tipo")

    if not identificador or not paciente or not tipo_saida:
        return jsonify(success=False, mensagem="Todos os campos (item, paciente, tipo) são obrigatórios.")

    item_encontrado = None
    if identificador in estoque_por_codigo:
        item_encontrado = estoque_por_codigo[identificador]
    elif identificador.lower() in estoque_por_nome:
        item_encontrado = estoque_por_nome[identificador.lower()]

    if item_encontrado:
        # Gera um ID único para o novo registro de histórico
        new_id = str(uuid.uuid4())
        registro = {
            "id": new_id, # Adiciona o ID único
            "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "item": item_encontrado["nome"],
            "tipo": tipo_saida,
            "paciente": paciente
        }
        historico.append(registro)
        salvar_json(HISTORICO_JSON_PATH, historico) # Salva o histórico atualizado
        return jsonify(success=True, **registro)

    return jsonify(success=False, mensagem="Item não encontrado. Verifique o código ou nome.")

# --- NOVAS ROTAS PARA GERENCIAMENTO DE HISTÓRICO (POR ID) ---

@app.route("/api/historico/<item_id>", methods=["GET"])
def get_historico_item(item_id):
    """
    Retorna os detalhes de um item do histórico pelo seu ID.
    Usado para preencher o modal de edição no frontend.
    """
    try:
        item_encontrado = next((item for item in historico if item.get('id') == item_id), None)
        if item_encontrado:
            return jsonify(item_encontrado)
        print(f"GET /api/historico/{item_id}: Item não encontrado.")
        return jsonify(success=False, message="Item histórico não encontrado."), 404
    except Exception as e:
        print(f"Erro inesperado na rota GET /api/historico/{item_id}: {e}")
        return jsonify(success=False, message=f"Erro interno do servidor ao buscar item: {e}"), 500

@app.route("/api/historico/<item_id>", methods=["PUT"])
def update_historico_item(item_id):
    """
    Atualiza um item específico no histórico.
    """
    try:
        data = request.form # Dados enviados pelo formulário via FormData
        updated_paciente = data.get("paciente")
        updated_item_nome = data.get("item") # O nome do item pode vir do modal
        updated_tipo = data.get("tipo")

        if not updated_item_nome or not updated_paciente or not updated_tipo:
            print(f"PUT /api/historico/{item_id}: Dados incompletos para atualização.")
            return jsonify(success=False, message="Todos os campos (item, paciente, tipo) são obrigatórios para a edição."), 400

        item_atualizado = False
        for item in historico:
            if item.get('id') == item_id:
                item['paciente'] = updated_paciente
                item['item'] = updated_item_nome # Atualiza o nome do item no histórico
                item['tipo'] = updated_tipo
                item['hora'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S") # Opcional: atualiza o timestamp
                item_atualizado = True
                break

        if item_atualizado:
            if salvar_json(HISTORICO_JSON_PATH, historico):
                print(f"PUT /api/historico/{item_id}: Item atualizado com sucesso.")
                return jsonify(success=True, message="Item atualizado com sucesso!")
            else:
                print(f"PUT /api/historico/{item_id}: Erro ao salvar histórico após atualização.")
                return jsonify(success=False, message="Erro ao salvar o histórico após atualização."), 500
        else:
            print(f"PUT /api/historico/{item_id}: Item não encontrado para atualização.")
            return jsonify(success=False, message="Item não encontrado para atualização"), 404
    except Exception as e:
        print(f"Erro inesperado na rota PUT /api/historico/{item_id}: {e}")
        return jsonify(success=False, message=f"Erro interno do servidor ao atualizar item: {e}"), 500

@app.route("/api/historico/<item_id>", methods=["DELETE"])
def delete_historico_item(item_id):
    """
    Remove um item específico do histórico pelo seu ID.
    """
    global historico # Garante que estamos modificando a lista global

    try:
        historico_atualizado = [item for item in historico if item.get('id') != item_id]

        if len(historico_atualizado) < len(historico): # Se o tamanho diminuiu, um item foi removido
            historico = historico_atualizado # Atualiza a lista em memória
            if salvar_json(HISTORICO_JSON_PATH, historico):
                print(f"DELETE /api/historico/{item_id}: Item removido do histórico com sucesso.")
                return jsonify(success=True, message="Item removido do histórico com sucesso.")
            else:
                print(f"DELETE /api/historico/{item_id}: Erro ao salvar o histórico após remoção.")
                return jsonify(success=False, message="Erro ao salvar o histórico após remoção."), 500
        else:
            print(f"DELETE /api/historico/{item_id}: Item não encontrado para remoção.")
            return jsonify(success=False, message="Item histórico não encontrado para remoção."), 404
    except Exception as e:
        print(f"Erro inesperado na rota DELETE /api/historico/{item_id}: {e}")
        return jsonify(success=False, message=f"Erro interno do servidor: {e}"), 500

# --- ROTAS PARA EDIÇÃO E ADIÇÃO NO ESTOQUE ---

@app.route("/edit_stock_item", methods=["POST"])
def edit_stock_item():
    """
    Edita um item existente no estoque.
    """
    original_codigo = request.form.get("original_codigo").strip().upper()
    updated_codigo = request.form.get("codigo").strip().upper()
    updated_nome = request.form.get("nome").strip()
    updated_quantidade_str = request.form.get("quantidade").strip()
    updated_tipo = request.form.get("tipo").strip()

    success, message = _add_or_update_item_to_estoque(
        updated_codigo, updated_nome, updated_quantidade_str, updated_tipo,
        is_update=True, original_codigo=original_codigo
    )

    if success:
        return redirect(url_for("ver_estoque", success_message=message))
    else:
        return redirect(url_for("ver_estoque", error_message=message))

@app.route("/adicionar_estoque", methods=["POST"])
def adicionar_estoque():
    """
    Adiciona um novo item ao estoque.
    """
    codigo = request.form.get("codigo").strip().upper()
    nome = request.form.get("nome").strip()
    quantidade_str = request.form.get("quantidade").strip()
    tipo = request.form.get("tipo").strip()

    success, message = _add_or_update_item_to_estoque(codigo, nome, quantidade_str, tipo)

    if success:
        return redirect(url_for('ver_estoque', success_message=message))
    else:
        return redirect(url_for('ver_estoque', error_message=message))

# --- Rotas de Alerta e Relatório ---

@app.route("/alerta", methods=["POST"])
def alerta():
    """
    Recebe um alerta de abertura de carrinho e emite via SocketIO.
    """
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
    """
    Gera um relatório de saídas em um arquivo de texto.
    """
    if not historico:
        return jsonify(success=False, mensagem="Nenhum item registrado ainda.")

    relatorio_linhas = []
    for item in historico:
        paciente_info = f" - Paciente: {item['paciente']}" if item.get('paciente') else ""
        tipo_info = f" - Tipo: {item['tipo']}" if item.get('tipo') else ""
        relatorio_linhas.append(f"{item['hora']} - {item['item']}{tipo_info}{paciente_info}")
    relatorio = "\n".join(relatorio_linhas)

    with open("relatorio_saida.txt", "w", encoding="utf-8") as f:
        f.write("Relatório de Itens Retirados\n")
        f.write("=" * 40 + "\n")
        f.write(relatorio)

    return jsonify(success=True)

@app.route("/baixar_relatorio", methods=["GET"])
def baixar_relatorio():
    """
    Permite o download do relatório de saídas.
    """
    caminho = "relatorio_saida.txt"
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    return "Relatório não encontrado", 404

if __name__ == "__main__":
    socketio.run(app, debug=True)
