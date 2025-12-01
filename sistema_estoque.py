import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Gestão 3.2", layout="wide") # Tela cheia para caber os ícones
ARQUIVO_DADOS = "banco_dados.csv"

# --- ESTADO DA NAVEGAÇÃO ---
if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "Produtos" # Começa no cadastro

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

# --- MENU DE ÍCONES (O NOVO DESIGN) ---
st.markdown("<h1 style='text-align: center; color: #4F8BF9;'>Sistema de Gestão Integrado</h1>", unsafe_allow_html=True)
st.write("") # Espaço

# Cria 6 colunas para os botões
c1, c2, c3, c4, c5, c6 = st.columns(6)

# Cada botão define a página atual ao ser clicado
with c1:
    if st.button("📦\nEstoque", use_container_width=True): st.session_state['pagina_atual'] = "Estoque"
with c2:
    if st.button("🚚\nTransf.", use_container_width=True): st.session_state['pagina_atual'] = "Transferência"
with c3:
    if st.button("🛒\nCompras", use_container_width=True): st.session_state['pagina_atual'] = "Compras"
with c4:
    if st.button("📋\nProdutos", use_container_width=True): st.session_state['pagina_atual'] = "Produtos"
with c5:
    if st.button("📉\nVendas", use_container_width=True): st.session_state['pagina_atual'] = "Vendas"
with c6:
    if st.button("💡\nSugestões", use_container_width=True): st.session_state['pagina_atual'] = "Sugestões"

st.markdown("<hr>", unsafe_allow_html=True) # Linha separadora

# --- CONTEÚDO DAS TELAS (RENDERIZAÇÃO CONDICIONAL) ---
pagina = st.session_state['pagina_atual']

# 1. TELA DE ESTOQUE
if pagina == "Estoque":
    st.subheader("📦 Controle de Estoque")
    st.info("Aqui você dará entrada (compras que chegaram) e baixa (consumo/perda).")
    # (Código da Parte 3 entrará aqui)

# 2. TELA DE TRANSFERÊNCIA
elif pagina == "Transferência":
    st.subheader("🚚 Transferência entre Locais")
    st.info("Mova produtos do Central para os Hospitais.")

# 3. TELA DE COMPRAS
elif pagina == "Compras":
    st.subheader("🛒 Pedidos de Compra")
    st.info("Gera lista do que precisa comprar.")

# 4. TELA DE PRODUTOS (JÁ FUNCIONANDO)
elif pagina == "Produtos":
    st.subheader("📋 Cadastro de Produtos")
    
    df_atual = carregar_dados()
    aba_cafe, aba_pereciveis = st.tabs(["☕ Café & Insumos", "🍎 Perecíveis"])
    
    def renderizar_cadastro(categoria_nome):
        # Formulário de Cadastro
        with st.container(border=True):
            st.markdown(f"**Novo Item: {categoria_nome}**")
            c_nome, c_forn = st.columns(2)
            nome = c_nome.text_input("Nome do Produto", key=f"n_{categoria_nome}")
            forn = c_forn.text_input("Fornecedor", key=f"f_{categoria_nome}")
            
            c_custo, c_min, c_btn = st.columns([1, 1, 1])
            custo = c_custo.number_input("Custo R$", 0.0, step=0.1, key=f"c_{categoria_nome}")
            minimo = c_min.number_input("Mínimo", 1, key=f"m_{categoria_nome}")
            
            st.write("") # Espaço para alinhar botão
            if c_btn.button("Salvar Produto", key=f"b_{categoria_nome}", use_container_width=True):
                if nome:
                    ok, msg = salvar_novo_produto(nome, categoria_nome, forn, custo, minimo)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
                else:
                    st.warning("Digite o nome.")

        # Lista de Produtos
        st.write("")
        df_filtro = df_atual[df_atual['Categoria'] == categoria_nome]
        
        if not df_filtro.empty:
            st.dataframe(
                df_filtro[['Produto', 'Saldo', 'Fornecedor', 'Custo']], 
                use_container_width=True, 
                hide_index=True
            )
            
            # Botão de Excluir no final
            with st.expander("🗑️ Área de Exclusão"):
                p_del = st.selectbox("Produto para apagar:", df_filtro['Produto'].unique(), key=f"del_{categoria_nome}")
                if st.button("Confirmar Exclusão", key=f"btn_del_{categoria_nome}"):
                    excluir_produto(p_del); st.rerun()
        else:
            st.info("Nenhum produto cadastrado.")

    with aba_cafe: renderizar_cadastro("Café")
    with aba_pereciveis: renderizar_cadastro("Perecíveis")

# 5. TELA DE VENDAS
elif pagina == "Vendas":
    st.subheader("📉 Baixa via Planilha")
    st.info("Importe seu Excel de vendas aqui.")

# 6. TELA DE SUGESTÕES
elif pagina == "Sugestões":
    st.subheader("💡 Inteligência")
    st.info("Dicas automáticas de gestão.")
