import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Online (Excel)", layout="wide", initial_sidebar_state="collapsed")
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

# --- CONEXÃO GOOGLE SHEETS ---
# O ttl=0 obriga o sistema a pegar dados novos sempre
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INICIALIZAÇÃO ---
def init_state():
    keys = ['carga_acumulada', 'transf_df_cache', 'transf_key_ver', 'transf_last_dest', 
            'compras_df_cache', 'compras_key_ver', 'last_forn', 'tela_atual', 'selecao_exclusao']
    for k in keys:
        if k not in st.session_state:
            if 'cache' in k: st.session_state[k] = None
            elif 'ver' in k: st.session_state[k] = 0
            elif 'carga' in k or 'selecao' in k: st.session_state[k] = []
            elif 'last' in k: st.session_state[k] = ""
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Estoque"

init_state()

# --- FUNÇÕES DE DADOS ---
def limpar_numero(v):
    if pd.isna(v): return 0.0
    s = str(v).lower().replace('r$','').replace('kg','').replace('un','').replace(' ','').replace(',','.')
    try: return float(s)
    except: return 0.0

def carregar_dados():
    cols = ["Codigo", "Produto", "Categoria", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI", "Estoque_Central", "Estoque_SA", "Estoque_SI", "Ultima_Atualizacao"]
    try:
        df = conn.read(worksheet="Estoque", ttl=0)
        if df.empty: return pd.DataFrame(columns=cols)
        for c in cols:
            if c not in df.columns: df[c] = 0 if "Estoque" in c or "Min" in c or "Custo" in c else ""
        
        # Tipagem forte
        num_cols = ["Estoque_Central", "Estoque_SA", "Estoque_SI", "Min_SA", "Min_SI", "Custo"]
        for c in num_cols: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
        df['Produto'] = df['Produto'].astype(str)
        df = df.drop_duplicates('Produto', keep='last')
        return df
    except: return pd.DataFrame(columns=cols)

def salvar_dados(df):
    conn.update(worksheet="Estoque", data=df)
    st.cache_data.clear()

def registrar_log(prod, qtd, tipo, det):
    try:
        novo = pd.DataFrame([{"Data": datetime.now().strftime("%Y-%m-%d %H:%M"), "Produto": prod, "Qtd": qtd, "Tipo": tipo, "Detalhe": det, "Usuario": "Sistema"}])
        try: antigo = conn.read(worksheet="Historico", ttl=0)
        except: antigo = pd.DataFrame()
        final = pd.concat([antigo, novo], ignore_index=True)
        conn.update(worksheet="Historico", data=final)
    except: pass

# --- MENU ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema Conectado ☁️</h2>", unsafe_allow_html=True)
st.markdown("---")
c1, c2, c3, c4, c5, c6 = st.columns(6)
def btn(col, t, i, k):
    if col.button(f"{i}\n{t}", key=k, use_container_width=True, type="primary" if st.session_state['tela_atual']==k else "secondary"):
        st.session_state['tela_atual'] = k; st.rerun()

btn(c1,"Estoque","📦","Estoque"); btn(c2,"Transferir","🚚","Transferencia"); btn(c3,"Compras","🛒","Compras")
btn(c4,"Produtos","📋","Produtos"); btn(c5,"Vendas","📉","Vendas"); btn(c6,"Histórico","📜","Historico")
st.markdown("---")

tela = st.session_state['tela_atual']
try: df = carregar_dados()
except: st.error("Erro de conexão Google Sheets."); st.stop()

# --- TELAS ---

if tela == "Estoque":
    st.header("📦 Contagem de Estoque")
    c_l, _ = st.columns([1,2])
    loc = c_l.selectbox("Local", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    
    col_map = {"Estoque Central": "Estoque_Central", "Hosp. Santo Amaro": "Estoque_SA", "Hosp. Santa Izabel": "Estoque_SI"}
    col_alvo = col_map[loc]
    
    with st.expander("📂 Upload Planilha"):
        f = st.file_uploader("Arquivo", key="up1")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                # Auto map simples
                cn = next((c for c in d.columns if "prod" in str(c).lower()), None)
                cq = next((c for c in d.columns if "qtd" in str(c).lower()), None)
                if cn and cq:
                    for i, r in d.iterrows():
                        p = str(r[cn]).strip(); q = limpar_numero(r[cq])
                        m = df['Produto'] == p
                        if m.any(): df.loc[m, col_alvo] = q
                        else:
                            n = {c:0 for c in df.columns}; n['Produto']=p; n[col_alvo]=q; n['Categoria']="Novo"
                            df = pd.concat([df, pd.DataFrame([n])], ignore_index=True)
                    salvar_dados(df); st.success("Ok!"); st.rerun()
            except: st.error("Erro arquivo")
    
    busca = st.text_input("Buscar:", "")
    v = df[df['Produto'].str.contains(busca, case=False, na=False)] if busca else df
    st.dataframe(v[['Codigo', 'Produto', col_alvo]], use_container_width=True)

elif tela == "Transferencia":
    st.header("🚚 Transferência")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        dest = st.selectbox("Destino:", ["Hosp. Santo Amaro", "Hosp. Santa Izabel"])
        if dest != st.session_state.get('transf_last_dest'): st.session_state['transf_df_cache']=None; st.session_state['transf_last_dest']=dest
        
        ce = "Estoque_SA" if "Amaro" in dest else "Estoque_SI"
        cm = "Min_SA" if "Amaro" in dest else "Min_SI"
        
        if st.button("🪄 Sugestão"):
            d = df[['Produto','Estoque_Central',ce,cm]].copy()
            d['Env'] = (d[cm]-d[ce]).apply(lambda x: max(0, int(x)))
            st.session_state['transf_df_cache'] = d; st.rerun()
            
        v = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df[['Produto','Estoque_Central',ce,cm]].assign(Env=0)
        b = st.text_input("Busca:", "")
        if b: v = v[v['Produto'].str.contains(b, case=False, na=False)]
        
        ed = st.data_editor(v, column_config={"Produto":st.column_config.TextColumn(disabled=True),"Estoque_Central":st.column_config.NumberColumn(disabled=True),"Env":st.column_config.NumberColumn(min_value=0)}, use_container_width=True, height=400)
        
        if st.button("Adicionar Carga"):
            its = ed[ed['Env']>0]
            if not its.empty:
                l = []
                for i, r in its.iterrows():
                    p=r['Produto']; q=int(r['Env'])
                    idx = df[df['Produto']==p].index[0]
                    df.at[idx, 'Estoque_Central'] -= q
                    df.at[idx, ce] += q
                    l.append({"Destino":dest, "Produto":p, "Qtd":q})
                    registrar_log(p, q, "Transf", dest)
                salvar_dados(df); st.session_state['carga'].extend(l); st.session_state['transf_df_cache']=None; st.success("Adicionado!"); st.rerun()
    
    with c2:
        st.markdown("### Carga")
        if st.session_state['carga']:
            dc = pd.DataFrame(st.session_state['carga'])
            st.dataframe(dc, use_container_width=True)
            
            # GERAR EXCEL (SUBSTITUI O PDF)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: dc.to_excel(w, index=False)
            st.download_button("📊 Baixar Romaneio (Excel)", buf.getvalue(), "Romaneio.xlsx")
            
            if st.button("Limpar"): st.session_state['carga']=[]; st.rerun()
        else: st.info("Vazia")

elif tela == "Compras":
    st.header("🛒 Compras")
    l = ["Todos"] + sorted([str(x) for x in df['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", l)
    
    if st.button("Calcular Sugestão"):
        d = df.copy() if sel=="Todos" else df[df['Fornecedor']==sel].copy()
        d['Meta'] = d['Min_SA'] + d['Min_SI']
        d['Total'] = d['Estoque_Central'] + d['Estoque_SA'] + d['Estoque_SI']
        d['Compra'] = (d['Meta'] - d['Total']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = d; st.rerun()
    
    v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df.copy() if sel=="Todos" else df[df['Fornecedor']==sel].copy())
    if 'Compra' not in v.columns: v['Compra'] = 0
    
    ed = st.data_editor(v[['Produto','Fornecedor','Custo','Compra']], column_config={"Compra":st.column_config.NumberColumn(min_value=0)}, use_container_width=True, height=500)
    
    total = (ed['Compra'] * ed['Custo']).sum()
    st.metric("Total", f"R$ {total:,.2f}")
    
    i = ed[ed['Compra']>0]
    if not i.empty:
        # GERAR EXCEL (SUBSTITUI O PDF)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: i.to_excel(w, index=False)
        st.download_button("📊 Baixar Pedido (Excel)", buf.getvalue(), "Pedido.xlsx")

elif tela == "Produtos":
    st.header("📋 Cadastro")
    with st.expander("Upload"):
        f = st.file_uploader("Arquivo", key="upm")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cols = {c.lower():c for c in d.columns}
                def g(k): 
                    for x in k:
                        for ky in cols: 
                            if x in ky: return cols[ky]
                    return None
                cn = g(['prod','nome']); cf = g(['forn']); cc = g(['cust'])
                if cn:
                    cnt=0
                    for i,r in d.iterrows():
                        p = str(r[cn]).strip()
                        if p and p!='nan':
                            m = df['Produto']==p
                            if m.any():
                                if cf: df.loc[m, 'Fornecedor'] = str(r[cf])
                                if cc: df.loc[m, 'Custo'] = limpar_numero(r[cc])
                            else:
                                n = {c:0 for c in df.columns}; n['Produto']=p; n['Categoria']='Geral'
                                df = pd.concat([df, pd.DataFrame([n])], ignore_index=True)
                            cnt+=1
                    salvar_dados(df); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro")
    st.dataframe(df)

elif tela == "Vendas":
    st.header("📉 Vendas")
    l = st.selectbox("Loja", ["Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    cm = "Estoque_SA" if "Amaro" in l else "Estoque_SI"
    f = st.file_uploader("Relatório Vendas")
    if f and st.button("Baixar"):
        try:
            d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            cn = d.columns[0]; cq = d.columns[1]
            cnt=0
            for i,r in d.iterrows():
                p=str(r[cn]).strip(); q=limpar_numero(r[cq])
                m = df['Produto']==p
                if m.any() and q>0:
                    df.loc[m, cm] = max(0, df.loc[m, cm].values[0]-q)
                    cnt+=1
            salvar_dados(df); registrar_log("Varios", cnt, "Venda", l); st.success(f"{cnt} baixados!"); st.rerun()
        except: st.error("Erro")

elif tela == "Historico":
    try: st.dataframe(conn.read(worksheet="Historico"))
    except: st.info("Sem dados")

elif tela == "Dashboard":
    st.metric("Total Itens", int(df['Estoque_Central'].sum() + df['Estoque_SA'].sum() + df['Estoque_SI'].sum()))
