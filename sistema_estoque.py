import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema 40.0 (Estável)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO DE ESTADO ---
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

# --- FUNÇÕES DE LIMPEZA E DADOS ---
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
    colunas = [
        "Codigo", "Codigo_Unico", "Produto", "Produto_Alt", 
        "Categoria", "Fornecedor", "Padrao", "Custo", 
        "Min_SA", "Min_SI", 
        "Estoque_Central", "Estoque_SA", "Estoque_SI"
    ]
    if not os.path.exists(ARQUIVO_DADOS):
        pd.DataFrame(columns=colunas).to_csv(ARQUIVO_DADOS, index=False)
        return pd.DataFrame(columns=colunas)
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)
    
    # Garante tipos e preenche vazios
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

    # Remove duplicatas pelo nome do produto
    return df.drop_duplicates(subset=['Produto'], keep='last').reset_index(drop=True)

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo = {"Data": datetime.now().strftime("%d/%m %H:%M"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): pd.DataFrame(columns=novo.keys()).to_csv(ARQUIVO_LOG, index=False)
    pd.concat([pd.read_csv(ARQUIVO_LOG), pd.DataFrame([novo])], ignore_index=True).to_csv(ARQUIVO_LOG, index=False)

# --- PDF ---
def criar_pdf_generico(dataframe, titulo_doc, colunas_largura=None):
    try:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=titulo_doc, ln=True, align='C')
        pdf.set_font("Arial", size=10); pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C'); pdf.ln(10)
        cols = dataframe.columns.tolist()
        if not colunas_largura:
            l = 190 // len(cols)
            larguras = [l] * len(cols)
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
                align = 'L' if j==0 else 'C'
                pdf.cell(larguras[j], 10, txt[:45], 1, 0, align)
            pdf.ln()
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return None

# --- MENU ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema Integrado 40.0</h2>", unsafe_allow_html=True)
st.markdown("---")
c1, c2, c3, c4, c5, c6 = st.columns(6)
def botao(col, txt, ico, nome_t):
    estilo = "primary" if st.session_state['tela_atual'] == nome_t else "secondary"
    if col.button(f"{ico}\n{txt}", key=nome_t, use_container_width=True, type=estilo):
        st.session_state['tela_atual'] = nome_t; st.rerun()

botao(c1,"Estoque","📦","Estoque"); botao(c2,"Transferir","🚚","Transferencia"); botao(c3,"Compras","🛒","Compras")
botao(c4,"Produtos","📋","Produtos"); botao(c5,"Vendas","📉","Vendas"); botao(c6,"Histórico","📜","Historico")
st.markdown("---")

tela = st.session_state['tela_atual']
df_db = carregar_dados()

# --- TELAS ---

