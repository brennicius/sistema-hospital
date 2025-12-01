import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Gestão 4.2 (Estoque)", layout="wide", initial_sidebar_state="collapsed")
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

# --- 2. MENU SUPERIOR ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h2>", unsafe_allow_html=True)
st.markdown("---")

if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Estoque" # Começa no Estoque agora

c1, c2, c3, c4, c5, c6 = st.columns(6)

def botao(col, txt, ico, nome_t):
    estilo = "primary" if st.session_state['tela_atual'] == nome_t else "secondary"
    if col.button(f"{ico}\n{txt}", key=nome_t, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = nome_t
        st.rerun()

botao(c1, "Estoque", "📦", "Estoque")
botao(c2, "Transferir", "🚚", "Transferencia")
botao(c3, "Compras", "🛒", "Compras")
botao(c4, "Produtos", "📋", "Produtos")
botao(c5, "Vendas", "📉", "Vendas")
botao(c6, "Sugestões", "💡", "Sugestoes")

st.markdown("---")

# --- 3. TELA DE ESTOQUE (A NOVIDADE) ---
if st.session_state['tela_atual'] == "Estoque":
    st.header("📦 Atualização de Estoque (Contagem)")
    
    df_db = carregar_dados()
    
    # Seletor de Local (Para saber onde salvar a quantidade)
    locais = {
        "Depósito Geral (Central)": "Estoque_Central",
        "Hospital Santo Amaro": "Estoque_SA",
        "Hospital Santa Izabel": "Estoque_SI"
    }
    
    col_local, col_vazio = st.columns([1, 2])
    local_selecionado = col_local.selectbox("📍 Onde você fez essa contagem?", list(locais.keys()))
    coluna_destino = locais[local_selecionado]
    
    with st.container(border=True):
        st.info(f"Suba a planilha de contagem do **{local_selecionado}**. O sistema buscará primeiro pelo Código, depois pelo Nome.")
        
        arquivo = st.file_uploader("Arquivo de Contagem", type=["xlsx", "csv"], key="up_estoque")
        
        if arquivo:
            try:
                # 1. Detecção Inteligente de Cabeçalho (igual fizemos antes)
                if arquivo.name.endswith('.csv'): df_temp = pd.read_csv(arquivo, header=None)
                else: df_temp = pd.read_excel(arquivo, header=None)
                
                header_row = 0
                for i, row in df_temp.head(20).iterrows():
                    row_s = row.astype(str).str.lower().tolist()
                    if any("código" in s or "codigo" in s or "produto" in s for s in row_s):
                        header_row = i
                        break
                
                arquivo.seek(0)
                if arquivo.name.endswith('.csv'): df_new = pd.read_csv(arquivo, header=header_row)
                else: df_new = pd.read_excel(arquivo, header=header_row)
                
                # 2. Seleção de Colunas
                cols = df_new.columns.tolist()
                c1, c2, c3 = st.columns(3)
                
                i_cod = next((i for i, c in enumerate(cols) if "cod" in str(c).lower()), 0)
                i_nom = next((i for i, c in enumerate(cols) if "nom" in str(c).lower() or "prod" in str(c).lower()), 0)
                i_qtd = next((i for i, c in enumerate(cols) if "qtd" in str(c).lower() or "saldo" in str(c).lower() or "fisico" in str(c).lower()), 0)
                
                col_codigo = c1.selectbox("Coluna Código", cols, index=i_cod)
                col_nome = c2.selectbox("Coluna Nome", cols, index=i_nom)
                col_qtd = c3.selectbox("Coluna Quantidade", cols, index=i_qtd)
                
                if st.button("🚀 Processar Contagem"):
                    atualizados = 0
                    nao_encontrados = []
                    
                    # Barra de progresso para dar feedback visual
                    bar = st.progress(0)
                    total_rows = len(df_new)
                    
                    for i, r in df_new.iterrows():
                        # Atualiza barra
                        bar.progress((i + 1) / total_rows)
                        
                        # Dados da planilha
                        cod_planilha = str(r[col_codigo]).strip()
                        nome_planilha = str(r[col_nome]).strip()
                        qtd_planilha = limpar_numero(r[col_qtd])
                        
                        match = pd.DataFrame()
                        
                        # --- ESTRATÉGIA 1: BUSCA POR CÓDIGO ---
                        if cod_planilha and cod_planilha != 'nan':
                            # Tenta bater com 'Codigo' ou 'Codigo_Unico' do banco
                            match = df_db[
                                (df_db['Codigo'] == cod_planilha) | 
                                (df_db['Codigo_Unico'] == cod_planilha)
                            ]
                        
                        # --- ESTRATÉGIA 2: BUSCA POR NOME (SE NÃO ACHOU POR CÓDIGO) ---
                        if match.empty and nome_planilha and nome_planilha != 'nan':
                            match = df_db[df_db['Produto'] == nome_planilha]
                            
                        # --- RESULTADO ---
                        if not match.empty:
                            # Pega o primeiro índice encontrado
                            idx = match.index[0]
                            # Atualiza a coluna do local selecionado
                            df_db.at[idx, coluna_destino] = qtd_planilha
                            atualizados += 1
                        else:
                            # Log de erro para você saber o que não bateu
                            identificador = cod_planilha if cod_planilha and cod_planilha != 'nan' else nome_planilha
                            if identificador and identificador != 'nan':
                                nao_encontrados.append(f"{identificador} (Qtd: {qtd_planilha})")
                    
                    bar.empty() # Limpa barra
                    salvar_banco(df_db)
                    
                    # Relatório Final
                    st.success(f"✅ Concluído! {atualizados} produtos atualizados em {local_selecionado}.")
                    
                    if nao_encontrados:
                        with st.expander(f"⚠️ {len(nao_encontrados)} Produtos não encontrados no cadastro (Verifique):"):
                            st.write(nao_encontrados)
                            
            except Exception as e:
                st.error(f"Erro ao processar: {e}")

    # --- VISUALIZAÇÃO DO ESTOQUE ATUAL ---
    st.divider()
    st.markdown(f"### 🔎 Visão Atual do Estoque")
    
    # Filtro rápido
    filtro = st.text_input("Filtrar produto:", placeholder="Digite o nome...")
    
    df_view = df_db.copy()
    if filtro:
        df_view = df_view[df_view['Produto'].str.contains(filtro, case=False, na=False)]
        
    # Mostra tabela focada no estoque
    st.dataframe(
        df_view[['Codigo', 'Produto', 'Padrao', 'Estoque_Central', 'Estoque_SA', 'Estoque_SI']],
        use_container_width=True,
        hide_index=True
    )

# --- OUTRAS TELAS (MANTER IGUAL POR ENQUANTO) ---
elif st.session_state['tela_atual'] == "Produtos":
    # (Código da Parte 2 que já fizemos - MANTIDO RESUMIDO AQUI PRA NÃO FICAR GIGANTE O TEXTO, MAS COPIE O ANTERIOR SE PRECISAR)
    # Vou colar o código completo da tela de Produtos abaixo para garantir que nada se perca
    st.header("📋 Cadastro Geral de Produtos")
    df_db = carregar_dados()
    with st.expander("📂 Importar Cadastro", expanded=True):
        c_upl, c_cat = st.columns([2, 1])
        arquivo = c_upl.file_uploader("Arquivo Excel/CSV", type=["xlsx", "csv"], key="up_prod")
        categoria_escolhida = c_cat.selectbox("Categoria:", ["Café", "Perecíveis", "Geral"])
        if arquivo and c_upl.button("Processar"):
            try:
                if arquivo.name.endswith('.csv'): df_new = pd.read_csv(arquivo)
                else: df_new = pd.read_excel(arquivo)
                cols = df_new.columns
                def find(k): 
                    for c in cols: 
                        if any(x in c.lower() for x in k): return c
                    return None
                c_cod = find(['código', 'codigo'])
                c_nome1 = find(['produto 1', 'nome produto'])
                c_forn = find(['fornecedor'])
                c_padr = find(['padrão', 'padrao'])
                c_cust = find(['custo', 'unitário'])
                c_msa = find(['santo amaro', 'st amaro'])
                c_msi = find(['santa izabel', 'st izabel'])
                
                if not c_nome1: st.error("Coluna Nome não encontrada.")
                else:
                    cnt = 0
                    for i, r in df_new.iterrows():
                        prod = str(r[c_nome1]).strip()
                        if not prod or prod == 'nan': continue
                        dados = {
                            "Codigo": str(r[c_cod]) if c_cod else "",
                            "Produto": prod,
                            "Categoria": categoria_escolhida,
                            "Fornecedor": str(r[c_forn]) if c_forn else "",
                            "Padrao": str(r[c_padr]) if c_padr else "",
                            "Custo": limpar_numero(r[c_cust]) if c_cust else 0.0,
                            "Min_SA": limpar_numero(r[c_msa]) if c_msa else 0.0,
                            "Min_SI": limpar_numero(r[c_msi]) if c_msi else 0.0
                        }
                        mask = (df_db['Produto'] == prod)
                        if mask.any():
                            for k, v in dados.items(): df_db.loc[mask, k] = v
                        else:
                            dados.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                            df_db = pd.concat([df_db, pd.DataFrame([dados])], ignore_index=True)
                        cnt += 1
                    salvar_banco(df_db); st.success(f"{cnt} processados!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
    st.divider()
    aba1, aba2, aba3 = st.tabs(["☕ Café", "🍎 Perecíveis", "📋 Todos"])
    def mostrar_tabela(cat):
        df_show = df_db if cat == "Todos" else df_db[df_db['Categoria'] == cat]
        if not df_show.empty:
            st.dataframe(df_show[["Codigo", "Produto", "Fornecedor", "Padrao", "Custo"]], use_container_width=True, hide_index=True)
            c_del1, c_del2 = st.columns([4, 1])
            p_del = c_del1.selectbox(f"Excluir ({cat}):", df_show['Produto'], key=f"d_{cat}", index=None)
            if p_del and c_del2.button("🗑️", key=f"b_{cat}"):
                salvar_banco(df_db[df_db['Produto'] != p_del]); st.rerun()
        else: st.info("Vazio.")
    with aba1: mostrar_tabela("Café")
    with aba2: mostrar_tabela("Perecíveis")
    with aba3: mostrar_tabela("Todos")

elif st.session_state['tela_atual'] == "Transferencia":
    st.title("🚚 Transferência"); st.info("Em breve...")

elif st.session_state['tela_atual'] == "Compras":
    st.title("🛒 Compras"); st.info("Em breve...")

elif st.session_state['tela_atual'] == "Vendas":
    st.title("📉 Vendas"); st.info("Em breve...")

elif st.session_state['tela_atual'] == "Sugestoes":
    st.title("💡 Sugestões"); st.info("Em breve...")
