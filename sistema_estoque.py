import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Gestão 1.0", layout="wide")
ARQUIVO_DADOS = "banco_dados.csv"

# --- FUNÇÃO: BANCO DE DADOS ---
# Cria o arquivo se ele não existir
def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        # Colunas essenciais para começar
        cols = ["Produto", "Categoria", "Local", "Quantidade", "Minimo", "Preco", "Fornecedor"]
        df = pd.DataFrame(columns=cols)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    return pd.read_csv(ARQUIVO_DADOS)

# Carrega os dados na memória
df = carregar_dados()

# --- BARRA LATERAL (MENU) ---
st.sidebar.title("📍 Navegação")
escolha = st.sidebar.radio(
    "Ir para:",
    [
        "1. 📦 Estoque (Entrada/Baixa)",
        "2. 🚚 Transferência",
        "3. 🛒 Compras",
        "4. 📋 Controle de Produtos",
        "5. 📉 Vendas (Baixa via Planilha)",
        "6. 💡 Sugestões (IA)"
    ]
)

st.sidebar.divider()
st.sidebar.info("Sistema reconstruído do zero.")

# --- TELAS DO SISTEMA ---

# 1. TELA DE ESTOQUE
if "1. 📦 Estoque" in escolha:
    st.header("📦 Gerenciamento de Estoque")
    st.caption("Dar entrada, baixa manual e visualizar saldos por local.")
    
    # (Aqui colocaremos a lógica de ver e editar estoque)
    st.info("Aguardando desenvolvimento da Parte 2...")

# 2. TELA DE TRANSFERÊNCIA
elif "2. 🚚 Transferência" in escolha:
    st.header("🚚 Transferência entre Locais")
    st.caption("Enviar produtos do Estoque Central para os Hospitais.")
    
    # (Aqui colocaremos a lógica de mover produtos)
    st.info("Aguardando desenvolvimento...")

# 3. TELA DE COMPRAS
elif "3. 🛒 Compras" in escolha:
    st.header("🛒 Pedido de Compra")
    st.caption("Gerar romaneio de compra baseado em fornecedores.")
    
    # (Aqui colocaremos a lógica de gerar PDF de compras)
    st.info("Aguardando desenvolvimento...")

# 4. TELA DE CONTROLE DE PRODUTOS (COM ABAS)
elif "4. 📋 Controle de Produtos" in escolha:
    st.header("📋 Cadastro e Controle")
    
    # Criando as duas abas solicitadas
    aba_cafe, aba_pereciveis = st.tabs(["☕ Café", "apple Perecíveis"])
    
    with aba_cafe:
        st.subheader("Gestão de Café e Insumos")
        st.write("Aqui ficarão apenas os produtos marcados como Café.")
        
    with aba_pereciveis:
        st.subheader("Gestão de Perecíveis")
        st.write("Aqui ficarão os produtos com validade curta.")

# 5. TELA DE VENDAS
elif "5. 📉 Vendas" in escolha:
    st.header("📉 Baixa de Vendas")
    st.caption("Upload de planilha para baixa automática.")
    
    # (Aqui colocaremos o upload inteligente)
    st.info("Aguardando desenvolvimento...")

# 6. TELA DE SUGESTÕES
elif "6. 💡 Sugestões" in escolha:
    st.header("💡 Inteligência de Negócio")
    st.caption("Sugestões de gestão baseadas em dados.")
    
    # (Aqui colocaremos os cálculos inteligentes)
    st.info("Aguardando desenvolvimento...")
