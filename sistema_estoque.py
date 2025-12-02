import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io
import math

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Gestão 36.2 (Ajustado)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

# --- INICIALIZAÇÃO DE ESTADO ---
def init_state():
    keys_defaults = {
        'romaneio_pdf': None, 'romaneio_xlsx': None, 'pedido_pdf': None, 'pedido_xlsx': None,
        'tela_atual': "Produtos", 'selecao_exclusao': [], 'carga_acumulada': [],
        'transf_key_ver': 0, 'transf_last_dest': "", 'transf_df_cache': None,
        'compras_df_cache': None, 'compras_key_ver': 0, 'last_forn': "Todos"
    }
    for key, default_val in keys_defaults.items():
        if key not in st.session_state: st.session_state[key] = default_val

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
    """Arredonda para inteiro (Ex: 4.8 -> 5)"""
    try: return int(round(limpar_numero(valor)))
    except: return 0

def limpar_codigo(valor):
    """Remove .0 de códigos numéricos"""
    if pd.isna(valor): return ""
    s = str(valor).strip()
    if s.endswith('.0'): return s[:-2]
    return s

@st.cache_data
def carregar_dados():
    colunas = ["Codigo", "Codigo_Unico", "Produto", "Produto_Alt", "Categoria", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI", "Estoque_Central", "Estoque_SA", "Estoque_SI"]
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=colunas)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)
    
    # Garante Tipagem
    for c in ["Estoque_Central", "Estoque_SA", "Estoque_SI", "Min_SA", "Min_SI"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    if "Custo" in df.columns: df["Custo"] = pd.to_numeric(df["Custo"], errors='coerce').fillna(0.0)
    if "Codigo" not in df.columns: df["Codigo"] = ""
    df["Codigo"] = df["Codigo"].astype(str).apply(limpar_codigo)
    
    return df

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): df = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
    else: df = pd.read_csv(ARQUIVO_LOG)
    pd.concat([df, pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF FUNÇÕES ---
def criar_pdf_unificado(lista_carga):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="ROMANEIO UNIFICADO", ln=True, align='C')
        pdf.set_font("Arial", size=10); pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C'); pdf.ln(10)
        df = pd.DataFrame(lista_carga)
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
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h2>", unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
def btn(c, t, i, k):
    if c.button(f"{i}\n{t}", key=k, use_container_width=True, type="primary" if st.session_state['tela_atual']==k else "secondary"):
        st.session_state['tela_atual'] = k; st.rerun()
btn(c1,"Estoque","📦","Estoque"); btn(c2,"Transf.","🚚","Transferencia"); btn(c3,"Compras","🛒","Compras")
btn(c4,"Produtos","📋","Produtos"); btn(c5,"Vendas","📉","Vendas"); btn(c6,"Histórico","📜","Historico")
st.markdown("---")

tela = st.session_state['tela_atual']
df_db = carregar_dados()

# --- TELA PRODUTOS (COM AJUSTE PARA SUA PLANILHA) ---
if tela == "Produtos":
    st.header("📋 Cadastro Geral")
    with st.expander("📂 Importar Cadastro Mestre"):
        c_upl, c_cat = st.columns([2, 1])
        arq = c_upl.file_uploader("Arquivo", type=["xlsx", "csv"], key="up_mst")
        cat = c_cat.selectbox("Categoria:", ["Café", "Perecíveis", "Geral"])
        if arq and c_upl.button("Processar"):
            try:
                if arq.name.endswith('.csv'): df_n = pd.read_csv(arq)
                else: df_n = pd.read_excel(arq)
                
                cols = df_n.columns
                def fnd(k): 
                    for c in cols: 
                        if any(x in str(c).lower() for x in k): return c
                    return None
                
                # Mapeamento ajustado para sua planilha
                cc = fnd(['código','codigo']) # Coluna A
                cn = fnd(['produto 1','nome produto', 'descrição']) # Coluna C
                cf = fnd(['fornec'])
                cp = fnd(['padr', 'emb'])
                ccst = fnd(['cust', 'unit'])
                cma = fnd(['amaro', 'sa'])
                cmi = fnd(['izabel', 'si'])
                
                cnt=0
                # Atualiza DataFrame na memória
                for i, r in df_n.iterrows():
                    p = str(r[cn]).strip()
                    if not p or p=='nan': continue
                    
                    # Valores limpos
                    v_cod = limpar_codigo(r[cc]) if cc else ""
                    v_forn = str(r[cf]) if cf else "Geral"
                    v_padr = str(r[cp]) if cp else ""
                    v_cust = limpar_numero(r[ccst]) if ccst else 0.0
                    v_msa = limpar_inteiro(r[cma]) if cma else 0
                    v_msi = limpar_inteiro(r[cmi]) if cmi else 0

                    d = {
                        "Codigo": v_cod, "Produto": p, "Categoria": cat,
                        "Fornecedor": v_forn, "Padrao": v_padr, "Custo": v_cust,
                        "Min_SA": v_msa, "Min_SI": v_msi
                    }
                    
                    m = df_db['Produto'] == p
                    if m.any():
                        for k,v in d.items(): df_db.loc[m, k] = v
                    else:
                        d.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                        df_db = pd.concat([df_db, pd.DataFrame([d])], ignore_index=True)
                    cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} processados!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
            
    st.divider()
    a1, a2, a3 = st.tabs(["☕ Café", "🍎 Perecíveis", "📋 Todos"])
    def show(c):
        d = df_db if c=="Todos" else df_db[df_db['Categoria']==c]
        if not d.empty:
            # Mostra colunas importantes (Código e Mínimos inclusos)
            st.dataframe(d[['Codigo','Produto','Fornecedor','Padrao','Custo', 'Min_SA', 'Min_SI']].style.format({"Custo": "R$ {:.2f}"}), use_container_width=True, hide_index=True)
            cd1, cd2 = st.columns([4,1])
            sel = cd1.selectbox(f"Excluir ({c})", d['Produto'].unique(), key=f"d_{c}", index=None)
            if sel and cd2.button("🗑️", key=f"b_{c}"):
                salvar_banco(df_db[df_db['Produto']!=sel]); st.rerun()
        else: st.info("Vazio")
    with a1: show("Café"); 
    with a2: show("Perecíveis"); 
    with a3: show("Todos")

