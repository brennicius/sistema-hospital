import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
ARQUIVO_DADOS = 'estoque_completo.csv'
ARQUIVO_LOG = 'historico_log.csv'
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

st.set_page_config(page_title="Sistema Blindado 28.0", layout="wide")

# --- AUTO-CRIAÇÃO DE ARQUIVOS (CORREÇÃO DEFINITIVA) ---
def garantir_arquivos_existem():
    # 1. Garante Banco de Dados
    if not os.path.exists(ARQUIVO_DADOS):
        df_base = pd.DataFrame(columns=["Loja", "Produto", "Estoque_Atual", "Media_Vendas_Semana", "Ultima_Atualizacao", "Fornecedor", "Custo_Unit"])
        df_base.to_csv(ARQUIVO_DADOS, index=False)
    
    # 2. Garante Histórico (Log)
    if not os.path.exists(ARQUIVO_LOG):
        df_log = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
        df_log.to_csv(ARQUIVO_LOG, index=False)

garantir_arquivos_existem() # Executa ao iniciar

# --- INICIALIZAÇÃO DE ESTADO ---
def init_state():
    keys = ['df_distribuicao_temp', 'df_compras_temp', 'romaneio_final', 'romaneio_pdf_cache', 
            'distribuicao_concluida', 'pedido_compra_final', 'selecao_exclusao']
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = None if 'df' in k or 'romaneio' in k or 'pedido' in k else []
            if k == 'distribuicao_concluida': st.session_state[k] = False

init_state()

# --- FUNÇÕES DE DADOS ---
@st.cache_data
def carregar_dados_cache():
    # Carregamento seguro
    try:
        df = pd.read_csv(ARQUIVO_DADOS)
    except Exception:
        return pd.DataFrame(columns=["Loja", "Produto", "Estoque_Atual", "Media_Vendas_Semana", "Ultima_Atualizacao", "Fornecedor", "Custo_Unit"])
    
    # Normalização
    cols_num = ["Estoque_Atual", "Media_Vendas_Semana", "Custo_Unit"]
    for col in cols_num:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else: df[col] = 0
            
    if "Fornecedor" not in df.columns: df["Fornecedor"] = "Geral"
    df["Fornecedor"] = df["Fornecedor"].fillna("Geral").astype(str)
    
    if not df.empty:
        df = df.groupby(['Loja', 'Produto', 'Fornecedor', 'Ultima_Atualizacao'], as_index=False).agg({
            'Estoque_Atual': 'sum', 'Media_Vendas_Semana': 'max', 'Custo_Unit': 'max'
        })
    return df

def salvar_dados(df):
    try:
        df.to_csv(ARQUIVO_DADOS, index=False)
        carregar_dados_cache.clear()
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    try:
        novo_log = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
        # Lê usando pandas direto para evitar erro de lock
        if os.path.exists(ARQUIVO_LOG):
            df_log = pd.read_csv(ARQUIVO_LOG)
        else:
            df_log = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
        
        df_log = pd.concat([df_log, pd.DataFrame([novo_log])], ignore_index=True)
        df_log.to_csv(ARQUIVO_LOG, index=False)
    except Exception as e:
        print(f"Erro ao salvar log (ignorado): {e}") # Não trava o sistema se o log falhar

# --- PDF BLINDADO ---
def criar_pdf_generico(dataframe, titulo_doc, colunas_largura=None):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=titulo_doc, ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(5)
        
        cols = dataframe.columns.tolist()
        if not colunas_largura:
            largura_base = 190 // len(cols)
            larguras = [largura_base] * len(cols)
            if "Produto" in cols: idx = cols.index("Produto"); larguras[idx] = 80 
        else: larguras = colunas_largura

        pdf.set_font("Arial", 'B', 9)
        for i, col in enumerate(cols):
            txt = str(col).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(larguras[i], 10, txt[:20], 1, 0, 'C')
        pdf.ln()
        
        pdf.set_font("Arial", size=9)
        for index, row in dataframe.iterrows():
            for i, col in enumerate(cols):
                valor = str(row[col])
                texto = valor.encode('latin-1', 'replace').decode('latin-1')
                align = 'L' if i == 0 else 'C'
                pdf.cell(larguras[i], 10, texto[:45], 1, 0, align)
            pdf.ln()
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        return str(e).encode('utf-8')

