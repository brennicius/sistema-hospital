import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Gestão 3.0", layout="centered") # Mudei para 'centered' para focar no meio
ARQUIVO_DADOS = "banco_dados.csv"

# --- LISTA DE TELAS (ICONES + NOMES) ---
OPCOES = [
    "📦 Estoque",
    "🚚 Transferência",
    "🛒 Compras",
    "📋 Controle de Produtos",
    "📉 Vendas",
    "💡 Sugestões"
]

# --- ESTADO DO MENU (MEMÓRIA) ---
# O sistema precisa lembrar em qual tela está
if 'indice_menu' not in st.session_state:
    st.session_state['indice_menu'] = 3 # Começa no 'Controle de Produtos' (Índice 3)

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        cols = ["Produto", "Categoria", "Local", "Saldo", "Minimo", "Custo", "Fornecedor"]
        df = pd.DataFrame(columns=cols)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    return pd.read_csv(ARQUIVO_DADOS)

def salvar_novo_produto(produto, categoria, fornecedor, custo, minimo):
    df = carregar_dados()
    if produto in df['Produto'].values:
        return False, "Produto já existe!"
    novo_item = {
        "Produto": produto, "Categoria": categoria, "Local": "Estoque Central",
        "Saldo": 0, "Minimo": minimo, "Custo": custo, "Fornecedor": fornecedor
    }
    pd.concat([df, pd.DataFrame([novo_item])], ignore_index=True).to_csv(ARQUIVO_DADOS, index=False)
    return True, "Produto cadastrado!"

def excluir_produto(produto):
    df = carregar_dados()
    df = df[df['Produto'] != produto]
    df.to_csv(ARQUIVO_DADOS, index=False)

# --- LAYOUT DO MENU (DESIGN NOVO) ---
st.markdown("<br>", unsafe_allow_html=True) # Espaço no topo

# Cria 3 colunas: Botão Esq | Título no Meio | Botão Dir
col_esq, col_meio, col_dir = st.columns([1, 6, 1])

with col_esq:
    if st.button("⬅️", use_container_width=True):
        st.session_state['indice_menu'] -= 1
        if st.session_state['indice_menu'] < 0:
            st.session_state['indice_menu'] = len(OPCOES) - 1 # Vai para o último

with col_dir:
    if st.button("➡️", use_container_width=True):
        st.session_state['indice_menu'] += 1
        if st.session_state['indice_menu'] >= len(OPCOES):
            st.session_state['indice_menu'] = 0 # Volta para o primeiro

# Pega a escolha atual baseada no índice
escolha_atual = OPCOES[st.session_state['indice_menu']]

# Mostra o Título Centralizado Bonito
with col_meio:
    st.markdown(f"<h1 style='text-align: center; color: #4F8BF9;'>{escolha_atual}</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True) # Linha divisória

# --- CONTEÚDO DAS TELAS ---

# 1. ESTOQUE
if escolha_atual == "📦 Estoque":
    st.info("Aqui você verá a lista de produtos e poderá adicionar/remover quantidades.")
    # (Código da Parte 3 virá aqui)

# 2. TRANSFERÊNCIA
elif escolha_atual == "🚚 Transferência":
    st.info("Aqui você moverá produtos do Central para os Hospitais.")

# 3. COMPRAS
elif escolha_atual == "🛒 Compras":
    st.info("Aqui você gerará os pedidos de compra.")

# 4. CONTROLE DE PRODUTOS (JÁ FUNCIONANDO)
elif escolha_atual == "📋 Controle de Produtos":
    df_atual = carregar_dados()
    aba_cafe, aba_pereciveis = st.tabs(["☕ Café & Insumos", "🍎 Perecíveis"])
    
    def renderizar_aba(categoria_nome):
        # Cadastro
        with st.expander(f"➕ Novo Item: {categoria_nome}"):
            with st.form(key=f"form_{categoria_nome}"):
                c1, c2 = st.columns(2)
                nome = c1.text_input("Produto")
                forn = c2.text_input("Fornecedor")
                c3, c4 = st.columns(2)
                custo = c3.number_input("Custo R$", 0.0, step=0.1)
                minimo = c4.number_input("Mínimo", 1)
                if st.form_submit_button("Salvar"):
                    ok, msg = salvar_novo_produto(nome, categoria_nome, forn, custo, minimo)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        
        # Visualização
        st.write("")
        df_filtro = df_atual[df_atual['Categoria'] == categoria_nome]
        if not df_filtro.empty:
            # Mostra dados em cards ou tabela limpa
            st.dataframe(df_filtro[['Produto', 'Fornecedor', 'Custo', 'Minimo']], use_container_width=True, hide_index=True)
            
            # Exclusão simplificada
            c_del1, c_del2 = st.columns([3, 1])
            p_del = c_del1.selectbox("Apagar item:", df_filtro['Produto'].unique(), key=f"s_{categoria_nome}", index=None, placeholder="Selecione...")
            if p_del and c_del2.button("🗑️", key=f"b_{categoria_nome}"):
                excluir_produto(p_del); st.rerun()
        else:
            st.caption("Nenhum item cadastrado.")

    with aba_cafe: renderizar_aba("Café")
    with aba_pereciveis: renderizar_aba("Perecíveis")

# 5. VENDAS
elif escolha_atual == "📉 Vendas":
    st.info("Aqui você subirá a planilha para dar baixa automática.")

# 6. SUGESTÕES
elif escolha_atual == "💡 Sugestões":
    st.info("Aqui a IA dará dicas de gestão.")
