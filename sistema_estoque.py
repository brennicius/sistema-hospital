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

st.set_page_config(page_title="Sistema 28.0 (Parâmetros)", layout="wide")

# --- INICIALIZAÇÃO DE ESTADO ---
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
    colunas = ["Loja", "Produto", "Estoque_Atual", "Media_Vendas_Semana", "Ultima_Atualizacao", "Fornecedor", "Custo_Unit"]
    if not os.path.exists(ARQUIVO_DADOS): return pd.DataFrame(columns=colunas)
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)
    
    for c in ["Estoque_Atual", "Media_Vendas_Semana", "Custo_Unit"]:
        if c in df.columns: df[c] = df[c].apply(limpar_numero)
        else: df[c] = 0
    
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    
    if not df.empty:
        df = df.groupby(['Loja', 'Produto', 'Fornecedor', 'Ultima_Atualizacao'], as_index=False).agg({
            'Estoque_Atual': 'sum', 'Media_Vendas_Semana': 'max', 'Custo_Unit': 'max'
        })
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
            if "Produto" in cols: larguras[cols.index("Produto")] = 80
        else: larguras = colunas_largura
        pdf.set_font("Arial", 'B', 9)
        for i, col in enumerate(cols): 
            txt = str(col).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(larguras[i], 10, txt[:20], 1, 0, 'C')
        pdf.ln()
        pdf.set_font("Arial", size=9)
        for index, row in dataframe.iterrows():
            for i, col in enumerate(cols):
                txt = str(row[col]).encode('latin-1', 'replace').decode('latin-1')
                align = 'L' if i==0 else 'C'
                pdf.cell(larguras[i], 10, txt[:45], 1, 0, align)
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
    with st.expander("📉 Baixar Vendas do Dia (Upload Relatório)", expanded=True):
        arquivo_vendas = st.file_uploader("Relatório de Vendas (Excel/CSV)", type=['csv', 'xlsx'], key="up_vendas")
        if arquivo_vendas:
            try:
                if arquivo_vendas.name.endswith('.csv'): df_vendas = pd.read_csv(arquivo_vendas)
                else: df_vendas = pd.read_excel(arquivo_vendas)
                st.write("Confirme as colunas:")
                c1, c2 = st.columns(2)
                cols = df_vendas.columns.tolist()
                idx_n = next((i for i, c in enumerate(cols) if "nome" in c.lower() or "prod" in c.lower() or "desc" in c.lower()), 0)
                idx_q = next((i for i, c in enumerate(cols) if "qtd" in c.lower() or "quant" in c.lower()), 0)
                cn = c1.selectbox("Coluna Produto", cols, index=idx_n)
                cq = c2.selectbox("Coluna Qtd", cols, index=idx_q)
                if st.button("🚀 Processar Baixa"):
                    suc = 0; err = []
                    for i, r in df_vendas.iterrows():
                        p = str(r[cn]).strip()
                        q = limpar_numero(r[cq])
                        if q > 0:
                            mask = (df_geral['Loja'] == loja_selecionada) & (df_geral['Produto'] == p)
                            if mask.any():
                                cur = df_geral.loc[mask, 'Estoque_Atual'].values[0]
                                df_geral.loc[mask, 'Estoque_Atual'] = max(0, cur - q)
                                suc += 1
                            else: err.append(p)
                    if suc > 0:
                        df_geral.loc[df_geral['Loja'] == loja_selecionada, 'Ultima_Atualizacao'] = datetime.now().strftime("%d/%m %H:%M")
                        salvar_dados(df_geral); registrar_log("Vários", suc, "Venda", f"Arquivo {loja_selecionada}"); st.success(f"✅ {suc} itens baixados!"); st.rerun()
                    else: st.warning("Nenhum item processado.")
            except Exception as e: st.error(f"Erro: {e}")

# --- INTERFACE ---
st.title("🚀 Sistema Integrado 28.0")
df_geral = carregar_dados_cache()

