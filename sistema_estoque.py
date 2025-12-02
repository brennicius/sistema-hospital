import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Local 36.2", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

# --- INICIALIZAÇÃO ---
def init_state():
    keys = ['df_distribuicao_temp', 'df_compras_temp', 'romaneio_final', 'romaneio_pdf_cache', 
            'distribuicao_concluida', 'pedido_compra_final', 'selecao_exclusao', 'carga_acumulada',
            'transf_df_cache', 'transf_key_ver', 'transf_last_dest', 'compras_df_cache', 'compras_key_ver', 'last_forn',
            'pedido_pdf', 'pedido_xlsx', 'romaneio_xlsx']
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = None if 'df' in k or 'romaneio' in k or 'pedido' in k else []
            if 'concluida' in k: st.session_state[k] = False
            elif 'key' in k: st.session_state[k] = 0
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Estoque"

init_state()

# --- FUNÇÕES ---
def limpar_numero(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace('kg', '').replace('un', '').replace(' ', '')
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    else: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def limpar_inteiro(valor):
    try: return int(round(limpar_numero(valor)))
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
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    
    if not df.empty: df = df.drop_duplicates(subset=['Produto'], keep='last').reset_index(drop=True)
    return df

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): df = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
    else: df = pd.read_csv(ARQUIVO_LOG)
    pd.concat([df, pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF ---
def criar_pdf_unificado(lista_carga):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="ROMANEIO UNIFICADO", ln=True, align='C')
        pdf.set_font("Arial", size=10); pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C'); pdf.ln(10)
        df = pd.DataFrame(lista_carga)
        df_p = df.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index()
        for c in ["Hospital Santo Amaro", "Hospital Santa Izabel"]: 
            if c not in df_p.columns: df_p[c] = 0
        pdf.set_fill_color(200, 220, 255); pdf.set_font("Arial", 'B', 10)
        pdf.cell(110, 8, "Produto", 1, 0, 'C', 1); pdf.cell(40, 8, "Sto Amaro", 1, 0, 'C', 1); pdf.cell(40, 8, "Sta Izabel", 1, 1, 'C', 1)
        pdf.set_font("Arial", size=10)
        for i, r in df_p.iterrows():
            p = str(r['Produto'])[:55].encode('latin-1','replace').decode('latin-1')
            qs = str(int(r["Hospital Santo Amaro"])) if r["Hospital Santo Amaro"]>0 else "-"; qi = str(int(r["Hospital Santa Izabel"])) if r["Hospital Santa Izabel"]>0 else "-"
            pdf.cell(110, 8, p, 1, 0, 'L'); pdf.cell(40, 8, qs, 1, 0, 'C'); pdf.cell(40, 8, qi, 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e: return str(e).encode('utf-8')

def criar_pdf_pedido(dataframe, fornecedor, total):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=f"PEDIDO - {fornecedor.upper()}", ln=True, align='C')
        pdf.set_font("Arial", size=10); pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C'); pdf.ln(10)
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        pdf.cell(90, 8, "Produto", 1, 0, 'C', 1); pdf.cell(30, 8, "Padrao", 1, 0, 'C', 1); pdf.cell(20, 8, "Qtd", 1, 0, 'C', 1); pdf.cell(25, 8, "Custo", 1, 0, 'C', 1); pdf.cell(25, 8, "Total", 1, 1, 'C', 1)
        pdf.set_font("Arial", size=9)
        for i, r in dataframe.iterrows():
            p = str(r['Produto'])[:45].encode('latin-1','replace').decode('latin-1')
            e = str(r.get('Padrao','-')).encode('latin-1','replace').decode('latin-1')
            q = int(r['Qtd Compra']); c = float(r['Custo']); t = float(r['Total Item'])
            pdf.cell(90, 8, p, 1, 0, 'L'); pdf.cell(30, 8, e, 1, 0, 'C'); pdf.cell(20, 8, str(q), 1, 0, 'C'); pdf.cell(25, 8, f"{c:.2f}", 1, 0, 'R'); pdf.cell(25, 8, f"{t:.2f}", 1, 1, 'R')
        pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, txt=f"TOTAL: R$ {total:,.2f}", ln=True, align='R')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e: return str(e).encode('utf-8')

