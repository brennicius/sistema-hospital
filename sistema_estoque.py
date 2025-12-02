import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Modo Segurança", layout="wide")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO ---
def init_state():
    keys = ['tela_atual', 'carga']
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = "Estoque" if k == 'tela_atual' else []

init_state()

# --- FUNÇÕES DE DADOS (CSV LOCAL) ---
def limpar_numero(v):
    if pd.isna(v): return 0.0
    s = str(v).lower().replace('r$','').replace('kg','').replace('un','').replace(' ','').replace(',','.')
    try: return float(s)
    except: return 0.0

def carregar_dados():
    cols = ["Codigo", "Produto", "Categoria", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI", "Estoque_Central", "Estoque_SA", "Estoque_SI"]
    if not os.path.exists(ARQUIVO_DADOS): return pd.DataFrame(columns=cols)
    try: return pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=cols)

def salvar_dados(df):
    df.to_csv(ARQUIVO_DADOS, index=False)

# --- INTERFACE ---
st.title("✅ Sistema Online (Modo Segurança)")
st.info("Se você está vendo isso, o servidor destravou! Agora podemos adicionar as funções extras.")

c1, c2, c3, c4 = st.columns(4)
if c1.button("📦 Estoque"): st.session_state['tela_atual'] = "Estoque"; st.rerun()
if c2.button("📋 Produtos"): st.session_state['tela_atual'] = "Produtos"; st.rerun()
if c3.button("🛒 Compras"): st.session_state['tela_atual'] = "Compras"; st.rerun()
if c4.button("🚚 Transf."): st.session_state['tela_atual'] = "Transf"; st.rerun()

df = carregar_dados()
tela = st.session_state['tela_atual']

if tela == "Estoque":
    st.header("Estoque")
    st.dataframe(df)
    with st.expander("Upload"):
        f = st.file_uploader("CSV/Excel")
        if f: st.success("Função de upload pronta para ativar.")

elif tela == "Produtos":
    st.header("Produtos")
    st.dataframe(df)

else:
    st.warning("As outras telas serão reativadas assim que confirmarmos que o servidor está limpo.")
