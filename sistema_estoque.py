import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Gestão 3.1", layout="centered")
ARQUIVO_DADOS = "banco_dados.csv"

# --- CONFIGURAÇÃO DO MENU (VISUAL) ---
MENU_DADOS = [
    {"nome": "Estoque", "icone": "📦"},
    {"nome": "Transferência", "icone": "🚚"},
    {"nome": "Compras", "icone": "🛒"},
    {"nome": "Produtos", "icone": "📋"},
    {"nome": "Vendas", "icone": "📉"},
    {"nome": "Sugestões", "icone": "💡"}
]

# --- ESTADO DO MENU ---
if 'indice_menu' not in st.session_state:
    st.session_state['indice_menu'] = 3 # Começa em Produtos

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
    return True, "Cadastrado!"

def excluir_produto(produto):
    df = carregar_dados()
    df = df[df['Produto'] != produto]
    df.to_csv(ARQUIVO_DADOS, index=False)

# --- LAYOUT CARROSSEL MINIMALISTA ---
st.markdown("<br>", unsafe_allow_html=True)

col_esq, col_meio, col_dir = st.columns([1, 4, 1])

# Botão Anterior
with col_esq:
    st.write("") # Espaço para alinhar verticalmente
    st.write("")
    if st.button("◀", use_container_width=True):
        st.session_state['indice_menu'] -= 1
        if st.session_state['indice_menu'] < 0:
            st.session_state['indice_menu'] = len(MENU_DADOS) - 1

# Botão Próximo
with col_dir:
    st.write("")
    st.write("")
    if st.button("▶", use_container_width=True):
        st.session_state['indice_menu'] += 1
        if st.session_state['indice_menu'] >= len(MENU_DADOS):
            st.session_state['indice_menu'] = 0

# O Desenho Central
item_atual = MENU_DADOS[st.session_state['indice_menu']]

with col_meio:
    # CSS para deixar o ícone gigante e centralizado
    st.markdown(
        f"""
        <div style="text-align: center;">
            <div style="font-size: 80px; line-height: 1;">{item_atual['icone']}</div>
            <div style="font-size: 16px; color: gray; font-weight: bold; margin-top: 10px;">{item_atual['nome']}</div>
        </div>
        <hr style="margin-top: 5px; margin-bottom: 20px;">
        """, 
        unsafe_allow_html=True
    )

# --- CONTEÚDO DAS TELAS ---

# 1. ESTOQUE
if item_atual['nome'] == "Estoque":
    st.info("Aqui você verá a lista de produtos e saldo.")
    # (Código da Parte 3 virá aqui)

# 2. TRANSFERÊNCIA
elif item_atual['nome'] == "Transferência":
    st.info("Mover produtos entre locais.")

# 3. COMPRAS
elif item_atual['nome'] == "Compras":
    st.info("Gerar pedidos.")

# 4. PRODUTOS (CADASTRO)
elif item_atual['nome'] == "Produtos":
    df_atual = carregar_dados()
    aba_cafe, aba_pereciveis = st.tabs(["☕ Café", "🍎 Perecíveis"])
    
    def renderizar_aba(categoria_nome):
        # Cadastro Minimalista
        with st.expander(f"➕ Novo Item"):
            with st.form(key=f"form_{categoria_nome}"):
                nome = st.text_input("Nome")
                c1, c2 = st.columns(2)
                forn = c1.text_input("Fornecedor")
                custo = c2.number_input("Custo R$", 0.0, step=0.1)
                minimo = st.number_input("Mínimo", 1)
                if st.form_submit_button("Salvar", use_container_width=True):
                    ok, msg = salvar_novo_produto(nome, categoria_nome, forn, custo, minimo)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        
        # Lista
        df_filtro = df_atual[df_atual['Categoria'] == categoria_nome]
        if not df_filtro.empty:
            st.dataframe(df_filtro[['Produto', 'Saldo', 'Fornecedor']], use_container_width=True, hide_index=True)
            
            c_del1, c_del2 = st.columns([4, 1])
            p_del = c_del1.selectbox("Apagar:", df_filtro['Produto'].unique(), key=f"s_{categoria_nome}", label_visibility="collapsed", index=None, placeholder="Selecione para excluir...")
            if p_del and c_del2.button("🗑️", key=f"b_{categoria_nome}"):
                excluir_produto(p_del); st.rerun()
        else:
            st.caption("Nada aqui ainda.")

    with aba_cafe: renderizar_aba("Café")
    with aba_pereciveis: renderizar_aba("Perecíveis")

# 5. VENDAS
elif item_atual['nome'] == "Vendas":
    st.info("Upload de planilhas.")

# 6. SUGESTÕES
elif item_atual['nome'] == "Sugestões":
    st.info("Inteligência Artificial.")