# --- FUNÇÕES ESPECIAIS (CMV, PREVISÃO) ---
def calcular_cmv_mensal():
    # Proteção: Se o arquivo não existir ou estiver vazio/corrompido, retorna vazio
    try:
        if not os.path.exists(ARQUIVO_LOG): return pd.DataFrame()
        df_l = pd.read_csv(ARQUIVO_LOG)
        if df_l.empty: return pd.DataFrame()
        
        df_e = carregar_dados_cache()
        
        df_c = df_l[df_l['Tipo'].isin(['Baixa', 'Venda'])].copy()
        if df_c.empty: return pd.DataFrame()
        
        mapa = df_e.groupby('Produto')['Custo_Unit'].max()
        df_c['Custo'] = df_c['Produto'].map(mapa).fillna(0)
        df_c['Total'] = df_c['Quantidade'] * df_c['Custo']
        
        def loja(x):
            x=str(x).lower()
            if "amaro" in x: return "Sto Amaro"
            if "izabel" in x: return "Sta Izabel"
            if "central" in x: return "Central"
            return "Outros"
        df_c['Loja'] = df_c['Detalhe'].apply(loja)
        return df_c.groupby('Loja')['Total'].sum().reset_index()
    except:
        return pd.DataFrame() # Retorna vazio em caso de qualquer erro

def renderizar_baixa_por_arquivo(df_geral, loja_selecionada):
    st.markdown("---")
    with st.expander("📉 Baixar Vendas do Dia (Upload Relatório)", expanded=True):
        arquivo_vendas = st.file_uploader("Relatório de Vendas", type=['csv', 'xlsx'], key="up_vendas")
        if arquivo_vendas:
            try:
                if arquivo_vendas.name.endswith('.csv'): df_vendas = pd.read_csv(arquivo_vendas)
                else: df_vendas = pd.read_excel(arquivo_vendas)
                
                st.write("Confirme as colunas:")
                c1, c2 = st.columns(2)
                cols = df_vendas.columns.tolist()
                
                # Tenta adivinhar (Safe)
                idx_n = 0; idx_q = 0
                for i, c in enumerate(cols):
                    if "nome" in c.lower() or "prod" in c.lower(): idx_n = i
                    if "qtd" in c.lower() or "quant" in c.lower(): idx_q = i
                
                cn = c1.selectbox("Produto", cols, index=idx_n)
                cq = c2.selectbox("Qtd", cols, index=idx_q)
                
                if st.button("🚀 Processar Baixa"):
                    suc = 0; err = []
                    for i, r in df_vendas.iterrows():
                        p = str(r[cn]).strip()
                        try: q = float(r[cq])
                        except: q = 0
                        if q > 0:
                            mask = (df_geral['Loja'] == loja_selecionada) & (df_geral['Produto'] == p)
                            if mask.any():
                                cur = df_geral.loc[mask, 'Estoque_Atual'].values[0]
                                df_geral.loc[mask, 'Estoque_Atual'] = max(0, cur - q)
                                suc += 1
                            else: err.append(p)
                    
                    if suc > 0:
                        df_geral.loc[df_geral['Loja'] == loja_selecionada, 'Ultima_Atualizacao'] = datetime.now().strftime("%d/%m %H:%M")
                        salvar_dados(df_geral)
                        registrar_log("Vários", suc, "Venda", f"Arquivo {loja_selecionada}")
                        st.success(f"✅ {suc} itens baixados!")
                        st.rerun()
                    else: st.warning("Nenhum item processado.")
            except Exception as e: st.error(f"Erro: {e}")

# --- MÉTODOS DE RESET E LIMPEZA ---
def resetar_processos():
    for k in ['df_distribuicao_temp', 'romaneio_final', 'df_compras_temp', 'pedido_compra_final', 'romaneio_pdf_cache']:
        st.session_state[k] = None
    st.session_state['distribuicao_concluida'] = False

def limpar_selecao(): st.session_state['selecao_exclusao'] = []
def selecionar_tudo_loja(): 
    if 'df_loja_atual' in st.session_state: st.session_state['selecao_exclusao'] = st.session_state['df_loja_atual']['Produto'].tolist()