# 1. PRODUTOS (CORRIGIDA)
if tela == "Produtos":
    st.header("📋 Cadastro e Ajustes")
    
    # UPLOAD MESTRE
    with st.expander("📂 Importar Planilha Mestre (Cadastro Completo)"):
        f = st.file_uploader("Arquivo", key="up_mst")
        cat = st.selectbox("Categoria para estes itens:", ["Café", "Perecíveis", "Geral"])
        if f and st.button("Processar Cadastro"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                # Mapeamento
                cols = {str(c).lower(): c for c in d.columns}
                def g(k): return next((cols[x] for x in cols if any(y in x for y in k)), None)
                
                cn = g(['nom','prod']); cc = g(['cod']); cf = g(['forn']); cp = g(['padr','emb']); ccst = g(['cust'])
                cma = g(['amaro']); cmi = g(['izabel'])
                
                if cn:
                    cnt = 0
                    df_db = df_db.set_index('Produto')
                    for i, r in d.iterrows():
                        p = str(r[cn]).strip()
                        if p and p!='nan':
                            # Dados a atualizar
                            vals = {
                                "Codigo": str(r[cc]) if cc and pd.notna(r[cc]) else "",
                                "Categoria": cat,
                                "Fornecedor": str(r[cf]) if cf and pd.notna(r[cf]) else "Geral",
                                "Padrao": str(r[cp]) if cp and pd.notna(r[cp]) else "",
                                "Custo": limpar_numero(r[ccst]) if ccst else 0.0,
                                "Min_SA": limpar_inteiro(r[cma]) if cma else 0,
                                "Min_SI": limpar_inteiro(r[cmi]) if cmi else 0
                            }
                            
                            if p in df_db.index:
                                for k,v in vals.items(): df_db.at[p, k] = v
                            else:
                                vals['Estoque_Central']=0; vals['Estoque_SA']=0; vals['Estoque_SI']=0
                                df_new = pd.DataFrame([vals], index=[p])
                                df_db = pd.concat([df_db, df_new])
                            cnt+=1
                    
                    salvar_banco(df_db.reset_index()); st.success(f"{cnt} processados!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    
    # EDITOR EM GRADE (NOVO!)
    st.markdown("### ✏️ Editor Rápido (Preencha o que falta)")
    st.info("Use esta tabela para corrigir Fornecedor, Preço e Código dos produtos novos.")
    
    # Filtros
    c_f1, c_f2 = st.columns(2)
    filtro_cat = c_f1.selectbox("Filtrar Categoria:", ["Todas"] + list(df_db['Categoria'].unique()))
    filtro_busca = c_f2.text_input("Buscar Produto:")
    
    df_edit = df_db.copy()
    if filtro_cat != "Todas": df_edit = df_edit[df_edit['Categoria'] == filtro_cat]
    if filtro_busca: df_edit = df_edit[df_edit['Produto'].str.contains(filtro_busca, case=False, na=False)]
    
    # Tabela Editável
    edited = st.data_editor(
        df_edit[['Codigo', 'Produto', 'Fornecedor', 'Padrao', 'Custo', 'Min_SA', 'Min_SI', 'Categoria']],
        column_config={
            "Produto": st.column_config.TextColumn(disabled=True),
            "Custo": st.column_config.NumberColumn(format="R$ %.2f")
        },
        use_container_width=True,
        height=500,
        key="editor_produtos"
    )
    
    # Botão para Salvar Edições
    if st.button("💾 Salvar Alterações da Tabela"):
        # Atualiza o banco principal com as edições
        df_db = df_db.set_index('Produto')
        edited = edited.set_index('Produto')
        df_db.update(edited)
        salvar_banco(df_db.reset_index())
        st.success("Alterações salvas com sucesso!")
        st.rerun()

    with st.expander("🔥 Apagar Tudo"):
        if st.button("ZERAR BANCO"): 
            salvar_banco(pd.DataFrame(columns=df_db.columns)); st.rerun()

# 2. ESTOQUE (CORRIGIDA)
elif tela == "Estoque":
    st.header("📦 Contagem de Estoque")
    c_l, _ = st.columns([1,2]); loc = c_l.selectbox("Local:", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    col_map = {"Estoque Central": "Estoque_Central", "Hosp. Santo Amaro": "Estoque_SA", "Hosp. Santa Izabel": "Estoque_SI"}
    col_dest = col_map[loc]
    
    with st.expander("📂 Upload Contagem (Cria produtos novos)", expanded=True):
        f = st.file_uploader("Arquivo", key="up_e")
        if f and st.button("Processar"):
            try:
                d = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                
                # Auto-detect header
                header_row = 0
                for i, r in d.head(20).iterrows():
                    s = r.astype(str).str.lower().tolist()
                    if any("cod" in x or "prod" in x for x in s): header_row=i; break
                
                f.seek(0)
                d = pd.read_csv(f, header=header_row) if f.name.endswith('.csv') else pd.read_excel(f, header=header_row)
                
                cols = d.columns.tolist()
                c1, c2, c3 = st.columns(3)
                cc = c1.selectbox("Cod", cols, index=next((i for i,c in enumerate(cols) if "cod" in str(c).lower()),0))
                cn = c2.selectbox("Nome", cols, index=next((i for i,c in enumerate(cols) if "nom" in str(c).lower()),0))
                cq = c3.selectbox("Qtd", cols, index=next((i for i,c in enumerate(cols) if "qtd" in str(c).lower()),0))
                
                att = 0
                df_db = df_db.set_index('Produto', drop=False)
                
                for i, r in d.iterrows():
                    c_val = str(r[cc]).strip()
                    n_val = str(r[cn]).strip()
                    q_val = limpar_inteiro(r[cq])
                    
                    if not n_val or n_val=='nan': continue
                    
                    # Lógica: Se existe, atualiza. Se não, cria.
                    if n_val in df_db.index:
                        df_db.at[n_val, col_dest] = q_val
                        # Se tiver codigo na planilha e nao no banco, atualiza
                        if c_val and not df_db.at[n_val, 'Codigo']:
                            df_db.at[n_val, 'Codigo'] = c_val
                    else:
                        # Novo Produto
                        novo = {c:0 if "Estoque" in c or "Min" in c or "Custo" in c else "" for c in df_db.columns}
                        novo['Produto'] = n_val
                        novo['Codigo'] = c_val
                        novo[col_dest] = q_val
                        novo['Categoria'] = "Novos/Indefinido"
                        novo['Fornecedor'] = "A Definir"
                        df_db = pd.concat([df_db, pd.DataFrame([novo]).set_index('Produto')], axis=0)
                    
                    att += 1
                
                salvar_banco(df_db.reset_index(drop=True))
                st.success(f"{att} linhas processadas!")
                st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    filt = st.text_input("Filtrar:", "")
    v = df_db[df_db['Produto'].str.contains(filt, case=False, na=False)] if filt else df_db
    # Mostra Código e Padrão agora!
    st.dataframe(v[['Codigo', 'Produto', 'Padrao', col_dest]].style.format({col_dest:"{:.0f}"}), use_container_width=True, hide_index=True)

# 3. COMPRAS
elif tela == "Compras":
    st.header("🛒 Compras")
    l = ["Todos"] + sorted([str(x) for x in df_db['Fornecedor'].unique() if str(x)!='nan'])
    sel = st.selectbox("Fornecedor", l)
    
    if st.button("🪄 Sugestão"):
        d = df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy()
        d['Meta'] = d['Min_SA'] + d['Min_SI']
        d['Total'] = d['Estoque_Central'] + d['Estoque_SA'] + d['Estoque_SI']
        d['Qtd Compra'] = (d['Meta'] - d['Total']).apply(lambda x: max(0, int(x)))
        st.session_state['compras_df_cache'] = d; st.rerun()
        
    v = st.session_state['compras_df_cache'].copy() if st.session_state['compras_df_cache'] is not None else (df_db.copy() if sel=="Todos" else df_db[df_db['Fornecedor']==sel].copy())
    if 'Qtd Compra' not in v.columns: v['Qtd Compra'] = 0
    
    bus = st.text_input("Buscar:", "")
    if bus: v = v[v['Produto'].str.contains(bus, case=False, na=False)]
    
    v['Total'] = v['Qtd Compra'] * v['Custo']
    ed = st.data_editor(v[['Produto','Fornecedor','Padrao','Custo','Qtd Compra','Total']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0), "Custo":st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total":st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    st.metric("Total", f"R$ {ed['Total'].sum():,.2f}")
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0].copy(); i['Total Item'] = i['Total']
        if not i.empty:
            st.session_state['pedido_pdf'] = criar_pdf_generico(i[['Produto','Fornecedor','Padrao','Qtd Compra','Custo','Total Item']], f"PEDIDO - {sel}")
            st.rerun()
            
    if st.session_state['pedido_pdf']: c1.download_button("Baixar", st.session_state['pedido_pdf'], "Ped.pdf", "application/pdf")

# 4. TRANSFERÊNCIA
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
        
        ed = st.data_editor(dv, column_config={"Produto":st.column_config.TextColumn(disabled=True), "Estoque_Central":st.column_config.NumberColumn(disabled=True), "E":st.column_config.NumberColumn("Enviar", min_value=0)}, use_container_width=True, height=400)
        
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
                st.session_state['romaneio_pdf'] = criar_pdf_generico(dfc, "ROMANEIO")
                st.rerun()
            if st.button("Limpar"): st.session_state['carga_acumulada']=[]; st.session_state['romaneio_pdf']=None; st.rerun()
            if st.session_state['romaneio_pdf']: st.download_button("Baixar PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")
        else: st.info("Vazio")

elif tela == "Vendas": st.info("Use a baixa por arquivo nas configurações de estoque ou implemente aqui.")
elif tela == "Sugestoes": st.info("Em breve")
