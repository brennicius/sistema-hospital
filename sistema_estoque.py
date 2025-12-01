import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Gestão 38.0 (Custo Decimal)", layout="wide", initial_sidebar_state="collapsed")
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

    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Compras"

init_state()

# --- FUNÇÕES ---
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
    return df

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def limpar_numero(valor):
    # Retorna FLOAT (com decimais) para não perder centavos do custo
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace('kg', '').replace('un', '').replace(' ', '')
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    else: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): df = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
    else: df = pd.read_csv(ARQUIVO_LOG)
    pd.concat([df, pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF ROMANEIO ---
def criar_pdf_unificado(lista_carga):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="ROMANEIO DE ENTREGA UNIFICADO", ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(10)
        
        df = pd.DataFrame(lista_carga)
        df['Quantidade'] = df['Quantidade'].astype(int) # Qtd em Inteiro
        df_pivot = df.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index()
        
        col_sa = "Hospital Santo Amaro"; col_si = "Hospital Santa Izabel"
        if col_sa not in df_pivot.columns: df_pivot[col_sa] = 0
        if col_si not in df_pivot.columns: df_pivot[col_si] = 0
        
        pdf.set_fill_color(200, 220, 255); pdf.set_font("Arial", 'B', 10)
        pdf.cell(110, 10, "Produto", 1, 0, 'C', fill=True)
        pdf.cell(40, 10, "Qtd Sto Amaro", 1, 0, 'C', fill=True)
        pdf.cell(40, 10, "Qtd Sta Izabel", 1, 1, 'C', fill=True)
        
        pdf.set_font("Arial", size=10)
        for i, r in df_pivot.iterrows():
            p = str(r['Produto'])[:55].encode('latin-1','replace').decode('latin-1')
            qs = str(int(r[col_sa])) if r[col_sa]>0 else "-"
            qi = str(int(r[col_si])) if r[col_si]>0 else "-"
            pdf.cell(110, 8, p, 1, 0, 'L')
            pdf.cell(40, 8, qs, 1, 0, 'C')
            pdf.cell(40, 8, qi, 1, 1, 'C')
        pdf.ln(20)
        pdf.cell(60,10,"_"*30,0,0,'C'); pdf.cell(5,10,"",0,0); pdf.cell(60,10,"_"*30,0,0,'C'); pdf.cell(5,10,"",0,0); pdf.cell(60,10,"_"*30,0,1,'C')
        pdf.set_font("Arial", size=8)
        pdf.cell(60,5,"Central",0,0,'C'); pdf.cell(5,5,"",0,0); pdf.cell(60,5,"Sto Amaro",0,0,'C'); pdf.cell(5,5,"",0,0); pdf.cell(60,5,"Sta Izabel",0,1,'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e: return str(e).encode('utf-8')

# --- PDF PEDIDO ---
def criar_pdf_pedido(dataframe, fornecedor, total):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=f"PEDIDO DE COMPRA - {fornecedor.upper()}", ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 9)
        pdf.cell(90, 8, "Produto", 1, 0, 'C', fill=True)
        pdf.cell(30, 8, "Padrao", 1, 0, 'C', fill=True)
        pdf.cell(20, 8, "Qtd", 1, 0, 'C', fill=True)
        pdf.cell(25, 8, "Custo", 1, 0, 'C', fill=True)
        pdf.cell(25, 8, "Total", 1, 1, 'C', fill=True)
        
        pdf.set_font("Arial", size=9)
        for i, r in dataframe.iterrows():
            p = str(r['Produto'])[:45].encode('latin-1','replace').decode('latin-1')
            emb = str(r.get('Padrao','-')).encode('latin-1','replace').decode('latin-1')
            q = int(r['Qtd Compra'])
            c = float(r['Custo'])
            t = float(r['Total Item'])
            
            pdf.cell(90, 8, p, 1, 0, 'L')
            pdf.cell(30, 8, emb, 1, 0, 'C')
            pdf.cell(20, 8, str(q), 1, 0, 'C')
            pdf.cell(25, 8, f"R$ {c:.2f}", 1, 0, 'R')
            pdf.cell(25, 8, f"R$ {t:.2f}", 1, 1, 'R')
        
        pdf.ln(5); pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 10, txt=f"TOTAL GERAL: R$ {total:,.2f}", ln=True, align='R')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e: return str(e).encode('utf-8')

# --- MENU SUPERIOR ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar</h2>", unsafe_allow_html=True)
st.markdown("---")

c1, c2, c3, c4, c5, c6 = st.columns(6)
def botao(col, txt, ico, nome_t):
    estilo = "primary" if st.session_state['tela_atual'] == nome_t else "secondary"
    if col.button(f"{ico}\n{txt}", key=nome_t, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = nome_t
        st.rerun()
botao(c1, "Estoque", "📦", "Estoque")
botao(c2, "Transferir", "🚚", "Transferencia")
botao(c3, "Compras", "🛒", "Compras")
botao(c4, "Produtos", "📋", "Produtos")
botao(c5, "Vendas", "📉", "Vendas")
botao(c6, "Sugestões", "💡", "Sugestoes")
st.markdown("---")

tela = st.session_state['tela_atual']
df_db = carregar_dados()

# =================================================================================
# 🛒 COMPRAS
# =================================================================================
if tela == "Compras":
    st.header("🛒 Gestão de Compras")
    c_forn, _ = st.columns([1, 2])
    forns = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x) != 'nan'])
    sel_forn = c_forn.selectbox("Fornecedor:", forns)
    
    if sel_forn != st.session_state.get('last_forn'):
        st.session_state['compras_df_cache'] = None
        st.session_state['compras_key_ver'] = st.session_state.get('compras_key_ver', 0) + 1
        st.session_state['last_forn'] = sel_forn
        st.session_state['pedido_pdf'] = None
        st.session_state['pedido_xlsx'] = None
    
    st.divider()
    
    if st.button("🪄 Calcular Sugestão (Meta - Estoque Total)"):
        df_c = df_db.copy() if sel_forn == "Todos" else df_db[df_db['Fornecedor'] == sel_forn].copy()
        df_c['Meta'] = df_c['Min_SA'] + df_c['Min_SI']
        df_c['Atual'] = df_c['Estoque_Central'] + df_c['Estoque_SA'] + df_c['Estoque_SI']
        df_c['Qtd Compra'] = (df_c['Meta'] - df_c['Atual']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = df_c
        st.session_state['compras_key_ver'] += 1
        st.success("Calculado!"); st.rerun()

    if st.session_state['compras_df_cache'] is not None: df_v = st.session_state['compras_df_cache'].copy()
    else:
        df_v = df_db.copy() if sel_forn == "Todos" else df_db[df_db['Fornecedor'] == sel_forn].copy()
        df_v['Meta'] = df_v['Min_SA'] + df_v['Min_SI']
        df_v['Atual'] = df_v['Estoque_Central'] + df_v['Estoque_SA'] + df_v['Estoque_SI']
        df_v['Qtd Compra'] = 0

    busca = st.text_input("🔍 Buscar:", "")
    if busca: df_v = df_v[df_v['Produto'].str.contains(busca, case=False, na=False)]
    
    df_v['Custo'] = df_v['Custo'].astype(float) # Garante float
    df_v['Total'] = df_v['Qtd Compra'] * df_v['Custo']

    # CONFIGURAÇÃO DO EDITOR
    edited = st.data_editor(
        df_v[['Produto', 'Fornecedor', 'Padrao', 'Atual', 'Meta', 'Custo', 'Qtd Compra']],
        column_config={
            "Produto": st.column_config.TextColumn(disabled=True),
            "Fornecedor": st.column_config.TextColumn(disabled=True),
            "Padrao": st.column_config.TextColumn("Emb", disabled=True, width="small"),
            "Atual": st.column_config.NumberColumn(disabled=True, format="%d"),
            "Meta": st.column_config.NumberColumn(disabled=True, format="%d"),
            "Custo": st.column_config.NumberColumn("R$ Unit", disabled=True, format="%.2f"), # DECIMAL AQUI
            "Qtd Compra": st.column_config.NumberColumn("🛒 Qtd", min_value=0, step=1, format="%d") # INTEIRO AQUI
        },
        use_container_width=True, hide_index=True, height=500, key=f"ed_comp_{st.session_state['compras_key_ver']}"
    )
    
    tot_i = int(edited['Qtd Compra'].sum())
    tot_v = (edited['Qtd Compra'] * edited['Custo']).sum()
    
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("Itens", tot_i); m2.metric("Total", f"R$ {tot_v:,.2f}")
    
    c_b1, c_b2, c_b3 = st.columns(3)
    if c_b1.button("📄 Processar Pedido", type="primary"):
        itens = edited[edited['Qtd Compra'] > 0].copy()
        itens['Total Item'] = itens['Qtd Compra'] * itens['Custo']
        if itens.empty: st.warning("Vazio")
        else:
            st.session_state['pedido_pdf'] = criar_pdf_pedido(itens, sel_forn, tot_v)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer: itens.to_excel(writer, index=False, sheet_name='Pedido')
            st.session_state['pedido_xlsx'] = buf.getvalue()
            registrar_log("Vários", tot_i, "Compra", f"R$ {tot_v:.2f}")
            st.rerun()

    if st.session_state['pedido_pdf']:
        c_b2.download_button("⬇️ PDF", st.session_state['pedido_pdf'], "Pedido.pdf", "application/pdf")
        c_b3.download_button("⬇️ Excel", st.session_state['pedido_xlsx'], "Pedido.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =================================================================================
# 🚚 TRANSFERENCIA (ACUMULATIVA)
# =================================================================================
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
                try: st.dataframe(df_c.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0), use_container_width=True)
                except: st.dataframe(df_c, use_container_width=True)
                
                if st.button("✅ Finalizar"):
                    st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                    buf = io.BytesIO(); 
                    with pd.ExcelWriter(buf, engine='openpyxl') as w: pd.DataFrame(st.session_state['carga_acumulada']).to_excel(w, index=False)
                    st.session_state['romaneio_xlsx'] = buf.getvalue()
                    st.rerun()
                
                if st.session_state['romaneio_pdf']:
                    c_d1, c_d2 = st.columns(2)
                    c_d1.download_button("PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
                    c_d2.download_button("Excel", st.session_state['romaneio_xlsx'], "Rom.xlsx")
                
                if st.button("Limpar"): st.session_state['carga_acumulada'] = []; st.session_state['romaneio_pdf'] = None; st.rerun()
            else: st.info("Vazio")

# =================================================================================
# 📦 ESTOQUE
# =================================================================================
elif tela == "Estoque":
    st.header("📦 Estoque (Contagem)")
    c_l, _ = st.columns([1,2]); loc = c_l.selectbox("Local:", ["Depósito Geral (Central)", "Hospital Santo Amaro", "Hospital Santa Izabel"])
    col_d = {"Depósito Geral (Central)": "Estoque_Central", "Hospital Santo Amaro": "Estoque_SA", "Hospital Santa Izabel": "Estoque_SI"}[loc]
    
    with st.expander("📂 Upload Contagem"):
        f = st.file_uploader("Arquivo", key="upe")
        if f:
            try:
                if f.name.endswith('.csv'): dt = pd.read_csv(f, header=None)
                else: dt = pd.read_excel(f, header=None)
                hr = 0
                for i, r in dt.head(20).iterrows():
                    if any("cod" in str(x).lower() or "prod" in str(x).lower() for x in r.values): hr = i; break
                f.seek(0)
                if f.name.endswith('.csv'): dn = pd.read_csv(f, header=hr)
                else: dn = pd.read_excel(f, header=hr)
                
                cols = dn.columns.tolist()
                c1, c2, c3 = st.columns(3)
                ic = next((i for i,c in enumerate(cols) if "cod" in str(c).lower()), 0)
                inm = next((i for i,c in enumerate(cols) if "nom" in str(c).lower() or "prod" in str(c).lower()), 0)
                iq = next((i for i,c in enumerate(cols) if "qtd" in str(c).lower() or "sald" in str(c).lower()), 0)
                
                cc = c1.selectbox("Cod", cols, index=ic)
                cn = c2.selectbox("Nome", cols, index=inm)
                cq = c3.selectbox("Qtd", cols, index=iq)
                
                if st.button("Processar"):
                    att = 0
                    for i, r in dn.iterrows():
                        c = str(r[cc]).strip(); n = str(r[cn]).strip(); q = limpar_numero(r[cq])
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

# =================================================================================
# 📋 PRODUTOS
# =================================================================================
elif tela == "Produtos":
    st.header("📋 Cadastro")
    with st.expander("📂 Importar Mestre"):
        f = st.file_uploader("Arquivo", key="upm")
        if f and st.button("Processar"):
            try:
                if f.name.endswith('.csv'): dn = pd.read_csv(f)
                else: dn = pd.read_excel(f)
                cols = dn.columns
                def fd(k): 
                    for c in cols: 
                        if any(x in c.lower() for x in k): return c
                    return None
                cc = fd(['cod']); cn = fd(['nom','prod']); cf = fd(['forn']); cp = fd(['padr']); cst = fd(['cust']); cma = fd(['amar']); cmi = fd(['izab'])
                
                cnt = 0
                for i, r in dn.iterrows():
                    p = str(r[cn]).strip()
                    if not p or p=='nan': continue
                    d = {"Codigo": str(r[cc]) if cc else "", "Produto": p, "Fornecedor": str(r[cf]) if cf else "", "Padrao": str(r[cp]) if cp else "", "Custo": limpar_numero(r[cst]) if cst else 0, "Min_SA": limpar_numero(r[cma]) if cma else 0, "Min_SI": limpar_numero(r[cmi]) if cmi else 0}
                    m = df_db['Produto']==p
                    if m.any(): 
                        for k,v in d.items(): df_db.loc[m, k] = v
                    else: 
                        d.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0, "Categoria":"Geral"})
                        df_db = pd.concat([df_db, pd.DataFrame([d])], ignore_index=True)
                    cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro")
    
    st.divider()
    if st.button("🗑️ ZERAR TUDO"): salvar_banco(pd.DataFrame(columns=df_db.columns)); st.success("Zerado"); st.rerun()
    st.dataframe(df_db[['Codigo','Produto','Fornecedor','Custo','Min_SA','Min_SI']].style.format({"Custo": "R$ {:.2f}"}), use_container_width=True, hide_index=True)

# --- OUTROS ---
elif tela == "Vendas": st.title("📉 Vendas"); st.info("Em breve...")
elif tela == "Sugestoes": st.title("💡 Sugestões"); st.info("Em breve...")
