import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
ARQUIVO_DADOS = 'estoque_completo.csv'
ARQUIVO_LOG = 'historico_log.csv'
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

st.set_page_config(page_title="Sistema Master 29.0", layout="wide")

# --- INICIALIZAÇÃO ---
def init_state():
    keys = ['df_distribuicao_temp', 'df_compras_temp', 'romaneio_final', 'romaneio_pdf_cache', 
            'distribuicao_concluida', 'pedido_compra_final', 'selecao_exclusao']
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = None if 'df' in k or 'romaneio' in k or 'pedido' in k else []
            if k == 'distribuicao_concluida': st.session_state[k] = False

init_state()

# --- FUNÇÕES DE LIMPEZA ---
def limpar_numero(valor):
    if pd.isna(valor): return 0
    if isinstance(valor, (int, float)): return valor
    v = str(valor).lower().replace('r$', '').replace('kg', '').replace('un', '').replace(' ', '')
    if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
    else: v = v.replace(',', '.')
    try: return float(v)
    except: return 0

# --- DADOS ---
@st.cache_data
def carregar_dados_cache():
    # Novas colunas baseadas na sua planilha Mestre
    colunas = [
        "Loja", "Codigo", "Codigo_Unico", "Produto", "Produto_Alt", 
        "Fornecedor", "Padrao", "Custo_Unit", 
        "Min_SA", "Min_SI", "Estoque_Atual", "Ultima_Atualizacao"
    ]
    
    if not os.path.exists(ARQUIVO_DADOS): return pd.DataFrame(columns=colunas)
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)
    
    # Garante tipos numéricos
    for c in ["Estoque_Atual", "Custo_Unit", "Min_SA", "Min_SI"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        else: df[c] = 0
            
    # Garante textos
    for c in ["Codigo", "Codigo_Unico", "Produto", "Fornecedor", "Padrao"]:
        if c not in df.columns: df[c] = ""
        df[c] = df[c].astype(str).replace('nan', '')

    # Remove duplicatas exatas de logica
    if not df.empty:
        df = df.groupby(['Loja', 'Produto'], as_index=False).first() # Prioriza cadastro único por loja
        
    return df

def salvar_dados(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados_cache.clear()

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): df = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
    else: df = pd.read_csv(ARQUIVO_LOG)
    pd.concat([df, pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF ---
def criar_pdf_generico(dataframe, titulo_doc, colunas_largura=None):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=titulo_doc, ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(5)
        cols = dataframe.columns.tolist()
        if not colunas_largura:
            l = 190 // len(cols)
            larguras = [l] * len(cols)
            if "Produto" in cols: larguras[cols.index("Produto")] = 70
        else: larguras = colunas_largura
        pdf.set_font("Arial", 'B', 8)
        for i, col in enumerate(cols): 
            txt = str(col).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(larguras[i], 10, txt[:20], 1, 0, 'C')
        pdf.ln()
        pdf.set_font("Arial", size=8)
        for index, row in dataframe.iterrows():
            for i, col in enumerate(cols):
                txt = str(row[col]).encode('latin-1', 'replace').decode('latin-1')
                align = 'L' if i==0 else 'C'
                pdf.cell(larguras[i], 10, txt[:40], 1, 0, align)
            pdf.ln()
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e: return str(e).encode('utf-8')

# --- MÉTODOS AUXILIARES ---
def resetar_processos():
    for k in ['df_distribuicao_temp', 'romaneio_final', 'df_compras_temp', 'pedido_compra_final', 'romaneio_pdf_cache']:
        st.session_state[k] = None
    st.session_state['distribuicao_concluida'] = False

def limpar_selecao(): st.session_state['selecao_exclusao'] = []
def selecionar_tudo_loja(): 
    if 'df_loja_atual' in st.session_state: st.session_state['selecao_exclusao'] = st.session_state['df_loja_atual']['Produto'].tolist()

def calcular_cmv_mensal():
    if not os.path.exists(ARQUIVO_LOG): return pd.DataFrame()
    df_l = pd.read_csv(ARQUIVO_LOG)
    df_e = carregar_dados_cache()
    df_c = df_l[df_l['Tipo'].isin(['Baixa', 'Venda'])].copy()
    if df_c.empty: return pd.DataFrame()
    mapa = df_e.groupby('Produto')['Custo_Unit'].max()
    df_c['Custo'] = df_c['Produto'].map(mapa).fillna(0)
    df_c['Total'] = df_c['Quantidade'] * df_c['Custo']
    def loja(x):
        x=str(x).lower()
        if "amaro" in x: return "Sto Amaro"
        if "izabel" in x: return "Sta Izabel"
        if "central" in x: return "Central"
        return "Outros"
    df_c['Loja'] = df_c['Detalhe'].apply(loja)
    return df_c.groupby('Loja')['Total'].sum().reset_index()

def renderizar_baixa_por_arquivo(df_geral, loja_selecionada):
    st.markdown("---")
    with st.expander("📉 Baixar Vendas (Inteligente)", expanded=True):
        f = st.file_uploader("Relatório Vendas", type=['csv', 'xlsx'], key="up_ven")
        if f:
            try:
                df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                st.info("O sistema tentará identificar o produto pelo Código ou Nome.")
                
                # Seleção de Colunas Chave
                cols = df.columns.tolist()
                c1, c2, c3 = st.columns(3)
                
                # Tentativa de auto-seleção
                i_cod = next((i for i, c in enumerate(cols) if "cod" in c.lower() or "cód" in c.lower()), 0)
                i_nom = next((i for i, c in enumerate(cols) if "nom" in c.lower() or "prod" in c.lower()), 0)
                i_qtd = next((i for i, c in enumerate(cols) if "qtd" in c.lower()), 0)
                
                col_cod = c1.selectbox("Coluna Código (Opcional)", ["Ignorar"] + cols, index=i_cod+1)
                col_nom = c2.selectbox("Coluna Nome", cols, index=i_nom)
                col_qtd = c3.selectbox("Coluna Qtd", cols, index=i_qtd)
                
                if st.button("🚀 Processar"):
                    suc = 0; err = []
                    # Prepara banco de dados da loja para busca rápida
                    db_loja = df_geral[df_geral['Loja'] == loja_selecionada].copy()
                    
                    for i, r in df.iterrows():
                        qtd = limpar_numero(r[col_qtd])
                        if qtd <= 0: continue
                        
                        match = pd.DataFrame()
                        
                        # 1. Tenta pelo Código (Se selecionado)
                        if col_cod != "Ignorar":
                            cod_busca = str(r[col_cod]).strip()
                            # Busca em Codigo ou Codigo_Unico
                            match = db_loja[
                                (db_loja['Codigo'] == cod_busca) | 
                                (db_loja['Codigo_Unico'] == cod_busca)
                            ]
                        
                        # 2. Se não achou, tenta pelo Nome
                        if match.empty:
                            nom_busca = str(r[col_nom]).strip()
                            match = db_loja[db_loja['Produto'] == nom_busca]
                            
                        # Se achou
                        if not match.empty:
                            idx = match.index[0]
                            # Abate do Geral
                            cur = df_geral.loc[idx, 'Estoque_Atual']
                            df_geral.loc[idx, 'Estoque_Atual'] = max(0, cur - qtd)
                            suc += 1
                        else:
                            err.append(f"{r[col_nom]}")

                    if suc > 0:
                        salvar_dados(df_geral); registrar_log("Lote", suc, "Venda", loja_selecionada)
                        st.success(f"✅ Baixados: {suc}")
                        if err: 
                            with st.expander(f"⚠️ {len(err)} Não encontrados (Verifique cadastro):"):
                                st.write(err)
                        st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

# --- INTERFACE ---
st.title("🚀 Sistema Master 29.0")
df_geral = carregar_dados_cache()

with st.sidebar:
    st.header("Menu")
    modo = st.radio("Ir para:", UNIDADES)
    st.divider()
    
    # --- UPLOAD DA PLANILHA MESTRE (CADASTRO) ---
    with st.expander("📂 ATUALIZAR CADASTRO (Mestre)"):
        st.info("Use a 'Planilha de Fornecedor' para atualizar dados cadastrais.")
        f = st.file_uploader("Planilha Base", type=['xlsx', 'csv'], key="up_mestre")
        if f and st.button("Processar Cadastro"):
            try:
                df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                
                # Mapeamento Manual (Hardcoded para a planilha do usuário)
                # Col A: Codigo, B: Cod Unico, C: Nome, Fornecedor, Padrão, Custo Unit., Minimos
                
                # Vamos criar um dicionário de produtos baseados nesta planilha
                # Para cada produto na planilha mestre, atualizamos ou criamos nas 3 lojas
                
                cnt_atualizados = 0
                
                # Carrega estado atual
                df_novo_estado = df_geral.copy()
                
                # Lista de lojas para garantir existência
                lojas_sistema = ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"]
                
                for i, row in df.iterrows():
                    # Mapeia colunas da planilha do usuário (ajustar indices se mudar)
                    # Assumindo ordem: A(0), B(1), C(2), ... Fornecedor, Padrão, Custo, Min SA, Min SI
                    
                    # Tenta pegar pelo nome da coluna se existir, senão pelo índice
                    try: cod = str(row['Código']).strip()
                    except: cod = ""
                    
                    try: cod_u = str(row['Código Único']).strip()
                    except: cod_u = ""
                    
                    # Nome: Tenta 'Nome do Produto'
                    try: prod = str(row['Nome do Produto']).strip()
                    except: prod = "Produto sem nome"
                    
                    if prod == "nan" or prod == "": continue
                    
                    # Dados extras
                    forn = str(row.get('Fornecedor', 'Geral')).strip()
                    padr = str(row.get('Padrão', '')).strip()
                    custo = limpar_numero(row.get('Custo Unit.', 0))
                    min_sa = limpar_numero(row.get('MINIMO SANTO AMARO', 0))
                    min_si = limpar_numero(row.get('MINIMO SANTA IZABEL', 0))
                    
                    # Para cada loja do sistema, atualiza/cria o registro deste produto
                    for loja in lojas_sistema:
                        # Busca se já existe
                        mask = (df_novo_estado['Loja'] == loja) & (df_novo_estado['Produto'] == prod)
                        
                        if mask.any():
                            # Atualiza dados cadastrais (Mantém estoque)
                            df_novo_estado.loc[mask, 'Codigo'] = cod
                            df_novo_estado.loc[mask, 'Codigo_Unico'] = cod_u
                            df_novo_estado.loc[mask, 'Fornecedor'] = forn
                            df_novo_estado.loc[mask, 'Padrao'] = padr
                            df_novo_estado.loc[mask, 'Custo_Unit'] = custo
                            df_novo_estado.loc[mask, 'Min_SA'] = min_sa
                            df_novo_estado.loc[mask, 'Min_SI'] = min_si
                        else:
                            # Cria novo
                            novo_item = {
                                "Loja": loja, "Produto": prod, "Estoque_Atual": 0,
                                "Codigo": cod, "Codigo_Unico": cod_u,
                                "Fornecedor": forn, "Padrao": padr, "Custo_Unit": custo,
                                "Min_SA": min_sa, "Min_SI": min_si,
                                "Ultima_Atualizacao": datetime.now().strftime("%d/%m %H:%M")
                            }
                            df_novo_estado = pd.concat([df_novo_estado, pd.DataFrame([novo_item])], ignore_index=True)
                            
                    cnt_atualizados += 1
                
                salvar_dados(df_novo_estado)
                resetar_processos()
                st.success(f"Cadastro Mestre Atualizado! {cnt_atualizados} produtos processados.")
                st.rerun()
                
            except Exception as e: st.error(f"Erro ao processar: {e}")

    # UPLOAD DE CONTAGEM (QUANTIDADE APENAS)
    with st.expander("📦 Upload Contagem (Só Estoque)"):
        f = st.file_uploader("Planilha Contagem", type=['csv', 'xlsx'], key="up_cont")
        if f and st.button("Atualizar Estoque"):
            try:
                df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cols = df.columns.tolist()
                c1, c2 = st.columns(2)
                # Seleção manual para evitar erro
                in_n = next((i for i, c in enumerate(cols) if "nome" in c.lower()), 0)
                in_q = next((i for i, c in enumerate(cols) if "qtd" in c.lower() or "saldo" in c.lower()), 0)
                cn = c1.selectbox("Col Produto", cols, index=in_n)
                cq = c2.selectbox("Col Qtd", cols, index=in_q)
                
                suc = 0
                for i, r in df.iterrows():
                    p = str(r[cn]).strip()
                    q = limpar_numero(r[cq])
                    # Busca e atualiza
                    m = (df_geral['Loja'] == modo) & (df_geral['Produto'] == p)
                    if m.any():
                        df_geral.loc[m, 'Estoque_Atual'] = q
                        suc += 1
                
                if suc > 0:
                    salvar_dados(df_geral); st.success(f"{suc} estoques atualizados!"); st.rerun()
                else: st.warning("Nenhum produto encontrado.")
            except: st.error("Erro")

    with st.expander("🗑️ Lixeira"):
        df_l = df_geral[df_geral['Loja']==modo]
        st.session_state['df_loja_atual'] = df_l
        c1, c2 = st.columns(2)
        c1.button("Tudo", on_click=selecionar_tudo_loja)
        c2.button("Limpar", on_click=limpar_selecao)
        it = st.multiselect("Itens:", df_l['Produto'].unique(), key='selecao_exclusao')
        if st.button("Excluir"):
            mask = ~((df_geral['Loja']==modo) & (df_geral['Produto'].isin(it)))
            salvar_dados(df_geral[mask]); resetar_processos(); st.success("Ok"); st.rerun()

# --- PÁGINAS ---
if modo == "📊 Dashboard":
    st.subheader("Visão Geral")
    df_c = df_geral.copy()
    df_c['Valor'] = df_c['Estoque_Atual'] * df_c['Custo_Unit']
    k1, k2, k3 = st.columns(3)
    k1.metric("Valor Total", f"R$ {df_c['Valor'].sum():,.2f}")
    k2.metric("Volume", f"{df_c['Estoque_Atual'].sum():,.0f}")
    k3.metric("Zerados", len(df_c[df_c['Estoque_Atual']<=0]))
    st.divider()
    
    st.markdown("### 🔥 Consumo (CMV)")
    cmv = calcular_cmv_mensal()
    if not cmv.empty: st.bar_chart(cmv.set_index('Loja'))
    else: st.info("Sem dados")

elif modo == "📜 Histórico":
    st.subheader("Log")
    if os.path.exists(ARQUIVO_LOG): st.dataframe(pd.read_csv(ARQUIVO_LOG).sort_values('Data', ascending=False), use_container_width=True)
    else: st.info("Vazio")

elif modo == "🛒 Compras":
    st.subheader("Compras (Baseado no Mínimo)")
    
    # Botão de Sugestão Inteligente (Usa o Mínimo cadastrado)
    if st.button("🪄 Gerar Sugestão (Estoque < Mínimo)"):
        # Lógica: Varre hospitais, vê o que tá abaixo do mínimo e soma a necessidade
        sugestoes = {} # {Produto: Qtd}
        
        # 1. Analisa Santo Amaro
        df_sa = df_geral[df_geral['Loja'] == "Hosp. Santo Amaro"]
        for i, r in df_sa.iterrows():
            if r['Estoque_Atual'] < r['Min_SA']:
                qtd = r['Min_SA'] - r['Estoque_Atual']
                sugestoes[r['Produto']] = sugestoes.get(r['Produto'], 0) + qtd
                
        # 2. Analisa Santa Izabel
        df_si = df_geral[df_geral['Loja'] == "Hosp. Santa Izabel"]
        for i, r in df_si.iterrows():
            if r['Estoque_Atual'] < r['Min_SI']:
                qtd = r['Min_SI'] - r['Estoque_Atual']
                sugestoes[r['Produto']] = sugestoes.get(r['Produto'], 0) + qtd
                
        # 3. Abate do que tem no Central
        df_cen = df_geral[df_geral['Loja'] == "Estoque Central"].set_index('Produto')
        
        lista_final = []
        for prod, qtd_nec in sugestoes.items():
            # Verifica se tem no central
            tem_central = df_cen.loc[prod, 'Estoque_Atual'] if prod in df_cen.index else 0
            
            # Só compra o que o Central NÃO consegue cobrir
            compra_real = max(0, qtd_nec - tem_central)
            
            if compra_real > 0:
                # Pega dados do cadastro
                forn = df_cen.loc[prod, 'Fornecedor'] if prod in df_cen.index else "Geral"
                cust = df_cen.loc[prod, 'Custo_Unit'] if prod in df_cen.index else 0
                lista_final.append({'Produto': prod, 'Fornecedor': forn, 'Custo_Unit': cust, 'Qtd': compra_real})
        
        if lista_final:
            st.session_state['df_compras_temp'] = pd.DataFrame(lista_final).sort_values('Fornecedor')
            st.success("Sugestão baseada nos Mínimos Gerada!")
        else:
            st.info("Estoques acima do mínimo ou Central cobre tudo.")

    if st.session_state['df_compras_temp'] is None:
        st.info("Clique no botão acima ou comece manual.")
        base = df_geral[df_geral['Loja']=="Estoque Central"][['Produto','Fornecedor','Custo_Unit']].copy()
        base = base.drop_duplicates('Produto').sort_values('Produto')
        base['Qtd'] = 0 
        st.session_state['df_compras_temp'] = base
    
    view = st.session_state['df_compras_temp']
    f_list = ["Todos"] + sorted(view['Fornecedor'].unique().tolist())
    sel = st.selectbox("Fornecedor", f_list)
    edit = view[view['Fornecedor']==sel].copy() if sel!="Todos" else view.copy()
    edit['Total'] = edit['Qtd'] * edit['Custo_Unit']
    
    ed = st.data_editor(edit, column_config={"Qtd": st.column_config.NumberColumn(min_value=0), "Custo_Unit": st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    if not ed.equals(edit):
        view.set_index('Produto', inplace=True); ed.set_index('Produto', inplace=True)
        view.update(ed); view.reset_index(inplace=True)
        st.session_state['df_compras_temp'] = view; st.rerun()
    
    total_ped = ed['Total'].sum()
    st.metric("Total", f"R$ {total_ped:,.2f}")
    
    if st.button("Baixar Pedido PDF"):
        i = st.session_state['df_compras_temp'].copy(); i['Total'] = i['Qtd'] * i['Custo_Unit']; i = i[i['Qtd']>0]
        if not i.empty:
            pdf_bytes = criar_pdf_generico(i[['Produto','Fornecedor','Qtd','Total']], "PEDIDO DE COMPRA", [90,50,20,30])
            st.download_button("Clique para Baixar PDF", pdf_bytes, "Pedido.pdf", "application/pdf")
            registrar_log("Vários", len(i), "Compra", f"R$ {total_ped:.2f}")
        else: st.warning("Vazio")

elif modo == "Estoque Central":
    if st.session_state['distribuicao_concluida']:
        st.success("Sucesso!")
        if st.session_state.get('romaneio_pdf_cache'): st.download_button("Baixar Romaneio", st.session_state['romaneio_pdf_cache'], "Rom.pdf", "application/pdf")
        if st.session_state['romaneio_final'] is not None: st.dataframe(st.session_state['romaneio_final'], use_container_width=True)
        if st.button("Voltar"): resetar_processos(); st.rerun()
    else:
        st.subheader("Distribuição")
        search = st.text_input("Buscar", placeholder="Nome ou Código...")
        
        # Inicializa se vazio
        if st.session_state['df_distribuicao_temp'] is None:
            df_b = df_geral[df_geral['Loja']==modo][['Produto','Estoque_Atual', 'Padrao']].copy()
            df_b['Env SA'] = 0; df_b['Env SI'] = 0
            
            # Traz dados dos hospitais
            df_sa = df_geral[df_geral['Loja']=="Hosp. Santo Amaro"].set_index('Produto')
            df_si = df_geral[df_geral['Loja']=="Hosp. Santa Izabel"].set_index('Produto')
            
            # Mapeia Tem e Minimo (Meta)
            df_b['Tem SA'] = df_b['Produto'].map(df_sa['Estoque_Atual']).fillna(0)
            df_b['Meta SA'] = df_b['Produto'].map(df_sa['Min_SA']).fillna(0)
            
            df_b['Tem SI'] = df_b['Produto'].map(df_si['Estoque_Atual']).fillna(0)
            df_b['Meta SI'] = df_b['Produto'].map(df_si['Min_SI']).fillna(0)
            
            st.session_state['df_distribuicao_temp'] = df_b
            
        df_w = st.session_state['df_distribuicao_temp']
        
        # Filtro de Busca (Nome ou Código)
        if search:
            mask_busca = (
                df_w['Produto'].str.contains(search, case=False, na=False) 
                # Se tivermos as colunas de código no futuro aqui, adicionamos
            )
            df_view = df_w[mask_busca].copy()
        else:
            # Prioriza mostrar quem está abaixo do mínimo
            df_view = df_w.sort_values('Estoque_Atual', ascending=False).head(50).copy()
        
        df_view['Saldo'] = df_view['Estoque_Atual'] - df_view['Env SA'] - df_view['Env SI']
        
        # Colunas visuais
        cols = ['Produto', 'Padrao', 'Estoque_Atual', 'Saldo', 'Tem SA', 'Meta SA', 'Env SA', 'Tem SI', 'Meta SI', 'Env SI']
        
        ed = st.data_editor(
            df_view[cols], 
            column_config={
                "Estoque_Atual": st.column_config.NumberColumn("Central", disabled=True),
                "Padrao": st.column_config.TextColumn("Emb.", disabled=True, width="small"),
                "Saldo": st.column_config.NumberColumn("Restante", disabled=True),
                "Tem SA": st.column_config.NumberColumn("🏠 Tem SA", disabled=True, format="%.0f"),
                "Meta SA": st.column_config.NumberColumn("🎯 Min SA", disabled=True, format="%.0f"), 
                "Env SA": st.column_config.NumberColumn("➡️ Enviar SA", min_value=0),
                "Tem SI": st.column_config.NumberColumn("🏠 Tem SI", disabled=True, format="%.0f"),
                "Meta SI": st.column_config.NumberColumn("🎯 Min SI", disabled=True, format="%.0f"),
                "Env SI": st.column_config.NumberColumn("➡️ Enviar SI", min_value=0)
            }, 
            use_container_width=True, height=500
        )
        
        if not ed.equals(df_view[cols]):
            ed.set_index('Produto', inplace=True); df_w.set_index('Produto', inplace=True)
            df_w.update(ed[['Env SA', 'Env SI']]); df_w.reset_index(inplace=True)
            st.session_state['df_distribuicao_temp'] = df_w; st.rerun()
            
        if st.button("Efetivar"):
            fin = st.session_state['df_distribuicao_temp']
            rom = []
            env = fin[(fin['Env SA']>0)|(fin['Env SI']>0)]
            if env.empty: st.warning("Nada")
            else:
                for i, r in env.iterrows():
                    sa, si, p = r['Env SA'], r['Env SI'], r['Produto']
                    idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                    if not idx.empty:
                        df_geral.loc[idx, 'Estoque_Atual'] -= (sa+si)
                        for l, q, meta_col in [("Hosp. Santo Amaro", sa, "Meta SA"), ("Hosp. Santa Izabel", si, "Meta SI")]:
                            if q>0:
                                idl = (df_geral['Loja']==l)&(df_geral['Produto']==p)
                                if idl.any(): df_geral.loc[idl, 'Estoque_Atual'] += q
                                else:
                                    n = df_geral.loc[idx].iloc[0].copy(); n['Loja']=l; n['Estoque_Atual']=q
                                    # Leva o Minimo/Meta junto se for novo
                                    if l == "Hosp. Santo Amaro": n['Min_SA'] = r.get('Meta SA', 0)
                                    if l == "Hosp. Santa Izabel": n['Min_SI'] = r.get('Meta SI', 0)
                                    df_geral = pd.concat([df_geral, pd.DataFrame([n])], ignore_index=True)
                        rom.append({"Produto":p, "Padrao": r['Padrao'], "Env SA":sa, "Env SI":si})
                        registrar_log(p, sa+si, "Transferência", f"SA:{sa} SI:{si}")
                salvar_dados(df_geral)
                pdf = criar_pdf_generico(pd.DataFrame(rom), "ROMANEIO")
                st.session_state['romaneio_pdf_cache'] = pdf
                st.session_state['romaneio_final'] = pd.DataFrame(rom)
                st.session_state['distribuicao_concluida'] = True
                st.session_state['df_distribuicao_temp'] = None
                st.rerun()

else:
    st.subheader(f"Gestão: {modo}")
    df_l = df_geral[df_geral['Loja'] == modo].copy()
    if not df_l.empty:
        renderizar_baixa_por_arquivo(df_geral, modo)
        
        # Define qual mínimo mostrar na tabela da loja
        col_min = 'Min_SA' if "Amaro" in modo else 'Min_SI'
        
        # Exibe tabela com a coluna "Mínimo" (Meta)
        st.dataframe(df_l[['Produto', 'Estoque_Atual', col_min, 'Fornecedor']], use_container_width=True)
    else: st.info("Vazio")
