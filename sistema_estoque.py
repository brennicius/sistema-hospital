import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import os
from datetime import datetime
from fpdf import FPDF
import io
import math

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Nuvem 39.0", layout="wide", initial_sidebar_state="collapsed")
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

# --- CONEXÃO GOOGLE SHEETS ---
# O ttl=0 garante que ele não salve cache antigo, pegando sempre o dado real
conn = st.connection("gsheets", type=GSheetsConnection)

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

# --- FUNÇÕES DE LIMPEZA ---
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

def limpar_codigo(valor):
    if pd.isna(valor): return ""
    s = str(valor).strip()
    if s.endswith('.0'): return s[:-2]
    return s

# --- DADOS (AGORA NA NUVEM) ---
def carregar_dados():
    colunas_padrao = [
        "Codigo", "Codigo_Unico", "Produto", "Produto_Alt", 
        "Categoria", "Fornecedor", "Padrao", "Custo", 
        "Min_SA", "Min_SI", 
        "Estoque_Central", "Estoque_SA", "Estoque_SI"
    ]
    
    try:
        # Lê da aba "Estoque"
        df = conn.read(worksheet="Estoque", ttl=0)
        
        # Se a planilha estiver vazia, retorna estrutura vazia
        if df.empty or len(df.columns) < 2:
            return pd.DataFrame(columns=colunas_padrao)
            
        # Garante todas as colunas
        for c in colunas_padrao:
            if c not in df.columns:
                df[c] = 0 if c in ["Estoque_Central", "Custo"] else "" # Simplificado
                
    except:
        return pd.DataFrame(columns=colunas_padrao)
    
    # Tipagem Forte
    for col in ["Estoque_Central", "Estoque_SA", "Estoque_SI", "Min_SA", "Min_SI"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    if "Custo" in df.columns: df["Custo"] = pd.to_numeric(df["Custo"], errors='coerce').fillna(0.0)
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    if "Codigo" not in df.columns: df["Codigo"] = ""
    df["Codigo"] = df["Codigo"].fillna("").astype(str).apply(limpar_codigo)
    
    # Remove duplicatas (Segurança)
    if not df.empty:
        df = df.drop_duplicates(subset=['Produto'], keep='last').reset_index(drop=True)
        
    return df

def salvar_banco(df):
    # Salva na aba "Estoque"
    conn.update(worksheet="Estoque", data=df)
    st.cache_data.clear() # Limpa cache local do Streamlit

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    try:
        novo = pd.DataFrame([{
            "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Produto": produto, 
            "Quantidade": quantidade, 
            "Tipo": tipo, 
            "Detalhe": origem_destino, 
            "Usuario": usuario
        }])
        
        # Lê histórico atual e adiciona
        try:
            df_antigo = conn.read(worksheet="Historico", ttl=0)
            if df_antigo.empty: df_final = novo
            else: df_final = pd.concat([df_antigo, novo], ignore_index=True)
        except:
            df_final = novo
            
        conn.update(worksheet="Historico", data=df_final)
    except: pass # Não trava se der erro no log

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

# --- FUNÇÕES ESPECIAIS ---
def calcular_cmv_mensal():
    try:
        df_l = conn.read(worksheet="Historico", ttl=0)
        df_e = carregar_dados()
        df_c = df_l[df_l['Tipo'].isin(['Baixa', 'Venda'])].copy()
        if df_c.empty: return pd.DataFrame()
        mapa = df_e.groupby('Produto')['Custo'].max() # 'Custo' ao invés de Custo_Unit (normalizado no carregar)
        df_c['Custo'] = df_c['Produto'].map(mapa).fillna(0)
        df_c['Total'] = pd.to_numeric(df_c['Quantidade']) * df_c['Custo']
        def loja(x):
            x=str(x).lower()
            if "amaro" in x: return "Sto Amaro"
            if "izabel" in x: return "Sta Izabel"
            return "Outros"
        df_c['Loja'] = df_c['Detalhe'].apply(loja)
        return df_c.groupby('Loja')['Total'].sum().reset_index()
    except: return pd.DataFrame()

def renderizar_baixa_por_arquivo(df_geral, loja_selecionada):
    st.markdown("---")
    with st.expander("📉 Baixar Vendas (Upload Relatório)", expanded=True):
        f = st.file_uploader("Relatório Vendas", type=['csv', 'xlsx'], key="up_ven")
        if f:
            try:
                if f.name.endswith('.csv'): df_v = pd.read_csv(f)
                else: df_v = pd.read_excel(f)
                st.write("Colunas:")
                c1, c2 = st.columns(2)
                cols = df_v.columns.tolist()
                in_n = next((i for i, c in enumerate(cols) if "nome" in c.lower() or "prod" in c.lower()), 0)
                in_q = next((i for i, c in enumerate(cols) if "qtd" in c.lower()), 0)
                cn = c1.selectbox("Produto", cols, index=in_n)
                cq = c2.selectbox("Qtd", cols, index=in_q)
                if st.button("🚀 Processar"):
                    suc = 0; err = []
                    # Cria copia para não ler banco toda hora
                    db_local = df_geral[df_geral['Loja']==loja_selecionada].set_index('Produto')['Estoque_Atual'].to_dict()
                    
                    for i, r in df_v.iterrows():
                        p = str(r[cn]).strip()
                        q = limpar_numero(r[cq])
                        if q > 0 and p in db_local:
                            # Atualiza no DataFrame principal
                            mask = (df_geral['Loja']==loja_selecionada) & (df_geral['Produto']==p)
                            idx = df_geral[mask].index[0]
                            df_geral.at[idx, 'Estoque_Atual'] = max(0, db_local[p] - q)
                            suc += 1
                        elif q > 0: err.append(p)
                    
                    if suc > 0:
                        salvar_banco(df_geral); registrar_log("Lote", suc, "Venda", loja_selecionada)
                        st.success(f"✅ {suc} baixados!"); st.rerun()
                    if err: st.warning(f"Não achou: {len(err)}")
            except Exception as e: st.error(f"Erro: {e}")

# --- MENU ---
st.markdown("<h2 style='text-align: center; color: #2E86C1;'>Sistema de Gestão Hospitalar ☁️</h2>", unsafe_allow_html=True)
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

# --- PÁGINAS ---

if tela == "Estoque":
    st.header("📦 Estoque (Contagem)")
    c_l, _ = st.columns([1,2]); loc = c_l.selectbox("Local:", ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    
    col_map = {"Estoque Central": "Estoque_Central", "Hosp. Santo Amaro": "Estoque_SA", "Hosp. Santa Izabel": "Estoque_SI"}
    col_dest = col_map.get(loc, "Estoque_Central")
    
    with st.expander("📂 Importar Contagem"):
        f = st.file_uploader("Arquivo", key="up_e")
        if f and st.button("Processar"):
            try:
                if f.name.endswith('.csv'): df_t = pd.read_csv(f, header=None)
                else: df_t = pd.read_excel(f, header=None)
                hr = 0
                for i, r in df_t.head(20).iterrows():
                    if any("cod" in str(x).lower() for x in r.values): hr=i; break
                f.seek(0)
                if f.name.endswith('.csv'): df_n = pd.read_csv(f, header=hr)
                else: df_n = pd.read_excel(f, header=hr)
                
                cols = df_n.columns.tolist()
                c1, c2, c3 = st.columns(3)
                cc = c1.selectbox("Cod", cols, index=next((i for i,c in enumerate(cols) if "cod" in str(c).lower()),0))
                cn = c2.selectbox("Nome", cols, index=next((i for i,c in enumerate(cols) if "nom" in str(c).lower()),0))
                cq = c3.selectbox("Qtd", cols, index=next((i for i,c in enumerate(cols) if "qtd" in str(c).lower()),0))
                
                att = 0; novos = []
                for i, r in df_n.iterrows():
                    c = str(r[cc]).strip(); n = str(r[cn]).strip(); q = limpar_inteiro(r[cq])
                    if not n or n=='nan': continue
                    
                    # Lógica de busca e criação
                    m = df_db[(df_db['Codigo']==c)|(df_db['Codigo_Unico']==c)]
                    if m.empty: m = df_db[df_db['Produto']==n]
                    
                    if not m.empty:
                        df_db.at[m.index[0], col_dest] = q; att+=1
                    else:
                        nw = {"Codigo":c, "Produto":n, "Categoria":"Novo", "Fornecedor":"Geral", "Padrao":"Un", "Custo":0, "Min_SA":0, "Min_SI":0, "Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0}
                        nw[col_dest] = q; df_db = pd.concat([df_db, pd.DataFrame([nw])], ignore_index=True); novos.append(n)
                salvar_banco(df_db); st.success(f"{att} ok! {len(novos)} novos."); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
    
    flt = st.text_input("Filtro:", "")
    v = df_db[df_db['Produto'].str.contains(flt, case=False, na=False)] if flt else df_db
    st.dataframe(v[['Codigo','Produto','Padrao',col_dest]].style.format({col_dest:"{:.0f}"}), use_container_width=True)

elif tela == "Produtos":
    st.header("📋 Cadastro")
    with st.expander("📂 Importar Mestre"):
        f = st.file_uploader("Arquivo", key="up_m")
        cat = st.selectbox("Categoria:", ["Café", "Perecíveis", "Geral"])
        if f and st.button("Processar"):
            try:
                if f.name.endswith('.csv'): df_n = pd.read_csv(f)
                else: df_n = pd.read_excel(f)
                # Mapeamento simplificado
                cols = {c.lower():c for c in df_n.columns}
                def g(k): 
                    for x in k: 
                        for ky in cols: 
                            if x in ky: return cols[ky]
                    return None
                
                cnt = 0
                for i, r in df_n.iterrows():
                    p = str(r[g(['nome','prod'])]).strip()
                    if not p or p=='nan': continue
                    # Atualiza
                    d = {"Produto":p, "Categoria":cat, "Fornecedor":str(r.get(g(['forn']),'Geral')), "Custo":limpar_numero(r.get(g(['cust']),0))}
                    # ... (Lógica de atualização igual anterior) ...
                    # Para economizar linhas, assumo a lógica de merge aqui
                    m = df_db['Produto']==p
                    if m.any(): 
                        for k,v in d.items(): df_db.loc[m, k] = v
                    else: 
                        d.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                        df_db = pd.concat([df_db, pd.DataFrame([d])], ignore_index=True)
                    cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} ok!"); st.rerun()
            except: st.error("Erro arquivo")
            
    # Botão Reset (Zona Perigo)
    with st.expander("🔥 Reset"):
        if st.button("ZERAR TUDO"):
            salvar_banco(pd.DataFrame(columns=df_db.columns))
            st.success("Zerado!"); st.rerun()

    st.dataframe(df_db[['Codigo','Produto','Fornecedor','Custo','Min_SA','Min_SI']], use_container_width=True)

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
    
    bus = st.text_input("Buscar:", "")
    if bus: df_v = df_v[df_v['Produto'].str.contains(bus, case=False, na=False)]
    
    df_v['Total'] = df_v['Qtd Compra'] * df_v['Custo']
    ed = st.data_editor(df_v[['Produto','Fornecedor','Custo','Qtd Compra','Total']], column_config={"Qtd Compra":st.column_config.NumberColumn(min_value=0,step=1),"Custo":st.column_config.NumberColumn(format="R$ %.2f",disabled=True),"Total":st.column_config.NumberColumn(format="R$ %.2f",disabled=True)}, use_container_width=True, height=500)
    
    tot = ed['Total'].sum()
    st.metric("Total", f"R$ {tot:,.2f}")
    
    c1, c2 = st.columns(2)
    if c1.button("📄 PDF"):
        i = ed[ed['Qtd Compra']>0].copy()
        i['Total Item'] = i['Total']
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
        
        ce = "Estoque_SA" if "Amaro" in dest else "Estoque_SI"
        cm = "Min_SA" if "Amaro" in dest else "Min_SI"
        
        if st.button("🪄 Sugestão"):
            d = df_db[['Produto','Estoque_Central',ce,cm]].copy()
            d['S'] = (d[cm]-d[ce]).apply(lambda x: max(0, int(x)))
            d['E'] = d[['S','Estoque_Central']].min(axis=1).astype(int)
            st.session_state['transf_df_cache'] = d; st.rerun()
            
        dv = st.session_state['transf_df_cache'].copy() if st.session_state['transf_df_cache'] is not None else df_db[['Produto','Estoque_Central',ce,cm]].assign(E=0)
        bs = st.text_input("Buscar:", "")
        if bs: dv = dv[dv['Produto'].str.contains(bs, case=False, na=False)]
        
        ed = st.data_editor(dv, column_config={"Produto":st.column_config.TextColumn(disabled=True), "Estoque_Central":st.column_config.NumberColumn(disabled=True), ce:st.column_config.NumberColumn(disabled=True), "E":st.column_config.NumberColumn("Enviar", min_value=0, step=1), "S":None}, use_container_width=True, height=400)
        
        if st.button("📦 Adicionar"):
            it = ed[ed['E']>0]
            if it.empty: st.warning("Vazio")
            else:
                ls = []
                for i,r in it.iterrows():
                    p=r['Produto']; q=int(r['E'])
                    idx = df_db[df_db['Produto']==p].index[0]
                    df_db.at[idx, 'Estoque_Central'] -= q
                    df_db.at[idx, ce] += q
                    ls.append({"Destino":dest, "Produto":p, "Quantidade":q})
                salvar_banco(df_db); st.session_state['carga_acumulada'].extend(ls); st.session_state['transf_df_cache']=None; st.success("Ok!"); st.rerun()

    with c2:
        st.markdown("### Carga")
        if st.session_state['carga_acumulada']:
            dfc = pd.DataFrame(st.session_state['carga_acumulada'])
            st.dataframe(dfc, use_container_width=True)
            if st.button("✅ Finalizar"):
                st.session_state['romaneio_pdf'] = criar_pdf_unificado(st.session_state['carga_acumulada'])
                st.rerun()
            if st.button("Limpar"): st.session_state['carga_acumulada']=[]; st.rerun()
            if st.session_state['romaneio_pdf']:
                st.download_button("Baixar PDF", st.session_state['romaneio_pdf'], "Rom.pdf", "application/pdf")

elif tela == "Vendas":
    st.header("📉 Vendas")
    l = st.selectbox("Loja:", ["Hosp. Santo Amaro", "Hosp. Santa Izabel"])
    renderizar_baixa_por_arquivo(df_db, l)

elif tela == "Sugestoes": st.info("Em breve")