# --- ESTOQUE ---
elif tela == "Estoque":
    st.header("📦 Estoque (Contagem)")
    cl, _ = st.columns([1,2]); loc = cl.selectbox("Local", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    cmap = {"Estoque Central":"Estoque_Central", "Hosp. Santo Amaro":"Estoque_SA", "Hosp. Santa Izabel":"Estoque_SI"}
    cdest = cmap[loc]
    
    with st.expander("📂 Importar Contagem"):
        f = st.file_uploader("Arquivo", key="up1")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                # Auto-Header 
                h=0
                for i,r in d.head(20).iterrows():
                    if any("prod" in str(x).lower() for x in r.values): h=i; break
                f.seek(0)
                d = pd.read_csv(f, header=h) if f.name.endswith('.csv') else pd.read_excel(f, header=h)
                
                cols = d.columns.tolist()
                ic = next((i for i,c in enumerate(cols) if "cod" in str(c).lower()),0)
                inm = next((i for i,c in enumerate(cols) if "nom" in str(c).lower() or "prod" in str(c).lower()),0)
                iq = next((i for i,c in enumerate(cols) if "qtd" in str(c).lower() or "sald" in str(c).lower()),0)
                
                c1, c2, c3 = st.columns(3)
                cc = c1.selectbox("Cod", cols, index=ic)
                cn = c2.selectbox("Nome", cols, index=inm)
                cq = c3.selectbox("Qtd", cols, index=iq)
                
                cnt=0
                for i, r in d.iterrows():
                    cod = str(r[cc]).strip()
                    p = str(r[cn]).strip()
                    q = limpar_inteiro(r[cq])
                    if p and p!='nan':
                        # Busca por Código OU Nome
                        m = df_db[(df_db['Codigo']==cod) | (df_db['Produto']==p)]
                        if not m.empty: 
                            df_db.loc[m.index, cdest] = q
                            cnt+=1
                        else:
                            # Auto-Cadastro se não achar
                            novo = {c:0 for c in df_db.columns}
                            novo.update({"Codigo":cod, "Produto":p, cdest:q, "Categoria":"Novo", "Fornecedor":"Geral"})
                            df_db = pd.concat([df_db, pd.DataFrame([novo])], ignore_index=True)
                            cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} ok!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
            
    st.divider()
    st.dataframe(df_db[['Codigo','Produto','Padrao',cdest]].style.format({cdest:"{:.0f}"}), use_container_width=True)