with st.sidebar:
    st.header("Menu")
    modo = st.radio("Ir para:", UNIDADES)
    st.divider()
    
    # UPLOAD ESTOQUE (QUANTIDADE FÍSICA)
    if modo in ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"]:
        with st.expander("📦 Upload Estoque (Contagem)"):
            st.info("Atualiza a quantidade física. Mantém média e preço.")
            f = st.file_uploader("Planilha Estoque", type=['csv', 'xlsx'], key="ue")
            if f:
                try:
                    df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                    mapa = {}
                    for c in df.columns:
                        cl = c.lower()
                        if "prod" in cl or "nome" in cl: mapa[c] = "Produto"
                        elif any(x in cl for x in ['est','qtd','quant','saldo','contagem']): mapa[c] = "Estoque_Atual"
                    df = df.rename(columns=mapa)
                    if "Produto" in df.columns:
                        if "Estoque_Atual" in df.columns: df["Estoque_Atual"] = df["Estoque_Atual"].apply(limpar_numero)
                        else: df["Estoque_Atual"] = 0
                        df["Loja"] = modo; df["Ultima_Atualizacao"] = datetime.now().strftime("%d/%m %H:%M")
                        
                        # Preserva Média e Preço
                        ant = df_geral[df_geral['Loja']==modo].set_index('Produto')
                        ant = ant[~ant.index.duplicated(keep='first')]
                        df = df.set_index('Produto')
                        
                        if not ant.empty:
                            df['Media_Vendas_Semana'] = df.index.map(ant['Media_Vendas_Semana']).fillna(0)
                            df['Fornecedor'] = df.index.map(ant['Fornecedor']).fillna("Geral")
                            df['Custo_Unit'] = df.index.map(ant['Custo_Unit']).fillna(0)
                        else: 
                            df['Media_Vendas_Semana']=0; df['Fornecedor']="Geral"; df['Custo_Unit']=0
                        
                        out = df_geral[df_geral['Loja']!=modo]
                        salvar_dados(pd.concat([out, df.reset_index()], ignore_index=True))
                        resetar_processos(); st.success("Estoque Atualizado!"); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

        # ATUALIZAR PARÂMETROS (MÉDIA) - NOVO!
        with st.expander("⚙️ Atualizar Média/Parâmetros"):
            st.info("Atualiza apenas a meta/média. Não muda o estoque físico.")
            f_param = st.file_uploader("Planilha Parâmetros", type=['csv', 'xlsx'], key="up_param")
            if f_param:
                try:
                    df_p = pd.read_csv(f_param) if f_param.name.endswith('.csv') else pd.read_excel(f_param)
                    st.write("Selecione as colunas:")
                    cp1, cp2 = st.columns(2)
                    cols_p = df_p.columns.tolist()
                    idx_pn = next((i for i, c in enumerate(cols_p) if "prod" in c.lower() or "nome" in c.lower()), 0)
                    idx_pm = next((i for i, c in enumerate(cols_p) if any(x in c.lower() for x in ['med','méd','param','padr','min'])), 0)
                    
                    c_prod = cp1.selectbox("Produto", cols_p, index=idx_pn)
                    c_media = cp2.selectbox("Média/Parâmetro", cols_p, index=idx_pm)
                    
                    if st.button("💾 Salvar Médias"):
                        df_p = df_p.rename(columns={c_prod: "Produto", c_media: "Nova_Media"})
                        df_p["Nova_Media"] = df_p["Nova_Media"].apply(limpar_numero)
                        df_p = df_p.set_index("Produto")
                        
                        # Atualiza apenas a loja atual
                        df_g = df_geral.set_index("Produto")
                        mask_loja = df_g['Loja'] == modo
                        
                        # Atualiza onde coincidir
                        df_g.loc[mask_loja, 'Media_Vendas_Semana'] = df_g.loc[mask_loja].index.map(df_p['Nova_Media']).fillna(df_g.loc[mask_loja, 'Media_Vendas_Semana'])
                        
                        salvar_dados(df_g.reset_index()); st.success("Parâmetros Atualizados!"); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

    with st.expander("💲 Atualizar Preços"):
        f = st.file_uploader("Arquivo", type=['csv', 'xlsx'], key="up")
        if f and st.button("Salvar Preços"):
            try:
                df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                mapa = {}
                for c in df.columns:
                    cl = c.lower()
                    if "prod" in cl: mapa[c] = "Produto"
                    elif "forn" in cl: mapa[c] = "Fornecedor"
                    elif any(x in cl for x in ['cust', 'pre', 'valor']): mapa[c] = "Custo_Unit"
                df = df.rename(columns=mapa)
                if "Custo_Unit" in df.columns: df["Custo_Unit"] = df["Custo_Unit"].apply(limpar_numero)
                df = df.drop_duplicates('Produto').set_index('Produto')
                g = df_geral.set_index('Produto')
                if "Fornecedor" in df.columns: g.update(df[['Fornecedor']])
                if "Custo_Unit" in df.columns: g.update(df[['Custo_Unit']])
                salvar_dados(g.reset_index()); st.success("Ok!"); st.rerun()
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
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔥 Consumo (CMV)")
        cmv = calcular_cmv_mensal()
        if not cmv.empty: st.bar_chart(cmv.set_index('Loja'))
        else: st.info("Sem dados")
    with c2:
        st.markdown("### 🏆 Top Valor")
        st.bar_chart(df_c.groupby('Produto')['Valor'].sum().sort_values(ascending=False).head(10))