# --- INTERFACE ---
st.title("🚀 Sistema Integrado 28.0")
df_geral = carregar_dados_cache()

with st.sidebar:
    st.header("Menu")
    modo = st.radio("Ir para:", UNIDADES)
    st.divider()
    
    # Upload Estoque
    if modo in ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"]:
        with st.expander("📦 Upload Estoque"):
            f = st.file_uploader("Arquivo", type=['csv', 'xlsx'], key="ue")
            if f:
                try:
                    df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                    mapa = {}
                    for c in df.columns:
                        cl = c.lower()
                        if "prod" in cl: mapa[c] = "Produto"
                        elif "est" in cl or "qtd" in cl: mapa[c] = "Estoque_Atual"
                        elif "med" in cl: mapa[c] = "Media_Vendas_Semana"
                    df = df.rename(columns=mapa)
                    if "Produto" in df.columns:
                        if "Estoque_Atual" not in df.columns: df["Estoque_Atual"]=0
                        if "Media_Vendas_Semana" not in df.columns: df["Media_Vendas_Semana"]=0
                        df["Loja"] = modo; df["Ultima_Atualizacao"] = datetime.now().strftime("%d/%m %H:%M")
                        
                        ant = df_geral[df_geral['Loja']==modo].set_index('Produto')
                        ant = ant[~ant.index.duplicated(keep='first')]
                        df = df.set_index('Produto')
                        if not ant.empty:
                            df['Fornecedor'] = df.index.map(ant['Fornecedor']).fillna("Geral")
                            df['Custo_Unit'] = df.index.map(ant['Custo_Unit']).fillna(0)
                        else: df['Fornecedor']="Geral"; df['Custo_Unit']=0
                        
                        out = df_geral[df_geral['Loja']!=modo]
                        salvar_dados(pd.concat([out, df.reset_index()], ignore_index=True))
                        resetar_processos(); st.success("Ok!"); st.rerun()
                except: st.error("Erro")

    with st.expander("💲 Preços"):
        f = st.file_uploader("Arquivo", type=['csv', 'xlsx'], key="up")
        if f and st.button("Salvar"):
            try:
                df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                mapa = {}
                for c in df.columns:
                    cl = c.lower()
                    if "prod" in cl: mapa[c] = "Produto"
                    elif "forn" in cl: mapa[c] = "Fornecedor"
                    elif "cust" in cl or "pre" in cl: mapa[c] = "Custo_Unit"
                df = df.rename(columns=mapa).drop_duplicates('Produto').set_index('Produto')
                g = df_geral.set_index('Produto')
                if "Fornecedor" in df.columns: g.update(df[['Fornecedor']])
                if "Custo_Unit" in df.columns: g.update(df[['Custo_Unit']])
                salvar_dados(g.reset_index()); st.success("Ok!"); st.rerun()
            except: st.error("Erro")

    with st.expander("🗑️ Lixeira"):
        df_l = df_geral[df_geral['Loja']==modo]
        st.session_state['df_loja_atual'] = df_l
        c1, c2 = st.columns(2)
        c1.button("Tudo", on_click=selecionar_tudo_loja)
        c2.button("Limpar", on_click=limpar_selecao)
        it = st.multiselect("Itens:", df_l['Produto'].unique(), key='selecao_exclusao')
        if st.button("Excluir"):
            mask = ~((df_geral['Loja']==modo) & (df_geral['Produto'].isin(it)))
            salvar_dados(df_geral[mask]); resetar_processos(); st.success("Ok"); st.rerun()

# --- PÁGINAS ---
if modo == "📊 Dashboard":
    st.subheader("Visão Geral")
    df_c = df_geral.copy()
    df_c['Valor'] = df_c['Estoque_Atual'] * df_c['Custo_Unit']
    k1, k2, k3 = st.columns(3)
    k1.metric("Valor Total", f"R$ {df_c['Valor'].sum():,.2f}")
    k2.metric("Volume", f"{df_c['Estoque_Atual'].sum():,.0f}")
    k3.metric("Zerados", len(df_c[df_c['Estoque_Atual']<=0]))
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔥 Consumo (CMV)")
        cmv = calcular_cmv_mensal()
        if not cmv.empty: st.bar_chart(cmv.set_index('Loja'))
        else: st.info("Sem histórico de consumo ainda.")
    with c2:
        st.markdown("### 🏆 Top Valor")
        st.bar_chart(df_c.groupby('Produto')['Valor'].sum().sort_values(ascending=False).head(10))

