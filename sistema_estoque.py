import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Unificado 30.1", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"

# --- 1. BANCO DE DADOS ---
@st.cache_data
def carregar_dados():
    colunas = [
        "Codigo", "Codigo_Unico", "Produto", "Produto_Alt", 
        "Categoria", "Fornecedor", "Padrao", "Custo", 
        "Min_SA", "Min_SI", 
        "Estoque_Central", "Estoque_SA", "Estoque_SI"
    ]
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=colunas)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    try: return pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def limpar_numero(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

# --- 2. MENU SUPERIOR (6 BOTÕES) ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h2>", unsafe_allow_html=True)
st.markdown("---")

if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Produtos"

# 6 Colunas
c1, c2, c3, c4, c5, c6 = st.columns(6)

def botao(col, txt, ico, nome_t):
    estilo = "primary" if st.session_state['tela_atual'] == nome_t else "secondary"
    if col.button(f"{ico}\n{txt}", key=nome_t, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = nome_t
        st.rerun()

botao(c1, "Estoque", "📦", "Estoque")
botao(c2, "Transferir", "🚚", "Transferencia")
botao(c3, "Compras", "🛒", "Compras")
botao(c4, "Produtos", "📋", "Produtos") # VOLTOU A SER UM SÓ
botao(c5, "Vendas", "📉", "Vendas")
botao(c6, "Sugestões", "💡", "Sugestoes")

st.markdown("---")

# --- 3. TELA PRODUTOS (CADASTRO MESTRE) ---
if st.session_state['tela_atual'] == "Produtos":
    st.header("📋 Cadastro Geral de Produtos")
    
    df_db = carregar_dados()
    
    # --- ÁREA DE UPLOAD ---
    with st.expander("📂 Importar Planilha de Cadastro/Atualização", expanded=True):
        st.info("Suba a planilha Mestre aqui. O sistema atualizará nomes, custos e mínimos.")
        
        # Seletor de Categoria para o Upload
        c_upl, c_cat = st.columns([2, 1])
        arquivo = c_upl.file_uploader("Arquivo Excel/CSV", type=["xlsx", "csv"])
        categoria_escolhida = c_cat.selectbox("Definir categoria destes produtos como:", ["Café", "Perecíveis", "Geral"])
        
        if arquivo and c_upl.button("🚀 Processar Cadastro"):
            try:
                if arquivo.name.endswith('.csv'): df_new = pd.read_csv(arquivo)
                else: df_new = pd.read_excel(arquivo)
                
                # Auto-detecção de colunas
                cols = df_new.columns
                def find(k): 
                    for c in cols: 
                        if any(x in c.lower() for x in k): return c
                    return None

                # Mapeamento
                c_cod = find(['código', 'codigo'])
                c_cod_u = find(['único', 'unico'])
                c_nome1 = find(['produto 1', 'nome produto', 'descrição'])
                c_nome2 = find(['produto 2'])
                c_forn = find(['fornecedor'])
                c_padr = find(['padrão', 'padrao'])
                c_cust = find(['custo', 'unitário'])
                c_msa = find(['santo amaro', 'st amaro'])
                c_msi = find(['santa izabel', 'st izabel'])
                
                if not c_nome1:
                    st.error("Erro: Não encontrei a coluna de Nome do Produto.")
                else:
                    cnt = 0
                    for i, r in df_new.iterrows():
                        prod = str(r[c_nome1]).strip()
                        if not prod or prod == 'nan': continue
                        
                        # Dados
                        dados = {
                            "Codigo": str(r[c_cod]) if c_cod else "",
                            "Codigo_Unico": str(r[c_cod_u]) if c_cod_u else "",
                            "Produto": prod,
                            "Produto_Alt": str(r[c_nome2]) if c_nome2 else "",
                            "Categoria": categoria_escolhida, # Usa a categoria do seletor
                            "Fornecedor": str(r[c_forn]) if c_forn else "",
                            "Padrao": str(r[c_padr]) if c_padr else "",
                            "Custo": limpar_numero(r[c_cust]) if c_cust else 0.0,
                            "Min_SA": limpar_numero(r[c_msa]) if c_msa else 0.0,
                            "Min_SI": limpar_numero(r[c_msi]) if c_msi else 0.0
                        }
                        
                        # Atualiza ou Cria
                        mask = (df_db['Produto'] == prod)
                        if mask.any():
                            # Se já existe, atualiza cadastro (mantém estoque)
                            for k, v in dados.items():
                                df_db.loc[mask, k] = v
                        else:
                            # Cria novo
                            dados["Estoque_Central"] = 0
                            dados["Estoque_SA"] = 0
                            dados["Estoque_SI"] = 0
                            df_db = pd.concat([df_db, pd.DataFrame([dados])], ignore_index=True)
                        cnt += 1
                        
                    salvar_banco(df_db)
                    st.success(f"{cnt} itens processados como '{categoria_escolhida}'!")
                    st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    # --- VISUALIZAÇÃO POR ABAS ---
    st.divider()
    aba1, aba2, aba3 = st.tabs(["☕ Café", "🍎 Perecíveis", "📋 Todos"])
    
    def mostrar_tabela(cat_filtro):
        if cat_filtro == "Todos":
            df_show = df_db
        else:
            df_show = df_db[df_db['Categoria'] == cat_filtro].copy()
            
        if not df_show.empty:
            st.dataframe(df_show[["Codigo", "Produto", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI"]], use_container_width=True, hide_index=True)
            
            c_del1, c_del2 = st.columns([4, 1])
            p_del = c_del1.selectbox(f"Excluir de {cat_filtro}:", df_show['Produto'], key=f"d_{cat_filtro}", index=None)
            if p_del and c_del2.button("🗑️", key=f"b_{cat_filtro}"):
                df_db_new = df_db[df_db['Produto'] != p_del]
                salvar_banco(df_db_new)
                st.rerun()
        else:
            st.info("Sem itens.")

    with aba1: mostrar_tabela("Café")
    with aba2: mostrar_tabela("Perecíveis")
    with aba3: mostrar_tabela("Todos")

# --- ROTEAMENTO DAS OUTRAS TELAS ---
elif st.session_state['tela_atual'] == "Estoque":
    st.title("📦 Estoque"); st.info("Próxima etapa...")

elif st.session_state['tela_atual'] == "Transferencia":
    st.title("🚚 Transferência"); st.info("Em breve...")

elif st.session_state['tela_atual'] == "Compras":
    st.title("🛒 Compras"); st.info("Em breve...")

elif st.session_state['tela_atual'] == "Vendas":
    st.title("📉 Vendas"); st.info("Em breve...")

elif st.session_state['tela_atual'] == "Sugestoes":
    st.title("💡 Sugestões"); st.info("Em breve...")
