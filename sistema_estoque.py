import streamlit as st
import pandas as pd
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Gestão 4.0",
    layout="wide", # Tela cheia para caber os botões
    initial_sidebar_state="collapsed" # Esconde a barra lateral
)

# --- 2. CONFIGURAÇÃO DO BANCO DE DADOS ---
ARQUIVO_DADOS = "banco_dados.csv"

def inicializar_banco_dados():
    # Se o arquivo não existir, cria com as colunas padrão
    if not os.path.exists(ARQUIVO_DADOS):
        colunas = [
            "Produto",      # Nome do item
            "Categoria",    # Café ou Perecíveis
            "Local",        # Central, Sto Amaro, Sta Izabel
            "Quantidade",   # Saldo atual
            "Minimo",       # Ponto de pedido
            "Custo",        # Preço de custo
            "Fornecedor"    # Quem vende
        ]
        df = pd.DataFrame(columns=colunas)
        df.to_csv(ARQUIVO_DADOS, index=False)

# Executa a criação do banco ao abrir o sistema
inicializar_banco_dados()

# --- 3. CONTROLE DE NAVEGAÇÃO ---
# Isso faz o sistema lembrar em qual tela você está
if 'tela_atual' not in st.session_state:
    st.session_state['tela_atual'] = "Produtos" # Começa no cadastro para facilitar

# --- 4. O MENU (DESIGN DE APLICATIVO) ---
st.markdown("<h1 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h1>", unsafe_allow_html=True)
st.markdown("---")

# Criação das 6 colunas para os botões
col1, col2, col3, col4, col5, col6 = st.columns(6)

def criar_botao_menu(coluna, texto, icone, nome_tela):
    # Se for a tela atual, o botão fica destacado (primary), senão fica cinza (secondary)
    estilo = "primary" if st.session_state['tela_atual'] == nome_tela else "secondary"
    with coluna:
        if st.button(f"{icone}\n{texto}", use_container_width=True, type=estilo):
            st.session_state['tela_atual'] = nome_tela
            st.rerun() # Recarrega a página para mudar a tela imediatamente

# Desenhando os botões
criar_botao_menu(col1, "Estoque", "📦", "Estoque")
criar_botao_menu(col2, "Transferir", "🚚", "Transferencia")
criar_botao_menu(col3, "Compras", "🛒", "Compras")
criar_botao_menu(col4, "Produtos", "📋", "Produtos")
criar_botao_menu(col5, "Vendas", "📉", "Vendas")
criar_botao_menu(col6, "Sugestões", "💡", "Sugestoes")

st.markdown("---")

# --- 5. ROTEAMENTO DAS TELAS ---
tela = st.session_state['tela_atual']

if tela == "Estoque":
    st.subheader("📦 Controle de Estoque (Entrada e Baixa)")
    st.info("Aqui vamos criar a lógica para somar e subtrair produtos.")

elif tela == "Transferencia":
    st.subheader("🚚 Transferência entre Locais")
    st.info("Aqui vamos criar a lógica para mover do Central para os Hospitais.")

elif tela == "Compras":
    st.subheader("🛒 Pedidos de Compra")
    st.info("Aqui vamos gerar os PDFs e Excel para fornecedores.")

elif tela == "Produtos":
    st.subheader("📋 Cadastro de Produtos")
    st.info("Aqui vamos cadastrar itens nas categorias Café e Perecíveis.")

elif tela == "Vendas":
    st.subheader("📉 Baixa por Planilha")
    st.info("Aqui faremos o upload do relatório de vendas.")

elif tela == "Sugestoes":
    st.subheader("💡 Sugestões Inteligentes")
    st.info("Aqui o sistema dirá o que comprar automaticamente.")