elif modo == "📜 Histórico":
    st.subheader("Log")
    if os.path.exists(ARQUIVO_LOG): st.dataframe(pd.read_csv(ARQUIVO_LOG).sort_values('Data', ascending=False), use_container_width=True)
    else: st.info("Vazio")

elif modo == "🛒 Compras":
    st.subheader("Compras")
    if st.session_state['df_compras_temp'] is None:
        base = df_geral[df_geral['Loja']=="Estoque Central"][['Produto','Fornecedor','Custo_Unit']].copy()
        base = base.drop_duplicates('Produto').sort_values('Produto')
        base['Qtd'] = 0
        st.session_state['df_compras_temp'] = base
    
    view = st.session_state['df_compras_temp']
    f_list = ["Todos"] + sorted(view['Fornecedor'].unique().tolist())
    sel = st.selectbox("Fornecedor", f_list)
    edit = view[view['Fornecedor']==sel].copy() if sel!="Todos" else view.copy()
    edit['Total'] = edit['Qtd'] * edit['Custo_Unit']
    
    ed = st.data_editor(edit, column_config={"Qtd": st.column_config.NumberColumn(min_value=0), "Custo_Unit": st.column_config.NumberColumn(format="R$ %.2f", disabled=True), "Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    if not ed.equals(edit):
        view.set_index('Produto', inplace=True); ed.set_index('Produto', inplace=True)
        view.update(ed); view.reset_index(inplace=True)
        st.session_state['df_compras_temp'] = view; st.rerun()
    
    st.metric("Total", f"R$ {ed['Total'].sum():,.2f}")
    if st.button("Baixar Pedido PDF"):
        i = st.session_state['df_compras_temp']; i = i[i['Qtd']>0]
        if not i.empty:
            pdf_bytes = criar_pdf_generico(i[['Produto','Fornecedor','Qtd','Total']], "PEDIDO DE COMPRA", [90,50,20,30])
            st.download_button("Clique para Baixar", pdf_bytes, "Pedido.pdf", "application/pdf")
            registrar_log("Vários", len(i), "Compra", f"R$ {ed['Total'].sum():.2f}")
        else: st.warning("Vazio")

elif modo == "Estoque Central":
    if st.session_state['distribuicao_concluida']:
        st.success("Sucesso!")
        if st.session_state.get('romaneio_pdf_cache'): st.download_button("Baixar Romaneio", st.session_state['romaneio_pdf_cache'], "Rom.pdf", "application/pdf")
        if st.session_state['romaneio_final'] is not None: st.dataframe(st.session_state['romaneio_final'], use_container_width=True)
        if st.button("Voltar"): resetar_processos(); st.rerun()
    else:
        st.subheader("Distribuição")
        with st.expander("Ajuste Manual"):
            p = st.selectbox("Prod", df_geral[df_geral['Loja']==modo]['Produto'].unique())
            q = st.number_input("Qtd", 1.0)
            c1, c2 = st.columns(2)
            if c1.button("Entrada"):
                idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                df_geral.loc[idx, 'Estoque_Atual'] += q
                salvar_dados(df_geral); registrar_log(p, q, "Entrada", "Man"); st.success("Ok"); st.rerun()
            if c2.button("Baixa"):
                idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                cur = df_geral.loc[idx, 'Estoque_Atual'].values[0]
                df_geral.loc[idx, 'Estoque_Atual'] = max(0, cur-q)
                salvar_dados(df_geral); registrar_log(p, q, "Baixa", "Man"); st.success("Ok"); st.rerun()
        
        search = st.text_input("Buscar", placeholder="Nome...")
        if st.session_state['df_distribuicao_temp'] is None:
            df_b = df_geral[df_geral['Loja']==modo][['Produto','Estoque_Atual']].copy()
            df_b['Env SA'] = 0; df_b['Env SI'] = 0
            for l, s in [("Hosp. Santo Amaro","SA"), ("Hosp. Santa Izabel","SI")]:
                df_h = df_geral[df_geral['Loja']==l].set_index('Produto')
                df_h = df_h[~df_h.index.duplicated(keep='first')]
                df_b[f'Tem {s}'] = df_b['Produto'].map(df_h['Estoque_Atual']).fillna(0)
                df_b[f'Med {s}'] = df_b['Produto'].map(df_h['Media_Vendas_Semana']).fillna(0)
            st.session_state['df_distribuicao_temp'] = df_b
            
        df_w = st.session_state['df_distribuicao_temp']
        df_view = df_w[df_w['Produto'].str.contains(search, case=False, na=False)].copy() if search else df_w.sort_values('Estoque_Atual', ascending=False).head(50).copy()
        
        df_view['Saldo'] = df_view['Estoque_Atual'] - df_view['Env SA'] - df_view['Env SI']
        cols = ['Produto', 'Estoque_Atual', 'Saldo', 'Tem SA', 'Med SA', 'Env SA', 'Tem SI', 'Med SI', 'Env SI']
        
        ed = st.data_editor(df_view[cols], column_config={"Estoque_Atual": st.column_config.NumberColumn(disabled=True), "Saldo": st.column_config.NumberColumn(disabled=True), "Tem SA": st.column_config.NumberColumn(disabled=True), "Med SA": st.column_config.NumberColumn(disabled=True), "Tem SI": st.column_config.NumberColumn(disabled=True), "Med SI": st.column_config.NumberColumn(disabled=True)}, use_container_width=True, height=500)
        
        if not ed.equals(df_view[cols]):
            ed.set_index('Produto', inplace=True); df_w.set_index('Produto', inplace=True)
            df_w.update(ed[['Env SA', 'Env SI']]); df_w.reset_index(inplace=True)
            st.session_state['df_distribuicao_temp'] = df_w; st.rerun()
            
        if st.button("Efetivar"):
            fin = st.session_state['df_distribuicao_temp']
            rom = []
            env = fin[(fin['Env SA']>0)|(fin['Env SI']>0)]
            if env.empty: st.warning("Nada")
            else:
                for i, r in env.iterrows():
                    sa, si, p = r['Env SA'], r['Env SI'], r['Produto']
                    idx = df_geral[(df_geral['Loja']==modo)&(df_geral['Produto']==p)].index
                    if not idx.empty:
                        df_geral.loc[idx, 'Estoque_Atual'] -= (sa+si)
                        for l, q, s in [("Hosp. Santo Amaro", sa, "SA"), ("Hosp. Santa Izabel", si, "SI")]:
                            if q>0:
                                idl = (df_geral['Loja']==l)&(df_geral['Produto']==p)
                                if idl.any(): df_geral.loc[idl, 'Estoque_Atual'] += q
                                else:
                                    n = df_geral.loc[idx].iloc[0].copy(); n['Loja']=l; n['Estoque_Atual']=q; n['Media_Vendas_Semana']=r.get(f'Med {s}',0)
                                    df_geral = pd.concat([df_geral, pd.DataFrame([n])], ignore_index=True)
                        rom.append({"Produto":p, "Env SA":sa, "Env SI":si})
                        registrar_log(p, sa+si, "Transferência", f"SA:{sa} SI:{si}")
                salvar_dados(df_geral)
                pdf = criar_pdf_generico(pd.DataFrame(rom), "ROMANEIO")
                st.session_state['romaneio_pdf_cache'] = pdf
                st.session_state['romaneio_final'] = pd.DataFrame(rom)
                st.session_state['distribuicao_concluida'] = True
                st.session_state['df_distribuicao_temp'] = None
                st.rerun()

else:
    st.subheader(f"Gestão: {modo}")
    df_l = df_geral[df_geral['Loja'] == modo].copy()
    if not df_l.empty:
        # AQUI ESTÁ A FUNÇÃO NOVA
        renderizar_baixa_por_arquivo(df_geral, modo)
        
        st.dataframe(df_l[['Produto', 'Estoque_Atual', 'Media_Vendas_Semana']], use_container_width=True)
    else: st.info("Vazio")