# --- MENU ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h2>", unsafe_allow_html=True)
st.markdown("---")
c1, c2, c3, c4, c5, c6 = st.columns(6)
def botao(col, txt, ico, nome_t):
    estilo = "primary" if st.session_state['tela_atual'] == nome_t else "secondary"
    if col.button(f"{ico}\n{txt}", key=nome_t, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = nome_t; st.rerun()
botao(c1, "Estoque", "📦", "Estoque"); botao(c2, "Transferir", "🚚", "Transferencia"); botao(c3, "Compras", "🛒", "Compras")
botao(c4, "Produtos", "📋", "Produtos"); botao(c5, "Vendas", "📉", "Vendas"); botao(c6, "Sugestões", "💡", "Sugestoes")
st.markdown("---")

tela = st.session_state['tela_atual']
df_db = carregar_dados()

# --- PÁGINAS ---
if tela == "Estoque":
    st.header("📦 Estoque")
    c_l, _ = st.columns([1,2]); loc = c_l.selectbox("Local", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    col_map = {"Estoque Central": "Estoque_Central", "Hosp. Santo Amaro": "Estoque_SA", "Hosp. Santa Izabel": "Estoque_SI"}
    col_dest = col_map.get(loc, "Estoque_Central")
    with st.expander("📂 Importar Contagem"):
        f = st.file_uploader("Arquivo", key="up_e")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cn = next((c for c in d.columns if "prod" in str(c).lower()), None)
                cq = next((c for c in d.columns if "qtd" in str(c).lower()), None)
                if cn and cq:
                    att=0
                    for i, r in d.iterrows():
                        p = str(r[cn]).strip(); q = limpar_inteiro(r[cq])
                        m = df_db['Produto'] == p
                        if m.any(): df_db.loc[m, col_dest] = q; att+=1
                    salvar_banco(df_db); st.success(f"{att} ok!"); st.rerun()
            except: st.error("Erro")
    flt = st.text_input("Filtrar:", "")
    v = df_db[df_db['Produto'].str.contains(flt, case=False, na=False)] if flt else df_db
    st.dataframe(v[['Codigo','Produto','Padrao',col_dest]].style.format({col_dest:"{:.0f}"}), use_container_width=True)

elif tela == "Produtos":
    st.header("📋 Cadastro")
    with st.expander("📂 Importar Mestre"):
        f = st.file_uploader("Arquivo", key="up_m")
        cat = st.selectbox("Categoria:", ["Café", "Perecíveis", "Geral"])
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cols = {c.lower():c for c in d.columns}
                def g(k): 
                    for x in k: 
                        for ky in cols: 
                            if x in ky: return cols[ky]
                    return None
                cnt = 0
                for i, r in d.iterrows():
                    p = str(r[g(['nome','prod'])]).strip()
                    if p and p!='nan':
                        dt = {"Produto":p, "Categoria":cat, "Fornecedor":str(r.get(g(['forn']),'Geral')), "Custo":limpar_numero(r.get(g(['cust']),0))}
                        m = df_db['Produto']==p
                        if m.any(): 
                            for k,v in dt.items(): df_db.loc[m, k] = v
                        else: 
                            dt.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                            df_db = pd.concat([df_db, pd.DataFrame([dt])], ignore_index=True)
                        cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro")
    st.dataframe(df_db[['Codigo','Produto','Fornecedor','Custo']], use_container_width=True)

elif tela == "Compras":
    st.header("🛒 Compras")
    l = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", l)
    if sel != st.session_state.get('last_forn'): st.session_state['compras_df_cache']=None; st.session_state['last_forn']=sel
    if st.button("🪄 Sugestão"):
        d = df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy()
        d['Meta'] = d['Min_SA'] + d['Min_SI']
        d['Total'] = d['Estoque_Central'] + d['Estoque_SA'] + d['Estoque_SI']
        d['Qtd Compra'] = (d['Meta'] - d['Total']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = d; st.rerun()
    v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy())
    if 'Qtd Compra' not in v.columns: v['Qtd Compra'] = 0
    ed = st.data_editor(v[['Produto','Fornecedor','Custo','Qtd Compra']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0, step=1)}, use_container_width=True, height=500)
    tot = (ed['Qtd Compra'] * ed['Custo']).sum(); st.metric("Total", f"R$ {tot:,.2f}")
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0].copy(); i['Total Item'] = i['Qtd Compra'] * i['Custo']
        if not i.empty:
            st.session_state['pedido_pdf'] = criar_pdf_pedido(i, sel, tot)
            b = io.BytesIO(); 
            with pd.ExcelWriter(b, engine='openpyxl') as w: i.to_excel(w, index=False)
            st.session_state['pedido_xlsx'] = b.getvalue()
            st.rerun()
    if st.session_state['pedido_pdf']:
        c1.download_button("Baixar PDF", st.session_state['pedido_pdf'], "Ped.pdf", "application/pdf")
        c2.download_button("Baixar Excel", st.session_state['pedido_xlsx'], "Ped.xlsx")

