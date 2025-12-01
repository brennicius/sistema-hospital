import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

st.set_page_config(page_title="Sistema Nuvem ☁️", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
# A conexão é criada uma vez e usada em todo o app
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INICIALIZAÇÃO DE ESTADO ---
def init_state():
    keys = ['df_distribuicao_temp', 'df_compras_temp', 'romaneio_final', 'romaneio_pdf_cache', 
            'distribuicao_concluida', 'pedido_compra_final', 'selecao_exclusao']
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = None if 'df' in k or 'romaneio' in k or 'pedido' in k else []
            if k == 'distribuicao_concluida': st.session_state[k] = False

init_state()

# --- FUNÇÕES DE DADOS (AGORA COM SHEETS) ---
def carregar_dados():
    colunas_padrao = ["Loja", "Produto", "Estoque_Atual", "Media_Vendas_Semana", "Ultima_Atualizacao", "Fornecedor", "Custo_Unit"]
    
    # TTL=0 garante que ele sempre pegue o dado fresco da planilha, não do cache antigo
    try:
        df = conn.read(worksheet="Estoque", ttl=0)
        # Se a planilha estiver vazia ou nova, cria a estrutura
        if df.empty or len(df.columns) < 2:
            return pd.DataFrame(columns=colunas_padrao)
    except:
        return pd.DataFrame(columns=colunas_padrao)
    
    # Tratamento de Nulos
    for col in ["Estoque_Atual", "Media_Vendas_Semana", "Custo_Unit"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    
    # Agrupamento para segurança
    if not df.empty:
        df = df.groupby(['Loja', 'Produto', 'Fornecedor', 'Ultima_Atualizacao'], as_index=False).agg({
            'Estoque_Atual': 'sum', 'Media_Vendas_Semana': 'max', 'Custo_Unit': 'max'
        })
    return df

def salvar_dados(df):
    # Salva na aba "Estoque" da planilha conectada
    conn.update(worksheet="Estoque", data=df)
    st.cache_data.clear() # Limpa cache interno do Streamlit

def carregar_log():
    try:
        df = conn.read(worksheet="Historico", ttl=0)
        if df.empty: return pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
        return df
    except:
        return pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo_log = pd.DataFrame([{
        "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Produto": produto,
        "Quantidade": quantidade,
        "Tipo": tipo,
        "Detalhe": origem_destino,
        "Usuario": usuario
    }])
    
    df_antigo = carregar_log()
    df_novo = pd.concat([df_antigo, novo_log], ignore_index=True)
    conn.update(worksheet="Historico", data=df_novo)

# --- FUNÇÕES AUXILIARES (IGUAIS AO ANTERIOR) ---
def calcular_kpis_avancados(df):
    df['Venda_Diaria'] = df['Media_Vendas_Semana'] / 7
    df['Dias_Cobertura'] = df.apply(lambda x: x['Estoque_Atual'] / x['Venda_Diaria'] if x['Venda_Diaria'] > 0 else 999, axis=1)
    df['Valor_Total'] = df['Estoque_Atual'] * df['Custo_Unit']
    df = df.sort_values('Valor_Total', ascending=False)
    total = df['Valor_Total'].sum()
    if total > 0:
        df['Acumulado'] = df['Valor_Total'].cumsum()
        df['Perc'] = df['Acumulado'] / total
        df['Classe_ABC'] = df['Perc'].apply(lambda x: "A" if x<=0.8 else "B" if x<=0.95 else "C")
    else: df['Classe_ABC'] = "C"
    return df

def status_cobertura(dias):
    if dias <= 3: return "🔴 Crítico"
    elif dias <= 7: return "🟠 Baixo"
    elif dias <= 30: return "🟢 Saudável"
    else: return "🔵 Excesso"

def criar_pdf_generico(dataframe, titulo_doc, colunas_largura=None):
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
        if "Produto" in cols: larguras[cols.index("Produto")] = 80
    else: larguras = colunas_largura
    pdf.set_font("Arial", 'B', 9)
    for i, col in enumerate(cols): pdf.cell(larguras[i], 10, col[:15], 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", size=9)
    for index, row in dataframe.iterrows():
        for i, col in enumerate(cols):
            txt = str(row[col]).encode('latin-1', 'replace').decode('latin-1')
            align = 'L' if i==0 else 'C'
            pdf.cell(larguras[i], 10, txt[:45], 1, 0, align)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

def resetar_processos():
    for k in ['df_distribuicao_temp', 'romaneio_final', 'df_compras_temp', 'pedido_compra_final', 'romaneio_pdf_cache']:
        st.session_state[k] = None
    st.session_state['distribuicao_concluida'] = False

def limpar_selecao(): st.session_state['selecao_exclusao'] = []
def selecionar_tudo_loja(): 
    if 'df_loja_atual' in st.session_state: st.session_state['selecao_exclusao'] = st.session_state['df_loja_atual']['Produto'].tolist()

def calcular_cmv_mensal():
    df_log = carregar_log()
    df_est = carregar_dados()
    if df_log.empty or df_est.empty: return pd.DataFrame()
    df_c = df_log[df_log['Tipo'].isin(['Baixa', 'Venda'])].copy()
    if df_c.empty: return pd.DataFrame()
    mapa = df_est.groupby('Produto')['Custo_Unit'].max()
    df_c['Custo'] = df_c['Produto'].map(mapa).fillna(0)
    df_c['Total'] = df_c['Quantidade'] * df_c['Custo']
    def id_loja(x):
        x=str(x).lower()
        if "amaro" in x: return "Sto Amaro"
        if "izabel" in x: return "Sta Izabel"
        if "central" in x: return "Central"
        return "Outros"
    df_c['Loja'] = df_c['Detalhe'].apply(id_loja)
    return df_c.groupby('Loja')['Total'].sum().reset_index()

# --- INTERFACE ---
st.title("☁️ Sistema Integrado Google Sheets")
try:
    df_geral = carregar_dados()
except Exception as e:
    st.error("Erro ao conectar no Google Sheets. Verifique o arquivo secrets.toml")
    st.stop()

# BARRA LATERAL
with st.sidebar:
    st.header("Navegação")
    modo = st.radio("Ir para:", UNIDADES)
    st.divider()
    
    # UPLOAD
    if modo in ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"]:
        with st.expander("📦 Upload Estoque"):
            arquivo = st.file_uploader("Planilha", type=['csv', 'xlsx'], key="up_est")
            if arquivo:
                try:
                    df_r = pd.read_csv(arquivo) if arquivo.name.endswith('.csv') else pd.read_excel(arquivo)
                    mapa = {}
                    for c in df_r.columns:
                        cl = c.lower()
                        if "prod" in cl: mapa[c] = "Produto"
                        elif "est" in cl or "qtd" in cl: mapa[c] = "Estoque_Atual"
                        elif "med" in cl: mapa[c] = "Media_Vendas_Semana"
                    df_p = df_r.rename(columns=mapa)
                    
                    if "Produto" in df_p.columns:
                        if "Estoque_Atual" not in df_p.columns: df_p["Estoque_Atual"] = 0
                        if "Media_Vendas_Semana" not in df_p.columns: df_p["Media_Vendas_Semana"] = 0
                        df_p["Loja"] = modo
                        df_p["Ultima_Atualizacao"] = datetime.now().strftime("%d/%m %H:%M")
                        
                        df_ant = df_geral[df_geral['Loja'] == modo].set_index('Produto')
                        df_ant = df_ant[~df_ant.index.duplicated(keep='first')]
                        df_p = df_p.set_index('Produto')
                        
                        if not df_ant.empty:
                            df_p['Fornecedor'] = df_p.index.map(df_ant['Fornecedor']).fillna("Geral")
                            df_p['Custo_Unit'] = df_p.index.map(df_ant['Custo_Unit']).fillna(0)
                        else:
                            df_p['Fornecedor'] = "Geral"; df_p['Custo_Unit'] = 0
                            
                        df_out = df_geral[df_geral['Loja'] != modo]
                        df_fin = pd.concat([df_out, df_p.reset_index()], ignore_index=True)
                        salvar_dados(df_fin); resetar_processos(); st.success("Salvo na Nuvem!"); st.rerun()
                except: st.error("Erro no arquivo")

    with st.expander("💲 Atualizar Preços"):
        arq_p = st.file_uploader("Preços", type=['csv', 'xlsx'], key="up_pr")
        if arq_p and st.button("Salvar Preços"):
            try:
                df_p = pd.read_csv(arq_p) if arq_p.name.endswith('.csv') else pd.read_excel(arq_p)
                mapa = {}
                for c in df_p.columns:
                    cl = c.lower()
                    if "prod" in cl: mapa[c] = "Produto"
                    elif "forn" in cl: mapa[c] = "Fornecedor"
                    elif "cust" in cl or "pre" in cl: mapa[c] = "Custo_Unit"
                df_p = df_p.rename(columns=mapa).drop_duplicates('Produto').set_index('Produto')
                df_g = df_geral.set_index('Produto')
                if "Fornecedor" in df_p.columns: df_g.update(df_p[['Fornecedor']])
                if "Custo_Unit" in df_p.columns: df_g.update(df_p[['Custo_Unit']])
                salvar_dados(df_g.reset_index()); st.success("Atualizado!"); st.rerun()
            except: st.error("Erro")

    with st.expander("🗑️ Lixeira"):
        df_loja = df_geral[df_geral['Loja'] == modo]
        st.session_state['df_loja_atual'] = df_loja
        c1, c2 = st.columns(2)
        c1.button("Tudo", on_click=selecionar_tudo_loja)
        c2.button("Limpar", on_click=limpar_selecao)
        itens = st.multiselect("Apagar:", df_loja['Produto'].unique(), key='selecao_exclusao')
        if st.button("❌ Apagar"):
            mask = ~((df_geral['Loja'] == modo) & (df_geral['Produto'].isin(itens)))
            salvar_dados(df_geral[mask]); resetar_processos(); st.success("Apagado!"); st.rerun()

# --- PÁGINAS ---
if modo == "📊 Dashboard":
    st.subheader("Visão Financeira (Nuvem)")
    df_c = df_geral.copy()
    df_c['Valor'] = df_c['Estoque_Atual'] * df_c['Custo_Unit']
    k1, k2, k3 = st.columns(3)
    k1.metric("Valor Total", f"R$ {df_c['Valor'].sum():,.2f}")
    k2.metric("Itens", f"{df_c['Estoque_Atual'].sum():,.0f}")
    k3.metric("Zerados", len(df_c[df_c['Estoque_Atual'] <= 0]))
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔥 Consumo Mensal (CMV)")
        df_cmv = calcular_cmv_mensal()
        if not df_cmv.empty: st.bar_chart(df_cmv.set_index('Loja'))
        else: st.info("Sem dados de consumo ainda.")
    with c2:
        st.markdown("### 🏆 Top Valor")
        st.bar_chart(df_c.groupby('Produto')['Valor'].sum().sort_values(ascending=False).head(10))

elif modo == "📜 Histórico":
    st.subheader("Log de Operações (Sheets)")
    st.dataframe(carregar_log().sort_values('Data', ascending=False), use_container_width=True)

elif modo == "🛒 Compras":
    st.subheader("Compras")
    if st.session_state['df_compras_temp'] is None:
        df_base = df_geral[df_geral['Loja'] == "Estoque Central"][['Produto', 'Fornecedor', 'Custo_Unit']].copy()
        df_base = df_base.drop_duplicates('Produto').sort_values('Produto')
        df_base['Qtd'] = 0
        st.session_state['df_compras_temp'] = df_base
    
    df_v = st.session_state['df_compras_temp']
    f_list = ["Todos"] + sorted(df_v['Fornecedor'].unique().tolist())
    sel_f = st.selectbox("Fornecedor", f_list)
    df_e = df_v[df_v['Fornecedor'] == sel_f].copy() if sel_f != "Todos" else df_v.copy()
    df_e['Total'] = df_e['Qtd'] * df_e['Custo_Unit']
    
    ed = st.data_editor(df_e, column_config={"Qtd": st.column_config.NumberColumn(min_value=0), "Custo_Unit": st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    if not ed.equals(df_e):
        df_v.set_index('Produto', inplace=True); ed.set_index('Produto', inplace=True)
        df_v.update(ed); df_v.reset_index(inplace=True)
        st.session_state['df_compras_temp'] = df_v; st.rerun()
        
    st.metric("Total", f"R$ {ed['Total'].sum():,.2f}")
    if st.button("Baixar Pedido"):
        i = st.session_state['df_compras_temp']
        i = i[i['Qtd'] > 0]
        if not i.empty:
            pdf = criar_pdf_generico(i[['Produto', 'Fornecedor', 'Qtd', 'Total']], "PEDIDO", [90, 50, 20, 30])
            st.download_button("PDF", pdf, "Ped.pdf", "application/pdf")
            registrar_log("Vários", len(i), "Compra", f"R$ {ed['Total'].sum():.2f}")

elif modo == "Estoque Central":
    if st.session_state['distribuicao_concluida']:
        st.success("Sucesso!")
        if st.session_state.get('romaneio_pdf_cache'): st.download_button("Baixar Romaneio", st.session_state['romaneio_pdf_cache'], "Rom.pdf", "application/pdf")
        if st.button("Voltar"): resetar_processos(); st.rerun()
    else:
        st.subheader("Distribuição")
        with st.expander("Ajuste Manual"):
            p = st.selectbox("Prod", df_geral[df_geral['Loja']==modo]['Produto'].unique())
            q = st.number_input("Qtd", 1.0)
            c1, c2 = st.columns(2)
            if c1.button("Entrada"):
                idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                df_geral.loc[idx, 'Estoque_Atual'] += q
                salvar_dados(df_geral); registrar_log(p, q, "Entrada", "Manual"); st.success("Ok"); st.rerun()
            if c2.button("Baixa"):
                idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                cur = df_geral.loc[idx, 'Estoque_Atual'].values[0]
                df_geral.loc[idx, 'Estoque_Atual'] = max(0, cur-q)
                salvar_dados(df_geral); registrar_log(p, q, "Baixa", "Manual"); st.success("Ok"); st.rerun()
        
        search = st.text_input("Buscar", placeholder="Nome...")
        if st.session_state['df_distribuicao_temp'] is None:
            df_b = df_geral[df_geral['Loja']==modo][['Produto','Estoque_Atual']].copy()
            df_b['Env SA'] = 0; df_b['Env SI'] = 0
            for l, s in [("Hosp. Santo Amaro","SA"), ("Hosp. Santa Izabel","SI")]:
                df_h = df_geral[df_geral['Loja']==l].set_index('Produto')
                df_h = df_h[~df_h.index.duplicated(keep='first')]
                df_b[f'Tem {s}'] = df_b['Produto'].map(df_h['Estoque_Atual']).fillna(0)
                df_b[f'Med {s}'] = df_b['Produto'].map(df_h['Media_Vendas_Semana']).fillna(0)
            st.session_state['df_distribuicao_temp'] = df_b
            
        df_w = st.session_state['df_distribuicao_temp']
        df_view = df_w[df_w['Produto'].str.contains(search, case=False, na=False)].copy() if search else df_w.sort_values('Estoque_Atual', ascending=False).head(50).copy()
        
        df_view['Saldo'] = df_view['Estoque_Atual'] - df_view['Env SA'] - df_view['Env SI']
        cols = ['Produto', 'Estoque_Atual', 'Saldo', 'Tem SA', 'Med SA', 'Env SA', 'Tem SI', 'Med SI', 'Env SI']
        
        ed = st.data_editor(df_view[cols], column_config={"Estoque_Atual": st.column_config.NumberColumn(disabled=True), "Saldo": st.column_config.NumberColumn(disabled=True), "Tem SA": st.column_config.NumberColumn(disabled=True), "Med SA": st.column_config.NumberColumn(disabled=True), "Tem SI": st.column_config.NumberColumn(disabled=True), "Med SI": st.column_config.NumberColumn(disabled=True)}, use_container_width=True, height=500)
        
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
                        for l, q, s in [("Hosp. Santo Amaro", sa, "SA"), ("Hosp. Santa Izabel", si, "SI")]:
                            if q>0:
                                idl = (df_geral['Loja']==l)&(df_geral['Produto']==p)
                                if idl.any(): df_geral.loc[idl, 'Estoque_Atual'] += q
                                else:
                                    n = df_geral.loc[idx].iloc[0].copy(); n['Loja']=l; n['Estoque_Atual']=q; n['Media_Vendas_Semana']=r.get(f'Med {s}',0)
                                    df_geral = pd.concat([df_geral, pd.DataFrame([n])], ignore_index=True)
                        rom.append({"Produto":p, "Env SA":sa, "Env SI":si})
                        registrar_log(p, sa+si, "Transferência", f"SA:{sa} SI:{si}")
                salvar_dados(df_geral)
                pdf = criar_pdf_generico(pd.DataFrame(rom), "ROMANEIO")
                st.session_state['romaneio_pdf_cache'] = pdf
                st.session_state['distribuicao_concluida'] = True
                st.session_state['df_distribuicao_temp'] = None
                st.rerun()

else:
    st.subheader(f"Gestão: {modo}")
    df_l = df_geral[df_geral['Loja'] == modo].copy()
    if not df_l.empty:
        with st.expander("📉 Baixa por Arquivo"):
            upl = st.file_uploader("Arquivo", key="vendas")
            if upl:
                try:
                    df_v = pd.read_csv(upl) if upl.name.endswith('.csv') else pd.read_excel(upl)
                    cols = df_v.columns.tolist()
                    c1, c2 = st.columns(2)
                    idx_n = next((i for i, c in enumerate(cols) if "nome" in c.lower() or "prod" in c.lower()), 0)
                    idx_q = next((i for i, c in enumerate(cols) if "qtd" in c.lower()), 0)
                    cn = c1.selectbox("Nome", cols, index=idx_n)
                    cq = c2.selectbox("Qtd", cols, index=idx_q)
                    if st.button("Processar"):
                        cnt = 0
                        for i, r in df_v.iterrows():
                            p = str(r[cn]).strip()
                            q = float(r[cq]) if pd.notnull(r[cq]) else 0
                            if q>0:
                                m = (df_geral['Loja']==modo)&(df_geral['Produto']==p)
                                if m.any():
                                    df_geral.loc[m, 'Estoque_Atual'] = max(0, df_geral.loc[m, 'Estoque_Atual'].values[0]-q)
                                    cnt+=1
                        if cnt>0: salvar_dados(df_geral); registrar_log("Vários", cnt, "Venda", modo); st.success(f"{cnt} baixados!"); st.rerun()
                except: st.error("Erro arquivo")
        st.dataframe(df_l[['Produto','Estoque_Atual','Media_Vendas_Semana']], use_container_width=True)
    else: st.info("Vazio")