import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io
import math

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema 37.2 (Fix Import)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO ---
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
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Produtos"

init_state()

# --- FUNÇÕES DE LIMPEZA (MELHORADAS) ---
def limpar_numero(valor):
    """Para dinheiro (mantém decimais)"""
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace('kg', '').replace('un', '').replace(' ', '')
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    else: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def limpar_inteiro(valor):
    """Para quantidade e mínimos (arredonda e tira decimais)"""
    val = limpar_numero(valor)
    try:
        return int(round(val)) # Arredonda matematicamente (4.8 -> 5)
    except:
        return 0

def limpar_codigo(valor):
    """Limpa o código removendo .0 se vier do Excel"""
    if pd.isna(valor): return ""
    s = str(valor).strip()
    if s.endswith('.0'): return s[:-2]
    return s

# --- BANCO DE DADOS ---
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
    
    # Garante tipos
    for col in ["Estoque_Central", "Estoque_SA", "Estoque_SI", "Min_SA", "Min_SI"]:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else: df[col] = 0
    
    if "Custo" in df.columns: df["Custo"] = pd.to_numeric(df["Custo"], errors='coerce').fillna(0.0)
            
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    if "Codigo" not in df.columns: df["Codigo"] = ""
    df["Codigo"] = df["Codigo"].fillna("").astype(str)

    if not df.empty:
        # Remove duplicatas mantendo o último atualizado
        df = df.drop_duplicates(subset=['Produto'], keep='last')
        
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
        pdf.cell(190, 10, txt="ROMANEIO DE ENTREGA", ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C'); pdf.ln(10)
        
        df = pd.DataFrame(lista_carga)
        df_pivot = df.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index()
        c_sa = "Hospital Santo Amaro"; c_si = "Hospital Santa Izabel"
        for c in [c_sa, c_si]: 
            if c not in df_pivot.columns: df_pivot[c] = 0
            
        pdf.set_fill_color(200, 220, 255); pdf.set_font("Arial", 'B', 10)
        pdf.cell(110, 10, "Produto", 1, 0, 'C', 1); pdf.cell(40, 10, "Sto Amaro", 1, 0, 'C', 1); pdf.cell(40, 10, "Sta Izabel", 1, 1, 'C', 1)
        pdf.set_font("Arial", size=10)
        for i, r in df_pivot.iterrows():
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
            pdf.cell(90, 8, p, 1, 0, 'L'); pdf.cell(30, 8, e, 1, 0, 'C'); pdf.cell(20, 8, str(int(r['Qtd Compra'])), 1, 0, 'C'); pdf.cell(25, 8, f"{r['Custo']:.2f}", 1, 0, 'R'); pdf.cell(25, 8, f"{r['Total Item']:.2f}", 1, 1, 'R')
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

# --- TELA PRODUTOS (CORREÇÃO IMPORTAÇÃO) ---
if tela == "Produtos":
    st.header("📋 Cadastro Geral")
    
    # UPLOAD MESTRE CORRIGIDO
    with st.expander("📂 Importar Cadastro Mestre (Códigos + Mínimos)", expanded=True):
        c_upl, c_cat = st.columns([2, 1])
        arq = c_upl.file_uploader("Arquivo", type=["xlsx", "csv"], key="up_mst")
        cat = c_cat.selectbox("Categoria:", ["Café", "Perecíveis", "Geral"])
        
        if arq and c_upl.button("Processar Cadastro"):
            try:
                if arq.name.endswith('.csv'): df_n = pd.read_csv(arq)
                else: df_n = pd.read_excel(arq)
                
                cols = df_n.columns.tolist()
                
                # Busca colunas mais robusta
                def fnd(k): 
                    for c in cols: 
                        if any(x in str(c).lower() for x in k): return c
                    return None
                
                cc = fnd(['código', 'codigo'])
                cn = fnd(['produto 1', 'nome produto', 'descrição'])
                cf = fnd(['fornec'])
                cp = fnd(['padr', 'emb'])
                ccst = fnd(['cust', 'unitário'])
                cma = fnd(['amaro', 'st amaro', 'sa'])
                cmi = fnd(['izabel', 'st izabel', 'si'])
                
                if not cn: st.error("Erro: Coluna 'Nome do Produto' não encontrada.")
                else:
                    cnt = 0
                    for i, r in df_n.iterrows():
                        p = str(r[cn]).strip()
                        if not p or p=='nan': continue
                        
                        # TRATAMENTO ESPECIAL PARA CÓDIGO
                        cod_bruto = r[cc] if cc else ""
                        cod_limpo = limpar_codigo(cod_bruto) # Usa a função nova
                        
                        d = {
                            "Codigo": cod_limpo,
                            "Produto": p,
                            "Categoria": cat,
                            "Fornecedor": str(r[cf]) if cf else "Geral",
                            "Padrao": str(r[cp]) if cp else "",
                            "Custo": limpar_numero(r[ccst]) if ccst else 0.0,
                            "Min_SA": limpar_inteiro(r[cma]) if cma else 0, # ARREDONDA
                            "Min_SI": limpar_inteiro(r[cmi]) if cmi else 0  # ARREDONDA
                        }
                        
                        # Atualiza ou Cria
                        mask = (df_db['Produto'] == p)
                        if mask.any():
                            for k, v in d.items(): df_db.loc[mask, k] = v
                        else:
                            d.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                            df_db = pd.concat([df_db, pd.DataFrame([d])], ignore_index=True)
                        cnt += 1
                        
                    salvar_banco(df_db)
                    st.success(f"✅ {cnt} produtos processados com sucesso!")
                    st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    
    # Botão Zona Perigo
    with st.expander("🔥 Apagar Tudo"):
        if st.button("🗑️ ZERAR BANCO"):
            colunas_limpas = ["Codigo", "Codigo_Unico", "Produto", "Produto_Alt", "Categoria", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI", "Estoque_Central", "Estoque_SA", "Estoque_SI"]
            salvar_banco(pd.DataFrame(columns=colunas_limpas)); st.success("Zerado!"); st.rerun()

    # Tabela Visualização
    a1, a2, a3 = st.tabs(["☕ Café", "🍎 Perecíveis", "📋 Todos"])
    def show(c):
        d = df_db if c=="Todos" else df_db[df_db['Categoria']==c]
        if not d.empty:
            st.dataframe(
                d[['Codigo', 'Produto', 'Fornecedor', 'Padrao', 'Custo', 'Min_SA', 'Min_SI']].style.format({
                    "Custo": "R$ {:.2f}",
                    "Min_SA": "{:.0f}",
                    "Min_SI": "{:.0f}"
                }), 
                use_container_width=True, 
                hide_index=True
            )
            
            cd1, cd2 = st.columns([4, 1])
            sel = cd1.selectbox(f"Excluir ({c})", d['Produto'].unique(), key=f"d_{c}", index=None)
            if sel and cd2.button("🗑️", key=f"b_{c}"):
                salvar_banco(df_db[df_db['Produto']!=sel]); st.rerun()
        else: st.info("Vazio")
        
    with a1: show("Café")
    with a2: show("Perecíveis")
    with a3: show("Todos")

# --- TELA TRANSFERENCIA ---
elif tela == "Transferencia":
    st.header("🚚 Transferência")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        with st.container(border=True):
            st.markdown("### Adicionar")
            dest = st.selectbox("Destino:", ["Hospital Santo Amaro", "Hospital Santa Izabel"])
            if dest != st.session_state.get('transf_last_dest'):
                st.session_state['transf_df_cache'] = None
                st.session_state['transf_key_ver'] = st.session_state.get('transf_key_ver',0) + 1
                st.session_state['transf_last_dest'] = dest
            
            col_est = "Estoque_SA" if "Amaro" in dest else "Estoque_SI"
            col_min = "Min_SA" if "Amaro" in dest else "Min_SI"
            
            if st.button("🪄 Preencher Sugestão"):
                df_c = df_db[['Produto', 'Estoque_Central', col_est, col_min]].copy()
                df_c['Sug'] = (df_c[col_min] - df_c[col_est]).apply(lambda x: max(0, int(x)))
                df_c['Env'] = df_c[['Sug', 'Estoque_Central']].min(axis=1).astype(int)
                st.session_state['transf_df_cache'] = df_c
                st.session_state['transf_key_ver'] += 1; st.rerun()

            df_v = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df_db[['Produto', 'Estoque_Central', col_est, col_min]].assign(Env=0)
            
            bus = st.text_input("Buscar:", "")
            if bus: df_v = df_v[df_v['Produto'].str.contains(bus, case=False, na=False)]
            
            ed = st.data_editor(df_v, column_config={"Produto": st.column_config.TextColumn(disabled=True), "Estoque_Central": st.column_config.NumberColumn("Central", disabled=True, format="%d"), col_est: st.column_config.NumberColumn("Loja", disabled=True, format="%d"), col_min: st.column_config.NumberColumn("Meta", disabled=True, format="%d"), "Env": st.column_config.NumberColumn("Enviar", min_value=0, step=1, format="%d"), "Sug": None}, use_container_width=True, hide_index=True, height=400, key=f"ed_tr_{st.session_state['transf_key_ver']}")
            
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
                    if st.button("Remover"):
                        idxs = [int(x.split(" | ")[0]) for x in sel]
                        for i in idxs:
                            it = st.session_state['carga_acumulada'][i]
                            idb = df_db[df_db['Produto']==it['Produto']].index[0]
                            df_db.at[idb, 'Estoque_Central'] += it['Quantidade']
                            df_db.at[idb, "Estoque_SA" if "Amaro" in it['Destino'] else "Estoque_SI"] -= it['Quantidade']
                        st.session_state['carga_acumulada'] = [v for i,v in enumerate(st.session_state['carga_acumulada']) if i not in idxs]
                        salvar_banco(df_db); st.success("Ok"); st.rerun()
                
                df_c = pd.DataFrame(st.session_state['carga_acumulada'])
                try: st.dataframe(df_c.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index(), use_container_width=True)
                except: st.dataframe(df_c, use_container_width=True)
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("✅ Finalizar"):
                    st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                    buf = io.BytesIO(); 
                    with pd.ExcelWriter(buf, engine='openpyxl') as w: pd.DataFrame(st.session_state['carga_acumulada']).to_excel(w, index=False)
                    st.session_state['romaneio_xlsx'] = buf.getvalue()
                    st.rerun()
                
                if c_btn2.button("🗑️ Limpar"): st.session_state['carga_acumulada'] = []; st.session_state['romaneio_pdf'] = None; st.rerun()
                if st.session_state['romaneio_pdf']:
                    c_d1, c_d2 = st.columns(2)
                    c_d1.download_button("PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
                    c_d2.download_button("Excel", st.session_state['romaneio_xlsx'], "Rom.xlsx")
            else: st.info("Vazio")

# --- OUTRAS TELAS ---
elif tela == "Estoque":
    st.header("📦 Estoque")
    c_l, _ = st.columns([1,2]); loc = c_l.selectbox("Local:", ["Depósito Geral (Central)", "Hospital Santo Amaro", "Hospital Santa Izabel"])
    col_d = {"Depósito Geral (Central)": "Estoque_Central", "Hospital Santo Amaro": "Estoque_SA", "Hospital Santa Izabel": "Estoque_SI"}[loc]
    with st.expander("📂 Upload Contagem"):
        f = st.file_uploader("Arquivo", key="upe")
        if f and st.button("Processar"):
            try:
                df_n = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                cols = df_n.columns.tolist()
                ic = next((i for i,c in enumerate(cols) if "cod" in str(c).lower()),0)
                inm = next((i for i,c in enumerate(cols) if "nom" in str(c).lower() or "prod" in str(c).lower()),0)
                iq = next((i for i,c in enumerate(cols) if "qtd" in str(c).lower() or "sald" in str(c).lower()),0)
                cc = cols[ic]; cn = cols[inm]; cq = cols[iq]
                att = 0
                for i, r in df_n.iterrows():
                    c = str(r[cc]).strip(); n = str(r[cn]).strip(); q = limpar_inteiro(r[cq])
                    if not n or n=='nan': continue
                    m = df_db[(df_db['Codigo']==c)|(df_db['Codigo_Unico']==c)]
                    if m.empty: m = df_db[df_db['Produto']==n]
                    if not m.empty: df_db.at[m.index[0], col_d] = q; att+=1
                    else:
                        nw = {"Codigo":c, "Produto":n, "Categoria":"Novo", "Fornecedor":"Geral", "Padrao":"Un", "Custo":0, "Min_SA":0, "Min_SI":0, "Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0}
                        nw[col_d] = q; df_db = pd.concat([df_db, pd.DataFrame([nw])], ignore_index=True)
                salvar_banco(df_db); st.success(f"{att} ok!"); st.rerun()
            except: st.error("Erro")
    flt = st.text_input("Filtro:", "")
    v = df_db[df_db['Produto'].str.contains(flt, case=False, na=False)] if flt else df_db
    st.dataframe(v[['Codigo','Produto','Padrao',col_d]].style.format({col_d: "{:.0f}"}), use_container_width=True, hide_index=True)

elif tela == "Compras":
    st.header("🛒 Compras")
    f_list = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", f_list)
    if sel != st.session_state.get('last_forn'): st.session_state['compras_df_cache']=None; st.session_state['last_forn']=sel
    
    if st.button("🪄 Sugestão"):
        df_c = df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy()
        df_c['Meta'] = df_c['Min_SA'] + df_c['Min_SI']
        df_c['Atual'] = df_c['Estoque_Central'] + df_c['Estoque_SA'] + df_c['Estoque_SI']
        df_c['Qtd Compra'] = (df_c['Meta'] - df_c['Atual']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = df_c; st.rerun()

    df_v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy())
    if 'Qtd Compra' not in df_v.columns: df_v['Qtd Compra'] = 0
    
    bus = st.text_input("Buscar", "")
    if bus: df_v = df_v[df_v['Produto'].str.contains(bus, case=False, na=False)]
    
    df_v['Total'] = df_v['Qtd Compra'] * df_v['Custo']
    ed = st.data_editor(df_v[['Produto','Fornecedor','Padrao','Custo','Qtd Compra','Total']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0, step=1, format="%d"), "Custo":st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total":st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    tot = ed['Total'].sum()
    st.metric("Total", f"R$ {tot:,.2f}")
    
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0]
        if not i.empty:
            pdf = criar_pdf_pedido(i, sel, tot)
            st.download_button("Baixar", pdf, "Ped.pdf", "application/pdf")
            registrar_log("Vários", len(i), "Compra", f"R$ {tot:.2f}")
    if c2.button("📊 Excel"):
        i = ed[ed['Qtd Compra']>0]
        if not i.empty:
            b = io.BytesIO(); 
            with pd.ExcelWriter(b, engine='openpyxl') as w: i.to_excel(w, index=False)
            st.download_button("Baixar", b.getvalue(), "Ped.xlsx")

elif tela == "Vendas": st.title("📉 Vendas"); st.info("Em breve")
elif tela == "Sugestoes": st.title("💡 Sugestões"); st.info("Em breve")
