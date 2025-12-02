import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema 41.0 (Mapeamento Manual)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO ---
def init_state():
    keys = ['romaneio_pdf', 'romaneio_xlsx', 'pedido_pdf', 'pedido_xlsx', 
            'tela_atual', 'selecao_exclusao', 'carga_acumulada',
            'transf_df_cache', 'transf_key_ver', 'transf_last_dest', 
            'compras_df_cache', 'compras_key_ver', 'last_forn']
    for k in keys:
        if k not in st.session_state:
            if 'ver' in k or 'key' in k: st.session_state[k] = 0
            elif 'cache' in k or 'df' in k or 'pdf' in k or 'xlsx' in k: st.session_state[k] = None
            elif 'carga' in k or 'selecao' in k: st.session_state[k] = []
            elif 'last' in k: st.session_state[k] = ""
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Produtos"

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
        else: df[c] = 0
    if "Custo" in df.columns: df["Custo"] = pd.to_numeric(df["Custo"], errors='coerce').fillna(0.0)
    
    text_cols = ["Codigo", "Produto", "Fornecedor", "Padrao", "Categoria"]
    for c in text_cols:
        if c not in df.columns: df[c] = ""
        df[c] = df[c].fillna("").astype(str)
        if c == "Fornecedor": df[c] = df[c].replace("", "Geral")
        if c == "Categoria": df[c] = df[c].replace("", "Geral")

    return df.drop_duplicates(subset=['Produto'], keep='last').reset_index(drop=True)

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def registrar_log(prod, qtd, tipo, dest, usu="Sistema"):
    n = {"Data": datetime.now().strftime("%d/%m %H:%M"), "Produto": prod, "Quantidade": qtd, "Tipo": tipo, "Detalhe": dest, "Usuario": usu}
    if not os.path.exists(ARQUIVO_LOG): pd.DataFrame(columns=n.keys()).to_csv(ARQUIVO_LOG, index=False)
    pd.concat([pd.read_csv(ARQUIVO_LOG), pd.DataFrame([n])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF ---
def criar_pdf_generico(dataframe, titulo_doc, colunas_largura=None):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=titulo_doc, ln=True, align='C')
        pdf.set_font("Arial", size=10); pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C'); pdf.ln(10)
        cols = dataframe.columns.tolist()
        if not colunas_largura:
            l = 190 // len(cols); larguras = [l] * len(cols)
            if "Produto" in cols: larguras[cols.index("Produto")] = 70
        else: larguras = colunas_largura
        pdf.set_font("Arial", 'B', 8)
        for i, c in enumerate(cols): 
            txt = str(c).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(larguras[i], 10, txt[:20], 1, 0, 'C')
        pdf.ln()
        pdf.set_font("Arial", size=8)
        for i, r in dataframe.iterrows():
            for j, c in enumerate(cols):
                txt = str(r[c]).encode('latin-1', 'replace').decode('latin-1')
                al = 'L' if j==0 else 'C'
                pdf.cell(larguras[j], 10, txt[:45], 1, 0, al)
            pdf.ln()
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return None

# --- MENU ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema Integrado 41.0</h2>", unsafe_allow_html=True)
st.markdown("---")
c1, c2, c3, c4, c5, c6 = st.columns(6)
def botao(c, t, i, k):
    if c.button(f"{i}\n{t}", key=k, use_container_width=True, type="primary" if st.session_state['tela_atual']==k else "secondary"):
        st.session_state['tela_atual'] = k; st.rerun()
botao(c1,"Estoque","📦","Estoque"); botao(c2,"Transf.","🚚","Transferencia"); botao(c3,"Compras","🛒","Compras")
botao(c4,"Produtos","📋","Produtos"); botao(c5,"Vendas","📉","Vendas"); botao(c6,"Histórico","📜","Historico")
st.markdown("---")

tela = st.session_state['tela_atual']
df_db = carregar_dados()

# --- TELA PRODUTOS (CORRIGIDA) ---
if tela == "Produtos":
    st.header("📋 Cadastro Mestre")
    
    with st.expander("📂 Importar Planilha Mestre (Fornecedor/Preço/Mínimos)", expanded=True):
        f = st.file_uploader("Arquivo", key="up_mst")
        cat = st.selectbox("Categoria:", ["Café", "Perecíveis", "Geral"])
        
        if f:
            try:
                if f.name.endswith('.csv'): df_t = pd.read_csv(f, header=None)
                else: df_t = pd.read_excel(f, header=None)
                
                # Auto-detect header row
                hr = 0
                for i, r in df_t.head(20).iterrows():
                    s = r.astype(str).str.lower().tolist()
                    if any("prod" in x or "nome" in x for x in s): hr=i; break
                
                f.seek(0)
                d = pd.read_csv(f, header=hr) if f.name.endswith('.csv') else pd.read_excel(f, header=hr)
                cols = d.columns.tolist()
                
                st.markdown("#### Mapeie as colunas da sua planilha:")
                c1, c2, c3 = st.columns(3)
                c4, c5, c6 = st.columns(3)
                
                # Índices sugeridos
                def idx(k): return next((i for i,c in enumerate(cols) if any(x in str(c).lower() for x in k)), 0)
                
                # SELETORES MANUAIS (ESSENCIAL)
                cc_n = c1.selectbox("Nome Produto", cols, index=idx(['nome','prod']))
                cc_c = c2.selectbox("Código (Opcional)", ["Ignorar"]+cols, index=idx(['cod'])+1)
                cc_f = c3.selectbox("Fornecedor", ["Ignorar"]+cols, index=idx(['forn'])+1)
                cc_p = c4.selectbox("Padrão/Emb.", ["Ignorar"]+cols, index=idx(['padr','emb'])+1)
                cc_cus = c5.selectbox("Custo Unit.", ["Ignorar"]+cols, index=idx(['cust','valor'])+1)
                
                st.markdown("**Mínimos (Metas) por Hospital:**")
                cm_sa = st.selectbox("Mínimo Sto Amaro", ["Ignorar"]+cols, index=idx(['amaro','sa'])+1)
                cm_si = st.selectbox("Mínimo Sta Izabel", ["Ignorar"]+cols, index=idx(['izabel','si'])+1)
                
                if st.button("🚀 Processar Cadastro"):
                    cnt = 0
                    # Atualiza DataFrame
                    df_db = df_db.set_index('Produto', drop=False)
                    
                    for i, r in d.iterrows():
                        p = str(r[cc_n]).strip()
                        if not p or p=='nan': continue
                        
                        # Monta dicionário de atualização
                        vals = {
                            "Categoria": cat,
                            "Codigo": str(r[cc_c]) if cc_c != "Ignorar" else "",
                            "Fornecedor": str(r[cc_f]) if cc_f != "Ignorar" else "Geral",
                            "Padrao": str(r[cc_p]) if cc_p != "Ignorar" else "",
                            "Custo": limpar_numero(r[cc_cus]) if cc_cus != "Ignorar" else 0.0,
                            "Min_SA": limpar_inteiro(r[cm_sa]) if cm_sa != "Ignorar" else 0,
                            "Min_SI": limpar_inteiro(r[cm_si]) if cm_si != "Ignorar" else 0,
                        }
                        
                        if p in df_db.index:
                            for k,v in vals.items(): df_db.at[p, k] = v
                        else:
                            vals.update({"Produto": p, "Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                            df_new = pd.DataFrame([vals])
                            df_new.set_index('Produto', drop=False, inplace=True)
                            df_db = pd.concat([df_db, df_new])
                        cnt += 1
                    
                    salvar_banco(df_db.reset_index(drop=True))
                    st.success(f"✅ {cnt} produtos atualizados/criados!")
                    st.rerun()
                    
            except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    
    # Editor Rápido
    st.markdown("### ✏️ Editor Rápido")
    edited = st.data_editor(
        df_db[['Codigo', 'Produto', 'Fornecedor', 'Padrao', 'Custo', 'Min_SA', 'Min_SI', 'Categoria']],
        column_config={
            "Produto": st.column_config.TextColumn(disabled=True),
            "Custo": st.column_config.NumberColumn(format="R$ %.2f")
        },
        use_container_width=True, height=400
    )
    if st.button("💾 Salvar Edições da Tabela"):
        # Atualiza o banco com o que foi editado na tabela visual
        df_db = df_db.set_index('Produto')
        edited = edited.set_index('Produto')
        df_db.update(edited)
        salvar_banco(df_db.reset_index())
        st.success("Salvo!")
        st.rerun()

    with st.expander("🔥 Apagar Tudo"):
        if st.button("ZERAR BANCO"): salvar_banco(pd.DataFrame(columns=df_db.columns)); st.rerun()

# --- ESTOQUE ---
elif tela == "Estoque":
    st.header("📦 Estoque")
    c1,c2 = st.columns([1,2]); loc = c1.selectbox("Local", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    cdest = {"Estoque Central":"Estoque_Central", "Hosp. Santo Amaro":"Estoque_SA", "Hosp. Santa Izabel":"Estoque_SI"}[loc]
    
    with st.expander("📂 Importar Contagem"):
        f = st.file_uploader("Arquivo", key="ue")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                # Auto header
                h=0
                for i,r in d.head(20).iterrows():
                    if any("prod" in str(x).lower() for x in r.values): h=i; break
                f.seek(0)
                d = pd.read_csv(f, header=h) if f.name.endswith('.csv') else pd.read_excel(f, header=h)
                
                cols = d.columns.tolist()
                c1,c2 = st.columns(2)
                cn = c1.selectbox("Col Produto", cols, index=next((i for i,c in enumerate(cols) if "prod" in str(c).lower()),0))
                cq = c2.selectbox("Col Qtd", cols, index=next((i for i,c in enumerate(cols) if "qtd" in str(c).lower()),0))
                
                att=0; novos=[]
                df_db = df_db.set_index('Produto', drop=False)
                
                for i, r in d.iterrows():
                    p = str(r[cn]).strip(); q = limpar_inteiro(r[cq])
                    if not p or p=='nan': continue
                    if p in df_db.index:
                        df_db.at[p, cdest] = q; att+=1
                    else:
                        n = {c:0 if "Est" in c or "Min" in c or "Cus" in c else "" for c in df_db.columns}
                        n.update({"Produto":p, cdest:q, "Categoria":"Novo", "Fornecedor":"Geral"})
                        df_db = pd.concat([df_db, pd.DataFrame([n]).set_index('Produto', drop=False)])
                        novos.append(p)
                salvar_banco(df_db.reset_index(drop=True)); st.success(f"{att} ok! {len(novos)} novos."); st.rerun()
            except: st.error("Erro")
            
    st.dataframe(df_db[['Codigo','Produto','Padrao',cdest]].style.format({cdest:"{:.0f}"}), use_container_width=True)

# --- COMPRAS ---
elif tela == "Compras":
    st.header("🛒 Compras")
    l = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", l)
    if sel != st.session_state.get('last_forn'): st.session_state['compras_df_cache']=None; st.session_state['last_forn']=sel
    
    if st.button("🪄 Sugestão (Meta - Total)"):
        d = df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy()
        d['Qtd Compra'] = ((d['Min_SA']+d['Min_SI']) - (d['Estoque_Central']+d['Estoque_SA']+d['Estoque_SI'])).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = d; st.rerun()
        
    v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy())
    if 'Qtd Compra' not in v.columns: v['Qtd Compra']=0
    
    bs = st.text_input("Buscar:", "")
    if bs: v = v[v['Produto'].str.contains(bs, case=False, na=False)]
    
    v['Total'] = v['Qtd Compra'] * v['Custo']
    ed = st.data_editor(v[['Produto','Fornecedor','Padrao','Custo','Qtd Compra','Total']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0), "Custo":st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total":st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
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
        c1.download_button("Baixar PDF", st.session_state['pedido_pdf'], "Ped.pdf", "application/pdf")
        c2.download_button("Baixar Excel", st.session_state['pedido_xlsx'], "Ped.xlsx")

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
            d['Sug'] = (d[cm]-d[ce]).apply(lambda x: max(0, int(x)))
            d['Env'] = d[['Sug','Estoque_Central']].min(axis=1).astype(int)
            st.session_state['transf_df_cache'] = d; st.rerun()
        v = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df_db[['Produto','Estoque_Central',ce,cm]].assign(Env=0)
        bs = st.text_input("Buscar:", "")
        if bs: v = v[v['Produto'].str.contains(bs, case=False, na=False)]
        ed = st.data_editor(v, column_config={"Produto":st.column_config.TextColumn(disabled=True), "Estoque_Central":st.column_config.NumberColumn(disabled=True), "Env":st.column_config.NumberColumn(min_value=0)}, use_container_width=True, height=400)
        if st.button("📦 Adicionar"):
            it = ed[ed['Env']>0]
            if not it.empty:
                l = []
                for i, r in it.iterrows():
                    p=r['Produto']; q=int(r['Env'])
                    idx = df_db[df_db['Produto']==p].index[0]
                    df_db.at[idx, 'Estoque_Central'] -= q
                    df_db.at[idx, ce] += q
                    l.append({"Destino":dest, "Produto":p, "Quantidade":q})
                salvar_banco(df_db); st.session_state['carga_acumulada'].extend(l); st.session_state['transf_df_cache']=None; st.success("Ok!"); st.rerun()
    with c2:
        if st.session_state['carga_acumulada']:
            dfc = pd.DataFrame(st.session_state['carga_acumulada'])
            try: st.dataframe(dfc.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0), use_container_width=True)
            except: st.dataframe(dfc)
            c1, c2 = st.columns(2)
            if c1.button("✅ Finalizar"):
                st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                st.rerun()
            if c2.button("Limpar"): st.session_state['carga_acumulada']=[]; st.session_state['romaneio_pdf']=None; st.rerun()
            if st.session_state['romaneio_pdf']: st.download_button("PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")

elif tela == "Vendas": st.info("Em breve")
elif tela == "Sugestoes": st.info("Em breve")
elif tela == "Dashboard": st.info("Em breve")
elif tela == "Historico": st.dataframe(pd.read_csv(ARQUIVO_LOG) if os.path.exists(ARQUIVO_LOG) else [])
