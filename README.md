# Smart Flow | Sprint 4

# ✅ Resumo Geral do Sistema

## 🔗 1. Integração com IoT (ESP32 + RFID + Servo + LED)
O ESP32 detecta um cartão RFID autorizado.
Ao ler o cartão, envia um POST /alerta com o uid para o Flask via Wi-Fi.
O Flask:
Marca o carrinho como "Aberto".
Dispara um alerta em tempo real para o frontend com WebSocket (Flask-SocketIO).
O servo motor e LEDs podem ser controlados no próprio ESP32 (ex: abrir carrinho, acender LED verde/vermelho).

## 📦 2. Controle de Estoque
Itens são armazenados com:
Código (ex: código de barras)
Nome
Quantidade atual

## 🧾 3. Baixa de Itens (com Scanner ou Digitação)
A tela de baixa permite que o usuário:
Escaneie um item com leitor de código de barras (que age como teclado).
O item é automaticamente baixado do estoque (quantidade -1).
A retirada é registrada no histórico com data/hora.

## 🧠 4. Cadastro de Cartões RFID Autorizados
Cada UID RFID pode estar associado a um nome (ex: "Enfermeira Ana").
Isso permite identificar quem abriu o carrinho no alerta.

## 📄 5. Geração e Download de Relatório
O sistema pode gerar um relatório de saídas (relatorio_saida.txt) com:
Data e hora da retirada
Nome do item
Permite baixar o relatório diretamente do navegador.

## ⚡ 6. Alerta em Tempo Real no Navegador
Assim que o ESP32 envia o alerta, o navegador exibe:
Nome da pessoa
Data/hora da abertura do carrinho
Usa WebSockets com Flask-SocketIO para atualização imediata.

## 🧑‍⚕️ 7. Interface Simples e Clara para Enfermeiras
Layout com Tailwind CSS e navegação limpa:
Página de baixa (/)
Página de estoque (/estoque)
Compatível com leitores de código de barras USB.
