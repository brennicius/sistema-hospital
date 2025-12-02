import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema 36.3 (Estável)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO ---
def init_state():
    keys = ['romaneio_pdf', 'romaneio_xlsx', 'pedido_pdf', 'pedido_xlsx', 'selecao_exclusao', 'carga_acumulada', 'transf_df_cache', 'compras_df_cache']
    for k in keys:
        if k not in st.session_state: st.session_state[k] = None if 'cache' in k or 'pdf' in k or 'xlsx' in k else []
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Estoque"
    if 'transf_key_ver' not in st.session_state: st.session_state['transf_key_ver'] = 0

init_state()

# --- FUNÇÕES ---
def limpar_numero(v):
    if pd.isna(v): return 0.0
    s = str(v).lower().replace('r$','').replace('kg','').replace('un','').replace(' ','').replace(',','.')
    try: return float(s)
    except: return 0.0

def limpar_inteiro(v):
    try: return int(round(limpar_numero(v)))
    except: return 0

@st.cache_data
def carregar_dados():
    colunas = ["Codigo", "Codigo_Unico", "Produto", "Produto_Alt", "Categoria", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI", "Estoque_Central", "Estoque_SA", "Estoque_SI"]
    if not os.path.exists(ARQUIVO_DADOS):
        pd.DataFrame(columns=colunas).to_csv(ARQUIVO_DADOS, index=False)
        return pd.DataFrame(columns=colunas)
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)
    
    for c in ["Estoque_Central", "Estoque_SA", "Estoque_SI", "Min_SA", "Min_SI"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    if "Custo" in df.columns: df["Custo"] = pd.to_numeric(df["Custo"], errors='coerce').fillna(0.0)
    
    return df.drop_duplicates('Produto', keep='last')

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def registrar_log(prod, qtd, tipo, det):
    novo = {"Data": datetime.now().strftime("%d/%m %H:%M"), "Produto": prod, "Qtd": qtd, "Tipo": tipo, "Detalhe": det, "Usuario": "Sistema"}
    if not os.path.exists(ARQUIVO_LOG): pd.DataFrame(columns=["Data", "Produto", "Qtd", "Tipo", "Detalhe", "Usuario"]).to_csv(ARQUIVO_LOG, index=False)
    pd.concat([pd.read_csv(ARQUIVO_LOG), pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF ---
def criar_pdf_unificado(lista):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="ROMANEIO", ln=True, align='C'); pdf.set_font("Arial", size=10); pdf.ln(10)
        df = pd.DataFrame(lista)
        piv = df.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index()
        for c in ["Hospital Santo Amaro", "Hospital Santa Izabel"]: 
            if c not in piv.columns: piv[c] = 0
        
        pdf.set_fill_color(220,220,220); pdf.set_font("Arial", 'B', 10)
        pdf.cell(110, 8, "Produto", 1, 0, 'C', 1); pdf.cell(40, 8, "Sto Amaro", 1, 0, 'C', 1); pdf.cell(40, 8, "Sta Izabel", 1, 1, 'C', 1)
        pdf.set_font("Arial", size=10)
        for i, r in piv.iterrows():
            p = str(r['Produto'])[:55].encode('latin-1','replace').decode('latin-1')
            sa = str(int(r["Hospital Santo Amaro"])) if r["Hospital Santo Amaro"]>0 else "-"
            si = str(int(r["Hospital Santa Izabel"])) if r["Hospital Santa Izabel"]>0 else "-"
            pdf.cell(110, 8, p, 1); pdf.cell(40, 8, sa, 1, 0, 'C'); pdf.cell(40, 8, si, 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return None

def criar_pdf_pedido(df, forn, total):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=f"PEDIDO - {forn}", ln=True, align='C'); pdf.ln(10)
        pdf.set_fill_color(220,220,220); pdf.set_font("Arial", 'B', 9)
        pdf.cell(90, 8, "Produto", 1, 0, 'C', 1); pdf.cell(20, 8, "Qtd", 1, 0, 'C', 1); pdf.cell(30, 8, "Total", 1, 1, 'C', 1)
        pdf.set_font("Arial", size=9)
        for i, r in df.iterrows():
            p = str(r['Produto'])[:45].encode('latin-1','replace').decode('latin-1')
            pdf.cell(90, 8, p, 1); pdf.cell(20, 8, str(int(r['Qtd Compra'])), 1, 0, 'C'); pdf.cell(30, 8, f"{r['Total Item']:.2f}", 1, 1, 'R')
        pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, txt=f"TOTAL: R$ {total:,.2f}", ln=True, align='R')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return None

# --- MENU ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Gestão Hospitalar</h2>", unsafe_allow_html=True)
c1,c2,c3,c4,c5,c6 = st.columns(6)
def btn(c, t, i, k):
    if c.button(f"{i}\n{t}", key=k, use_container_width=True, type="primary" if st.session_state['tela_atual']==k else "secondary"):
        st.session_state['tela_atual'] = k; st.rerun()
btn(c1,"Estoque","📦","Estoque"); btn(c2,"Transf.","🚚","Transferencia"); btn(c3,"Compras","🛒","Compras")
btn(c4,"Produtos","📋","Produtos"); btn(c5,"Vendas","📉","Vendas"); btn(c6,"Histórico","📜","Historico")
st.markdown("---")

tela = st.session_state['tela_atual']
df = carregar_dados()

# --- TELAS ---
if tela == "Estoque":
    st.header("📦 Contagem")
    cl, _ = st.columns([1,2]); loc = cl.selectbox("Local", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    cmap = {"Estoque Central":"Estoque_Central", "Hosp. Santo Amaro":"Estoque_SA", "Hosp. Santa Izabel":"Estoque_SI"}
    cdest = cmap[loc]
    
    with st.expander("Upload"):
        f = st.file_uploader("Planilha", key="up1")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cn = next((c for c in d.columns if "prod" in str(c).lower()), None)
                cq = next((c for c in d.columns if "qtd" in str(c).lower()), None)
                if cn and cq:
                    cnt=0
                    for i, r in d.iterrows():
                        p = str(r[cn]).strip(); q = limpar_inteiro(r[cq])
                        if p and p!='nan':
                            m = df['Produto'] == p
                            if m.any(): df.loc[m, cdest] = q
                            else:
                                n = {c:0 for c in df.columns}; n['Produto']=p; n[cdest]=q; n['Categoria']="Novo"
                                df = pd.concat([df, pd.DataFrame([n])], ignore_index=True)
                            cnt+=1
                    salvar_banco(df); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro")
    
    flt = st.text_input("Filtro:", "")
    v = df[df['Produto'].str.contains(flt, case=False, na=False)] if flt else df
    st.dataframe(v[['Codigo','Produto','Padrao',cdest]].style.format({cdest:"{:.0f}"}), use_container_width=True)

elif tela == "Produtos":
    st.header("📋 Cadastro")
    with st.expander("Importar"):
        f = st.file_uploader("Planilha", key="up2")
        cat = st.selectbox("Categoria", ["Café", "Perecíveis", "Geral"])
        if f and st.button("Salvar"):
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
                            dt = {"Produto":p, "Categoria":cat, "Fornecedor":str(r.get(cf,'Geral')), "Custo":limpar_numero(r.get(cc,0))}
                            if m.any(): 
                                for k,v in dt.items(): df.loc[m, k] = v
                            else:
                                dt.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                                df = pd.concat([df, pd.DataFrame([dt])], ignore_index=True)
                            cnt+=1
                    salvar_banco(df); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro")

    with st.expander("🔥 Reset"):
        if st.button("APAGAR TUDO"): salvar_banco(pd.DataFrame(columns=df.columns)); st.success("Zerado!"); st.rerun()

    a1,a2,a3 = st.tabs(["Café","Perecíveis","Todos"])
    def sh(c):
        d = df if c=="Todos" else df[df['Categoria']==c]
        if not d.empty:
            st.dataframe(d[['Produto','Fornecedor','Custo']], use_container_width=True)
            c1,c2 = st.columns([4,1])
            s = c1.selectbox(f"Del {c}", d['Produto'].unique(), key=f"d_{c}", index=None)
            if s and c2.button("🗑️", key=f"b_{c}"):
                salvar_banco(df[df['Produto']!=s]); st.rerun()
    with a1: sh("Café"); 
    with a2: sh("Perecíveis"); 
    with a3: sh("Todos")

elif tela == "Compras":
    st.header("🛒 Compras")
    fl = ["Todos"] + sorted([str(x) for x in df['Fornecedor'].unique() if str(x)!='nan'])
    sl = st.selectbox("Fornecedor", fl)
    
    if st.button("Sugestão"):
        d = df.copy() if sl=="Todos" else df[df['Fornecedor']==sl].copy()
        d['Meta'] = d['Min_SA'] + d['Min_SI']
        d['Atual'] = d['Estoque_Central'] + d['Estoque_SA'] + d['Estoque_SI']
        d['Qtd Compra'] = (d['Meta'] - d['Atual']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = d; st.rerun()
        
    v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df.copy() if sl=="Todos" else df[df['Fornecedor']==sl].copy())
    if 'Qtd Compra' not in v.columns: v['Qtd Compra'] = 0
    
    bs = st.text_input("Buscar", key="bs_c")
    if bs: v = v[v['Produto'].str.contains(bs, case=False, na=False)]
    
    v['Total'] = v['Qtd Compra'] * v['Custo']
    ed = st.data_editor(v[['Produto','Fornecedor','Custo','Qtd Compra','Total']], key="ed_c", column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0)}, use_container_width=True, height=400)
    
    tot = ed['Total'].sum(); st.metric("Total", f"R$ {tot:,.2f}")
    
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0].copy(); i['Total Item'] = i['Total']
        if not i.empty:
            st.session_state['pedido_pdf'] = criar_pdf_pedido(i, sl, tot)
            b = io.BytesIO(); 
            with pd.ExcelWriter(b, engine='openpyxl') as w: i.to_excel(w, index=False)
            st.session_state['pedido_xlsx'] = b.getvalue()
            registrar_log("Varios", len(i), "Compra", f"R$ {tot:.2f}"); st.rerun()
            
    if st.session_state['pedido_pdf']:
        c1.download_button("Baixar PDF", st.session_state['pedido_pdf'], "Ped.pdf", "application/pdf")
        c2.download_button("Baixar XLS", st.session_state['pedido_xlsx'], "Ped.xlsx")