elif tela == "Transferencia":
    st.header("🚚 Transferência")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        dest = st.selectbox("Para:", ["Hospital Santo Amaro", "Hospital Santa Izabel"])
        if dest != st.session_state.get('transf_last_dest'): st.session_state['transf_df_cache']=None; st.session_state['transf_last_dest']=dest
        ce = "Estoque_SA" if "Amaro" in dest else "Estoque_SI"; cm = "Min_SA" if "Amaro" in dest else "Min_SI"
        if st.button("🪄 Sugestão"):
            d = df_db[['Produto','Estoque_Central',ce,cm]].copy()
            d['S'] = (d[cm]-d[ce]).apply(lambda x: max(0, int(x)))
            d['E'] = d[['S','Estoque_Central']].min(axis=1).astype(int)
            st.session_state['transf_df_cache'] = d; st.rerun()
        dv = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df_db[['Produto','Estoque_Central',ce,cm]].assign(E=0)
        ed = st.data_editor(dv, column_config={"Produto":st.column_config.TextColumn(disabled=True), "E":st.column_config.NumberColumn("Enviar", min_value=0, step=1)}, use_container_width=True, height=400)
        if st.button("📦 Adicionar"):
            it = ed[ed['E']>0]
            if not it.empty:
                ls = []
                for i,r in it.iterrows():
                    p=r['Produto']; q=int(r['E'])
                    idx = df_db[df_db['Produto']==p].index[0]
                    df_db.at[idx, 'Estoque_Central'] -= q
                    df_db.at[idx, ce] += q
                    ls.append({"Destino":dest, "Produto":p, "Quantidade":q})
                salvar_banco(df_db); st.session_state['carga_acumulada'].extend(ls); st.session_state['transf_df_cache']=None; st.success("Ok!"); st.rerun()
    with c2:
        if st.session_state['carga_acumulada']:
            dfc = pd.DataFrame(st.session_state['carga_acumulada'])
            st.dataframe(dfc)
            if st.button("✅ Finalizar"):
                st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                b = io.BytesIO(); 
                with pd.ExcelWriter(b, engine='openpyxl') as w: dfc.to_excel(w, index=False)
                st.session_state['romaneio_xlsx'] = b.getvalue()
                st.rerun()
            if st.button("🗑️ Limpar"): st.session_state['carga_acumulada']=[]; st.rerun()
            if st.session_state['romaneio_pdf']:
                c_d1, c_d2 = st.columns(2)
                c_d1.download_button("PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
                c_d2.download_button("Excel", st.session_state['romaneio_xlsx'], "Rom.xlsx")

elif tela == "Vendas": st.info("Em breve")
elif tela == "Sugestoes": st.info("Em breve")
