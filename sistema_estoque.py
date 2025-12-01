import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Separado 30.0", layout="wide", initial_sidebar_state="collapsed")
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

# --- 2. MENU SUPERIOR (7 BOTÕES) ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h2>", unsafe_allow_html=True)
st.markdown("---")

if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Cafe"

# Agora temos 7 colunas
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

def botao(col, txt, ico, nome_t):
    estilo = "primary" if st.session_state['tela_atual'] == nome_t else "secondary"
    if col.button(f"{ico}\n{txt}", key=nome_t, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = nome_t
        st.rerun()

botao(c1, "Estoque", "📦", "Estoque")
botao(c2, "Transferir", "🚚", "Transferencia")
botao(c3, "Compras", "🛒", "Compras")
botao(c4, "Café", "☕", "Cafe")           # Menu Separado
botao(c5, "Perecíveis", "🍎", "Pereciveis") # Menu Separado
botao(c6, "Vendas", "📉", "Vendas")
botao(c7, "Sugestões", "💡", "Sugestoes")

st.markdown("---")

# --- 3. LÓGICA DE CADASTRO (REUTILIZÁVEL) ---
def tela_cadastro_categoria(categoria_nome, titulo_emoji):
    """
    Esta função monta a tela de cadastro automaticamente
    baseada na categoria que a gente passar (Café ou Perecível)
    """
    st.header(f"{titulo_emoji} Gestão de {categoria_nome}")
    
    df_db = carregar_dados()
    
    # --- ÁREA DE UPLOAD ---
    with st.expander(f"📂 Cadastrar/Atualizar {categoria_nome} (Via Planilha)", expanded=True):
        st.info(f"Suba a planilha aqui. Os produtos serão salvos automaticamente como '{categoria_nome}'.")
        arquivo = st.file_uploader("Arquivo", type=["xlsx", "csv"], key=f"up_{categoria_nome}")
        
        if arquivo and st.button("🚀 Processar Cadastro"):
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
                            "Categoria": categoria_nome, # FORÇA A CATEGORIA DO MENU
                            "Fornecedor": str(r[c_forn]) if c_forn else "",
                            "Padrao": str(r[c_padr]) if c_padr else "",
                            "Custo": limpar_numero(r[c_cust]) if c_cust else 0.0,
                            "Min_SA": limpar_numero(r[c_msa]) if c_msa else 0.0,
                            "Min_SI": limpar_numero(r[c_msi]) if c_msi else 0.0
                        }
                        
                        # Atualiza ou Cria
                        mask = (df_db['Produto'] == prod)
                        if mask.any():
                            # Se já existe, atualiza os dados cadastrais (exceto estoque)
                            # E GARANTE que a categoria mude para a atual se estiver errada
                            for k, v in dados.items():
                                df_db.loc[mask, k] = v
                        else:
                            # Cria novo com estoques zerados
                            dados["Estoque_Central"] = 0
                            dados["Estoque_SA"] = 0
                            dados["Estoque_SI"] = 0
                            df_db = pd.concat([df_db, pd.DataFrame([dados])], ignore_index=True)
                        cnt += 1
                        
                    salvar_banco(df_db)
                    st.success(f"{cnt} itens processados em {categoria_nome}!")
                    st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    # --- TABELA DE VISUALIZAÇÃO ---
    st.divider()
    st.markdown(f"**Base de Dados: {categoria_nome}**")
    
    # Filtra só o que é da categoria atual
    df_show = df_db[df_db['Categoria'] == categoria_nome].copy()
    
    if not df_show.empty:
        # Mostra colunas úteis
        cols_view = ["Codigo", "Produto", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI"]
        st.dataframe(df_show[cols_view], use_container_width=True, hide_index=True)
        
        # Excluir
        c_del1, c_del2 = st.columns([4, 1])
        p_del = c_del1.selectbox("Excluir Item:", df_show['Produto'], key=f"del_{categoria_nome}", index=None)
        if p_del and c_del2.button("🗑️ Apagar", key=f"btn_{categoria_nome}"):
            df_db = df_db[df_db['Produto'] != p_del]
            salvar_banco(df_db)
            st.rerun()
    else:
        st.info(f"Nenhum produto cadastrado como {categoria_nome}.")


# --- ROTEAMENTO DAS TELAS ---
tela = st.session_state['tela_atual']

if tela == "Estoque":
    st.title("📦 Estoque"); st.info("Próxima etapa...")

elif tela == "Transferencia":
    st.title("🚚 Transferência"); st.info("Em breve...")

elif tela == "Compras":
    st.title("🛒 Compras"); st.info("Em breve...")

# --- AQUI ESTÁ A MÁGICA: CHAMAMOS A MESMA FUNÇÃO MUDANDO O NOME ---
elif tela == "Cafe":
    tela_cadastro_categoria("Café", "☕")

elif tela == "Pereciveis":
    tela_cadastro_categoria("Perecíveis", "🍎")
# ------------------------------------------------------------------

elif tela == "Vendas":
    st.title("📉 Vendas"); st.info("Em breve...")

elif tela == "Sugestoes":
    st.title("💡 Sugestões"); st.info("Em breve...")
