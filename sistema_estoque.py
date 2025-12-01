import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io
import math

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Gestão 36.1 (Fix Upload)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO DE ESTADO ---
def init_state():
    keys = ['df_distribuicao_temp', 'df_compras_temp', 'romaneio_final', 'romaneio_pdf_cache', 
            'distribuicao_concluida', 'pedido_compra_final', 'selecao_exclusao', 'carga_acumulada',
            'transf_df_cache', 'transf_key_ver', 'transf_last_dest', 'compras_df_cache', 'compras_key_ver', 'last_forn',
            'pedido_pdf', 'pedido_xlsx']
    for k in keys:
        if k not in st.session_state:
            if 'ver' in k or 'key' in k: st.session_state[k] = 0
            elif 'cache' in k or 'df' in k or 'pdf' in k or 'xlsx' in k or 'final' in k: st.session_state[k] = None
            elif 'carga' in k or 'selecao' in k: st.session_state[k] = []
            elif 'concluida' in k: st.session_state[k] = False
            elif 'last' in k: st.session_state[k] = ""
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Estoque"

init_state()

# --- FUNÇÕES DE LIMPEZA E DADOS ---
def limpar_numero(valor):
    """Converte para Float (Dinheiro)"""
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace('kg', '').replace('un', '').replace(' ', '')
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    else: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def limpar_inteiro(valor):
    """Converte para Inteiro (Quantidade)"""
    try:
        val = limpar_numero(valor)
        return int(round(val))
    except: return 0

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
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)
    
    # Garante tipos numéricos e reseta índice
    for col in ["Estoque_Central", "Estoque_SA", "Estoque_SI", "Min_SA", "Min_SI"]:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else: df[col] = 0
    
    if "Custo" in df.columns: df["Custo"] = pd.to_numeric(df["Custo"], errors='coerce').fillna(0.0)
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    
    if not df.empty:
        # Remove duplicatas e reseta índice para evitar erros de .at[]
        df = df.drop_duplicates(subset=['Produto'], keep='last').reset_index(drop=True)
        
    return df

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): df = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
    else: df = pd.read_csv(ARQUIVO_LOG)
    pd.concat([df, pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF GERAL ---
def criar_pdf_unificado(lista_carga):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="ROMANEIO UNIFICADO", ln=True, align='C')
        pdf.set_font("Arial", size=10); pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C'); pdf.ln(10)
        
        df = pd.DataFrame(lista_carga)
        df_p = df.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index()
        c_sa = "Hospital Santo Amaro"; c_si = "Hospital Santa Izabel"
        for c in [c_sa, c_si]: 
            if c not in df_p.columns: df_p[c] = 0
            
        pdf.set_fill_color(200, 220, 255); pdf.set_font("Arial", 'B', 10)
        pdf.cell(110, 8, "Produto", 1, 0, 'C', 1); pdf.cell(40, 8, "Sto Amaro", 1, 0, 'C', 1); pdf.cell(40, 8, "Sta Izabel", 1, 1, 'C', 1)
        pdf.set_font("Arial", size=10)
        for i, r in df_p.iterrows():
            p = str(r['Produto'])[:55].encode('latin-1','replace').decode('latin-1')
            qs = str(int(r[c_sa])) if r[c_sa]>0 else "-"; qi = str(int(r[c_si])) if r[c_si]>0 else "-"
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
        st.session_state['tela_atual'] = nome_t
        st.rerun()
botao(c1, "Estoque", "📦", "Estoque"); botao(c2, "Transferir", "🚚", "Transferencia"); botao(c3, "Compras", "🛒", "Compras")
botao(c4, "Produtos", "📋", "Produtos"); botao(c5, "Vendas", "📉", "Vendas"); botao(c6, "Sugestões", "💡", "Sugestoes")
st.markdown("---")

tela = st.session_state['tela_atual']
df_db = carregar_dados()

# =================================================================================
# 📦 ESTOQUE (CORREÇÃO UPLOAD)
# =================================================================================
if tela == "Estoque":
    st.header("📦 Atualização de Estoque (Contagem)")
    locais = {"Depósito Geral (Central)": "Estoque_Central", "Hospital Santo Amaro": "Estoque_SA", "Hospital Santa Izabel": "Estoque_SI"}
    c_loc, _ = st.columns([1,2]); loc_sel = c_loc.selectbox("Local:", list(locais.keys()))
    col_dest = locais[loc_sel]
    
    with st.expander("📂 Importar Planilha de Contagem", expanded=True):
        arq = st.file_uploader("Arquivo", type=["xlsx", "csv"], key="up_est")
        if arq:
            try:
                if arq.name.endswith('.csv'): df_t = pd.read_csv(arq, header=None)
                else: df_t = pd.read_excel(arq, header=None)
                hr = 0
                for i, r in df_t.head(20).iterrows():
                    s = r.astype(str).str.lower().tolist()
                    if any("código" in x or "produto" in x for x in s): hr = i; break
                arq.seek(0)
                if arq.name.endswith('.csv'): df_n = pd.read_csv(arq, header=hr)
                else: df_n = pd.read_excel(arq, header=hr)
                
                cols = df_n.columns.tolist()
                c1, c2, c3 = st.columns(3)
                ic = next((i for i,c in enumerate(cols) if "cod" in str(c).lower()),0)
                inm = next((i for i,c in enumerate(cols) if "nom" in str(c).lower() or "prod" in str(c).lower()),0)
                iq = next((i for i,c in enumerate(cols) if "qtd" in str(c).lower() or "sald" in str(c).lower()),0)
                
                cc = c1.selectbox("Col Código", cols, index=ic)
                cn = c2.selectbox("Col Nome", cols, index=inm)
                cq = c3.selectbox("Col Qtd", cols, index=iq)
                
                if st.button("🚀 Processar"):
                    att = 0; novos = []
                    bar = st.progress(0)
                    total = len(df_n)
                    
                    # Reset de índice para garantir acesso seguro
                    df_db = df_db.reset_index(drop=True)
                    
                    for i, r in df_n.iterrows():
                        bar.progress((i+1)/total)
                        cod = str(r[cc]).strip(); nom = str(r[cn]).strip(); qtd = limpar_inteiro(r[cq])
                        if not nom or nom=='nan': continue
                        
                        m = df_db[(df_db['Codigo']==cod)|(df_db['Codigo_Unico']==cod)]
                        if m.empty: m = df_db[df_db['Produto']==nom]
                        
                        if not m.empty:
                            idx = m.index[0] # Pega o índice seguro
                            df_db.loc[idx, col_dest] = qtd
                            att+=1
                        else:
                            n = {"Codigo": cod, "Produto": nom, "Categoria": "Novo", "Fornecedor": "Geral", "Padrao": "Un", "Custo": 0, "Min_SA":0, "Min_SI":0, "Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0}
                            n[col_dest] = qtd
                            df_db = pd.concat([df_db, pd.DataFrame([n])], ignore_index=True)
                            novos.append(nom)
                            
                    salvar_banco(df_db); bar.empty(); st.success(f"{att} Atualizados!"); 
                    if novos: st.warning(f"{len(novos)} Novos cadastrados.")
            except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    filt = st.text_input("Filtrar:", placeholder="Nome...")
    v = df_db[df_db['Produto'].str.contains(filt, case=False, na=False)] if filt else df_db
    st.dataframe(v[['Codigo', 'Produto', 'Padrao', col_dest]], use_container_width=True, hide_index=True)

# =================================================================================
# 🛒 COMPRAS
# =================================================================================
elif tela == "Compras":
    st.header("🛒 Compras")
    f_list = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", f_list)
    if sel != st.session_state.get('last_forn'): st.session_state['compras_df_cache']=None; st.session_state['last_forn']=sel
    
    if st.button("🪄 Sugestão (Meta - Total)"):
        df_c = df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy()
        df_c['Meta'] = df_c['Min_SA'] + df_c['Min_SI']
        df_c['Atual'] = df_c['Estoque_Central'] + df_c['Estoque_SA'] + df_c['Estoque_SI']
        df_c['Qtd Compra'] = (df_c['Meta'] - df_c['Atual']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = df_c; st.rerun()

    df_v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy())
    if 'Qtd Compra' not in df_v.columns: df_v['Qtd Compra'] = 0
    
    bus = st.text_input("Buscar:", "")
    if bus: df_v = df_v[df_v['Produto'].str.contains(bus, case=False, na=False)]
    
    df_v['Total'] = df_v['Qtd Compra'] * df_v['Custo']
    ed = st.data_editor(df_v[['Produto','Fornecedor','Padrao','Custo','Qtd Compra','Total']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0, step=1, format="%d"), "Custo":st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total":st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    tot = ed['Total'].sum()
    st.metric("Total", f"R$ {tot:,.2f}")
    
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0]
        if not i.empty:
            st.session_state['pedido_pdf'] = criar_pdf_pedido(i, sel, tot)
            b = io.BytesIO(); 
            with pd.ExcelWriter(b, engine='openpyxl') as w: i.to_excel(w, index=False)
            st.session_state['pedido_xlsx'] = b.getvalue()
            registrar_log("Vários", len(i), "Compra", f"R$ {tot:.2f}")
            st.rerun()
    
    if st.session_state['pedido_pdf']:
        c1.download_button("Baixar PDF", st.session_state['pedido_pdf'], "Ped.pdf", "application/pdf")
        c2.download_button("Baixar Excel", st.session_state['pedido_xlsx'], "Ped.xlsx")

# =================================================================================
# 🚚 TRANSFERÊNCIA
# =================================================================================
elif tela == "Transferencia":
    st.header("🚚 Transferência")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        with st.container(border=True):
            st.markdown("### Adicionar")
            dest = st.selectbox("Destino:", ["Hospital Santo Amaro", "Hospital Santa Izabel"])
            if dest != st.session_state.get('transf_last_dest'): st.session_state['transf_df_cache']=None; st.session_state['transf_key_ver'] = st.session_state.get('transf_key_ver',0)+1; st.session_state['transf_last_dest']=dest
            
            col_est = "Estoque_SA" if "Amaro" in dest else "Estoque_SI"
            col_min = "Min_SA" if "Amaro" in dest else "Min_SI"
            
            if st.button("🪄 Sugestão"):
                df_c = df_db[['Produto', 'Estoque_Central', col_est, col_min]].copy()
                df_c['Sug'] = (df_c[col_min] - df_c[col_est]).apply(lambda x: max(0, int(x)))
                df_c['Env'] = df_c[['Sug', 'Estoque_Central']].min(axis=1).astype(int)
                st.session_state['transf_df_cache'] = df_c
                st.session_state['transf_key_ver'] += 1; st.rerun()

            df_v = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df_db[['Produto', 'Estoque_Central', col_est, col_min]].assign(Env=0)
            bus = st.text_input("Buscar:", "")
            if bus: df_v = df_v[df_v['Produto'].str.contains(bus, case=False, na=False)]
            
            ed = st.data_editor(df_v, column_config={"Produto": st.column_config.TextColumn(disabled=True), "Estoque_Central": st.column_config.NumberColumn("Central", disabled=True), col_est: st.column_config.NumberColumn("Loja", disabled=True), col_min: st.column_config.NumberColumn("Meta", disabled=True), "Env": st.column_config.NumberColumn("Enviar", min_value=0, step=1), "Sug": None}, use_container_width=True, hide_index=True, height=400, key=f"ed_tr_{st.session_state['transf_key_ver']}")
            
            if st.button("📦 Adicionar"):
                its = ed[ed['Env']>0]
                if its.empty: st.warning("Vazio")
                else:
                    err = False; tmp = []
                    for i, r in its.iterrows():
                        p = r['Produto']; q = int(r['Env'])
                        idx = df_db[df_db['Produto']==p].index[0]
                        if q > df_db.at[idx, 'Estoque_Central']: st.error(f"Erro {p}"); err=True; break
                        df_db.at[idx, 'Estoque_Central'] -= q
                        df_db.at[idx, "Estoque_SA" if "Amaro" in dest else "Estoque_SI"] += q
                        registrar_log(p, q, "Transf", dest)
                        tmp.append({"Destino": dest, "Produto": p, "Quantidade": q})
                    if not err:
                        salvar_banco(df_db); st.session_state['carga_acumulada'].extend(tmp); st.session_state['transf_df_cache'] = None; st.session_state['transf_key_ver'] += 1; st.success("Adicionado!"); st.rerun()

    with c2:
        with st.container(border=True):
            st.markdown("### Carga")
            if st.session_state['carga_acumulada']:
                with st.expander("Remover"):
                    l = [f"{i} | {x['Produto']} -> {x['Destino']} ({x['Quantidade']})" for i, x in enumerate(st.session_state['carga_acumulada'])]
                    sel = st.multiselect("Item", l)
                    if st.button("Confirmar"):
                        idxs = [int(x.split(" | ")[0]) for x in sel]
                        for i in idxs:
                            it = st.session_state['carga_acumulada'][i]
                            idb = df_db[df_db['Produto']==it['Produto']].index[0]
                            df_db.at[idb, 'Estoque_Central'] += it['Quantidade']
                            df_db.at[idb, "Estoque_SA" if "Amaro" in it['Destino'] else "Estoque_SI"] -= it['Quantidade']
                        st.session_state['carga_acumulada'] = [v for i,v in enumerate(st.session_state['carga_acumulada']) if i not in idxs]
                        salvar_banco(df_db); st.success("Ok"); st.rerun()
                
                df_c = pd.DataFrame(st.session_state['carga_acumulada'])
                try: st.dataframe(df_c.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0), use_container_width=True)
                except: st.dataframe(df_c, use_container_width=True)
                
                c_b1, c_b2 = st.columns(2)
                if c_b1.button("✅ Finalizar"):
                    st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                    b = io.BytesIO(); 
                    with pd.ExcelWriter(b, engine='openpyxl') as w: pd.DataFrame(st.session_state['carga_acumulada']).to_excel(w, index=False)
                    st.session_state['romaneio_xlsx'] = b.getvalue()
                    st.rerun()
                if c_b2.button("🗑️ Limpar"): st.session_state['carga_acumulada'] = []; st.session_state['romaneio_pdf'] = None; st.rerun()
                
                if st.session_state['romaneio_pdf']:
                    st.success("Pronto!")
                    c_d1, c_d2 = st.columns(2)
                    c_d1.download_button("📄 PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
                    c_d2.download_button("📊 Excel", st.session_state['romaneio_xlsx'], "Rom.xlsx")
            else: st.info("Vazia")

# =================================================================================
# 📋 PRODUTOS
# =================================================================================
elif tela == "Produtos":
    st.header("📋 Cadastro")
    with st.expander("📂 Importar Mestre"):
        f = st.file_uploader("Arquivo", key="upm")
        if f and st.button("Processar"):
            try:
                df_n = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cols = df_n.columns.tolist()
                def fnd(k): 
                    for c in cols: 
                        if any(x in str(c).lower() for x in k): return c
                    return None
                cc = fnd(['código','codigo']); cn = fnd(['produto 1','nome']); cf = fnd(['fornec']); cp = fnd(['padr']); ccst = fnd(['cust']); cma = fnd(['amaro']); cmi = fnd(['izabel'])
                cnt=0
                df_db = df_db.reset_index(drop=True)
                for i, r in df_n.iterrows():
                    p = str(r[cn]).strip()
                    if not p or p=='nan': continue
                    d = {"Codigo": str(r[cc]) if cc else "", "Produto": p, "Fornecedor": str(r[cf]) if cf else "", "Padrao": str(r[cp]) if cp else "", "Custo": limpar_numero(r[ccst]) if ccst else 0, "Min_SA": limpar_inteiro(r[cma]) if cma else 0, "Min_SI": limpar_inteiro(r[cmi]) if cmi else 0}
                    m = df_db['Produto']==p
                    if m.any(): 
                        for k,v in d.items(): df_db.loc[m, k] = v
                    else: 
                        d.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0, "Categoria":"Geral"})
                        df_db = pd.concat([df_db, pd.DataFrame([d])], ignore_index=True)
                    cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro")
    
    if st.button("🗑️ ZERAR TUDO"): salvar_banco(pd.DataFrame(columns=df_db.columns)); st.success("Zerado"); st.rerun()
    st.dataframe(df_db[['Codigo','Produto','Fornecedor','Custo','Min_SA','Min_SI']].style.format({"Custo": "R$ {:.2f}"}), use_container_width=True, hide_index=True)

# --- OUTROS ---
elif tela == "Vendas": st.title("📉 Vendas"); st.info("Em breve...")
elif tela == "Sugestoes": st.title("💡 Sugestões"); st.info("Em breve...")
