import streamlit as st
import pandas as pd
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Gestão 4.1",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. BANCO DE DADOS (ATUALIZADO PARA SUA PLANILHA) ---
ARQUIVO_DADOS = "banco_dados.csv"

def carregar_dados():
    colunas = [
        "Codigo",           # Coluna A
        "Codigo_Unico",     # Coluna B
        "Produto",          # Nome Produto 1
        "Produto_Alt",      # Nome Produto 2 (Para busca)
        "Categoria",        # Café ou Perecíveis
        "Fornecedor",       # Fornecedor
        "Padrao",           # Unidade/Caixa/Kg
        "Custo",            # Custo Unitário
        "Min_SA",           # Mínimo Santo Amaro
        "Min_SI",           # Mínimo Santa Izabel
        "Estoque_Central",  # Quantidade Atual
        "Estoque_SA",       # Quantidade Atual
        "Estoque_SI"        # Quantidade Atual
    ]
    
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=colunas)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    
    try:
        return pd.read_csv(ARQUIVO_DADOS)
    except:
        return pd.DataFrame(columns=colunas)

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)

def limpar_numero(valor):
    """Converte texto de dinheiro/quantidade para numero"""
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

# --- 3. MENU SUPERIOR ---
st.markdown("<h1 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h1>", unsafe_allow_html=True)
st.markdown("---")

col1, col2, col3, col4, col5, col6 = st.columns(6)

if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Produtos"

def botao_menu(col, texto, icone, tela):
    estilo = "primary" if st.session_state['tela_atual'] == tela else "secondary"
    if col.button(f"{icone}\n{texto}", key=tela, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = tela
        st.rerun()

botao_menu(col1, "Estoque", "📦", "Estoque")
botao_menu(col2, "Transferir", "🚚", "Transferencia")
botao_menu(col3, "Compras", "🛒", "Compras")
botao_menu(col4, "Produtos", "📋", "Produtos")
botao_menu(col5, "Vendas", "📉", "Vendas")
botao_menu(col6, "Sugestões", "💡", "Sugestoes")

st.markdown("---")

# --- 4. TELA DE PRODUTOS ---
if st.session_state['tela_atual'] == "Produtos":
    st.header("📋 Cadastro Mestre de Produtos")
    
    df_db = carregar_dados()
    
    # --- ÁREA DE IMPORTAÇÃO (IMPORTANTE) ---
    with st.expander("📂 Importar Planilha de Fornecedor (Base de Dados)", expanded=True):
        st.info("Use sua planilha padrão para cadastrar ou atualizar os produtos em massa.")
        
        c_upload, c_cat = st.columns([2, 1])
        arquivo = c_upload.file_uploader("Arraste sua planilha aqui", type=["xlsx", "csv"])
        categoria_upload = c_cat.selectbox("Estes produtos são:", ["Perecíveis", "Café/Insumos"])
        
        if arquivo and c_upload.button("🚀 Processar Cadastro"):
            try:
                # Lê o arquivo
                if arquivo.name.endswith('.csv'): df_new = pd.read_csv(arquivo)
                else: df_new = pd.read_excel(arquivo)
                
                # Mapeamento das suas colunas
                # Procura colunas parecidas com os nomes que você passou
                cols = df_new.columns
                
                # Função para achar coluna por palavra chave
                def find_col(keywords):
                    for c in cols:
                        if any(k.lower() in c.lower() for k in keywords): return c
                    return None

                col_cod = find_col(['código', 'codigo'])
                col_cod_u = find_col(['único', 'unico'])
                col_nome1 = find_col(['produto 1', 'nome produto'])
                col_nome2 = find_col(['produto 2'])
                col_forn = find_col(['fornecedor'])
                col_padrao = find_col(['padrão', 'padrao'])
                col_custo = find_col(['custo', 'unitário', 'unitario'])
                col_min_si = find_col(['santa izabel', 'izabel'])
                col_min_sa = find_col(['santo amaro', 'amaro'])
                
                if not col_nome1:
                    st.error("Não encontrei a coluna 'Nome Produto 1'. Verifique o arquivo.")
                else:
                    count = 0
                    for index, row in df_new.iterrows():
                        nome = str(row[col_nome1]).strip()
                        if not nome or nome == 'nan': continue
                        
                        # Prepara dados
                        dados_novos = {
                            "Codigo": str(row[col_cod]) if col_cod else "",
                            "Codigo_Unico": str(row[col_cod_u]) if col_cod_u else "",
                            "Produto": nome,
                            "Produto_Alt": str(row[col_nome2]) if col_nome2 else "",
                            "Categoria": categoria_upload,
                            "Fornecedor": str(row[col_forn]) if col_forn else "",
                            "Padrao": str(row[col_padrao]) if col_padrao else "",
                            "Custo": limpar_numero(row[col_custo]) if col_custo else 0.0,
                            "Min_SA": limpar_numero(row[col_min_sa]) if col_min_sa else 0.0,
                            "Min_SI": limpar_numero(row[col_min_si]) if col_min_si else 0.0,
                        }
                        
                        # Atualiza ou Cria
                        mask = df_db['Produto'] == nome
                        if mask.any():
                            # Atualiza campos (sem zerar estoque)
                            for k, v in dados_novos.items():
                                df_db.loc[mask, k] = v
                        else:
                            # Cria novo (inicia estoque zerado)
                            dados_novos["Estoque_Central"] = 0
                            dados_novos["Estoque_SA"] = 0
                            dados_novos["Estoque_SI"] = 0
                            df_db = pd.concat([df_db, pd.DataFrame([dados_novos])], ignore_index=True)
                        count += 1
                    
                    salvar_banco(df_db)
                    st.success(f"Sucesso! {count} produtos processados/atualizados.")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erro ao processar: {e}")

    # --- VISUALIZAÇÃO ---
    st.divider()
    aba1, aba2 = st.tabs(["☕ Café/Insumos", "🍎 Perecíveis"])
    
    def mostrar_tabela(categoria):
        df_show = df_db[df_db['Categoria'] == categoria]
        if df_show.empty:
            st.info(f"Nenhum produto cadastrado em {categoria}.")
        else:
            # Mostra colunas relevantes
            cols_view = ["Codigo", "Produto", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI"]
            st.dataframe(df_show[cols_view], use_container_width=True, hide_index=True)
            
            # Botão de excluir
            c_del1, c_del2 = st.columns([4, 1])
            p_del = c_del1.selectbox(f"Excluir de {categoria}:", df_show['Produto'], key=f"sel_{categoria}", index=None)
            if p_del and c_del2.button("Apagar", key=f"btn_{categoria}"):
                df_db_new = df_db[df_db['Produto'] != p_del]
                salvar_banco(df_db_new)
                st.rerun()

    with aba1: mostrar_tabela("Café/Insumos")
    with aba2: mostrar_tabela("Perecíveis")

# --- OUTRAS TELAS (Vazias por enquanto) ---
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