elif modo == "📜 Histórico":
    st.subheader("Log")
    if os.path.exists(ARQUIVO_LOG): st.dataframe(pd.read_csv(ARQUIVO_LOG).sort_values('Data', ascending=False), use_container_width=True)
    else: st.info("Vazio")

elif modo == "🛒 Compras":
    st.subheader("Compras")
    if st.session_state['df_compras_temp'] is None:
        base = df_geral[df_geral['Loja']=="Estoque Central"][['Produto','Fornecedor','Custo_Unit']].copy()
        base = base.drop_duplicates('Produto').sort_values('Produto')
        base['Qtd'] = 0 
        st.session_state['df_compras_temp'] = base
    
    if 'Qtd' not in st.session_state['df_compras_temp'].columns: st.session_state['df_compras_temp'] = None; st.rerun()

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
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 Baixar Pedido PDF"):
            i = st.session_state['df_compras_temp'].copy(); i['Total'] = i['Qtd'] * i['Custo_Unit']; i = i[i['Qtd']>0]
            if not i.empty:
                pdf_bytes = criar_pdf_generico(i[['Produto','Fornecedor','Qtd','Total']], "PEDIDO DE COMPRA", [90,50,20,30])
                st.download_button("Clique para Baixar PDF", pdf_bytes, "Pedido.pdf", "application/pdf")
                registrar_log("Vários", len(i), "Compra", f"R$ {total_ped:.2f}")
            else: st.warning("Vazio")
    with c2:
        i_xls = st.session_state['df_compras_temp'].copy(); i_xls['Total'] = i_xls['Qtd'] * i_xls['Custo_Unit']; i_xls = i_xls[i_xls['Qtd']>0]
        if not i_xls.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: i_xls[['Produto','Fornecedor','Qtd','Total']].to_excel(writer, index=False, sheet_name='Pedido')
            st.download_button("📊 Baixar Pedido Excel", buffer.getvalue(), "Pedido_Compra.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif modo == "Estoque Central":
    if st.session_state['distribuicao_concluida']:
        st.success("Sucesso!")
        if st.session_state.get('romaneio_pdf_cache'): st.download_button("Baixar Romaneio", st.session_state['romaneio_pdf_cache'], "Rom.pdf", "application/pdf")
        if st.session_state['romaneio_final'] is not None: st.dataframe(st.session_state['romaneio_final'], use_container_width=True)
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
                salvar_dados(df_geral); registrar_log(p, q, "Entrada", "Man"); st.success("Ok"); st.rerun()
            if c2.button("Baixa"):
                idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                cur = df_geral.loc[idx, 'Estoque_Atual'].values[0]
                df_geral.loc[idx, 'Estoque_Atual'] = max(0, cur-q)
                salvar_dados(df_geral); registrar_log(p, q, "Baixa", "Man"); st.success("Ok"); st.rerun()
        
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
                st.session_state['romaneio_final'] = pd.DataFrame(rom)
                st.session_state['distribuicao_concluida'] = True
                st.session_state['df_distribuicao_temp'] = None
                st.rerun()

else:
    st.subheader(f"Gestão: {modo}")
    df_l = df_geral[df_geral['Loja'] == modo].copy()
    if not df_l.empty:
        renderizar_baixa_por_arquivo(df_geral, modo)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_l[['Produto', 'Estoque_Atual', 'Media_Vendas_Semana']].to_excel(writer, index=False, sheet_name='Estoque')
        st.download_button(f"📊 Baixar Estoque {modo} (.xlsx)", buf.getvalue(), f"Estoque_{modo}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        st.dataframe(df_l[['Produto', 'Estoque_Atual', 'Media_Vendas_Semana']], use_container_width=True)
    else: st.info("Vazio")