elif tela == "Transferencia":
    st.header("🚚 Transferência")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        dst = st.selectbox("Para:", ["Hospital Santo Amaro", "Hospital Santa Izabel"])
        ce = "Estoque_SA" if "Amaro" in dst else "Estoque_SI"; cm = "Min_SA" if "Amaro" in dst else "Min_SI"
        
        if st.button("Sugestão"):
            d = df[['Produto','Estoque_Central',ce,cm]].copy()
            d['Env'] = (d[cm]-d[ce]).apply(lambda x: max(0, int(x)))
            st.session_state['transf_df_cache'] = d; st.rerun()
            
        v = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df[['Produto','Estoque_Central',ce,cm]].assign(Env=0)
        bs = st.text_input("Buscar", key="bs_t")
        if bs: v = v[v['Produto'].str.contains(bs, case=False, na=False)]
        
        ed = st.data_editor(v, key="ed_t", column_config={"Produto":st.column_config.TextColumn(disabled=True), "Estoque_Central":st.column_config.NumberColumn(disabled=True), "Env":st.column_config.NumberColumn(min_value=0)}, use_container_width=True, height=400)
        
        if st.button("Adicionar"):
            its = ed[ed['Env']>0]
            if not its.empty:
                ls = []
                for i,r in its.iterrows():
                    p=r['Produto']; q=int(r['Env'])
                    idx = df[df['Produto']==p].index[0]
                    df.at[idx, 'Estoque_Central'] -= q
                    df.at[idx, ce] += q
                    ls.append({"Destino":dst, "Produto":p, "Quantidade":q})
                salvar_banco(df); st.session_state['carga_acumulada'].extend(ls); st.session_state['transf_df_cache']=None; st.success("Ok!"); st.rerun()
    with c2:
        if st.session_state['carga_acumulada']:
            dc = pd.DataFrame(st.session_state['carga_acumulada'])
            st.dataframe(dc)
            if st.button("Finalizar"):
                st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                b = io.BytesIO(); 
                with pd.ExcelWriter(b, engine='openpyxl') as w: dc.to_excel(w, index=False)
                st.session_state['romaneio_xlsx'] = b.getvalue()
                st.rerun()
            if st.button("Limpar"): st.session_state['carga_acumulada']=[]; st.session_state['romaneio_pdf']=None; st.rerun()
            if st.session_state['romaneio_pdf']:
                st.download_button("PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
                st.download_button("XLS", st.session_state['romaneio_xlsx'], "Rom.xlsx")
        else: st.info("Vazio")

elif tela == "Vendas": st.info("Em breve")
elif tela == "Historico": 
    if os.path.exists(ARQUIVO_LOG): st.dataframe(pd.read_csv(ARQUIVO_LOG))
    else: st.info("Vazio")