# --- TRANSFERÊNCIA ---
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
        bs = st.text_input("Buscar:", "")
        if bs: dv = dv[dv['Produto'].str.contains(bs, case=False, na=False)]
        
        ed = st.data_editor(dv, column_config={"Produto":st.column_config.TextColumn(disabled=True), "Estoque_Central":st.column_config.NumberColumn(disabled=True), "E":st.column_config.NumberColumn("Enviar", min_value=0, step=1), "S":None}, use_container_width=True, height=400)
        
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
            try: st.dataframe(dfc.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0), use_container_width=True)
            except: st.dataframe(dfc)
            c_b1, c_b2 = st.columns(2)
            if c_b1.button("✅ Finalizar"):
                st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                b = io.BytesIO(); 
                with pd.ExcelWriter(b, engine='openpyxl') as w: pd.DataFrame(st.session_state['carga_acumulada']).to_excel(w, index=False)
                st.session_state['romaneio_xlsx'] = b.getvalue()
                st.rerun()
            if c_b2.button("🗑️ Limpar"): st.session_state['carga_acumulada']=[]; st.session_state['romaneio_pdf']=None; st.rerun()
            if st.session_state['romaneio_pdf']:
                st.download_button("PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
                st.download_button("XLS", st.session_state['romaneio_xlsx'], "Rom.xlsx")
        else: st.info("Vazio")

# --- COMPRAS ---
elif tela == "Compras":
    st.header("🛒 Compras")
    l = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", l)
    
    if st.button("🪄 Sugestão"):
        d = df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy()
        d['Meta'] = d['Min_SA'] + d['Min_SI']
        d['Total'] = d['Estoque_Central'] + d['Estoque_SA'] + d['Estoque_SI']
        d['Compra'] = (d['Meta'] - d['Total']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = d; st.rerun()
        
    v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy())
    if 'Qtd Compra' not in v.columns: v['Qtd Compra'] = 0
    
    bus = st.text_input("Buscar:", key="bs_c")
    if bus: v = v[v['Produto'].str.contains(bus, case=False, na=False)]
    
    v['Total'] = v['Qtd Compra'] * v['Custo']
    ed = st.data_editor(v[['Produto','Fornecedor','Custo','Qtd Compra','Total']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0, step=1)}, use_container_width=True, height=500)
    
    tot = ed['Total'].sum(); st.metric("Total", f"R$ {tot:,.2f}")
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0].copy(); i['Total Item'] = i['Total']
        if not i.empty:
            st.session_state['pedido_pdf'] = criar_pdf_pedido(i, sel, tot)
            b = io.BytesIO(); 
            with pd.ExcelWriter(b, engine='openpyxl') as w: i.to_excel(w, index=False)
            st.session_state['pedido_xlsx'] = b.getvalue()
            st.rerun()
    if st.session_state['pedido_pdf']:
        c1.download_button("PDF", st.session_state['pedido_pdf'], "Ped.pdf", "application/pdf")
        c2.download_button("Excel", st.session_state['pedido_xlsx'], "Ped.xlsx")

# --- DEMAIS TELAS ---
elif tela == "Vendas": st.info("Em breve")
elif tela == "Sugestoes": st.info("Em breve")
