import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
ARQUIVO_DADOS = 'estoque_completo.csv'
ARQUIVO_LOG = 'historico_log.csv'
UNIDADES = ["📊 Dashboard", "Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel", "🛒 Compras", "📜 Histórico"]

st.set_page_config(page_title="Sistema Gestão 27.0 (Final)", layout="wide")

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
    colunas_padrao = ["Loja", "Produto", "Estoque_Atual", "Media_Vendas_Semana", "Ultima_Atualizacao", "Fornecedor", "Custo_Unit"]
    if not os.path.exists(ARQUIVO_DADOS): return pd.DataFrame(columns=colunas_padrao)
    try: df = pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas_padrao)
    
    for col in ["Estoque_Atual", "Media_Vendas_Semana", "Custo_Unit"]:
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
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados_cache.clear()

def registrar_log(produto, quantidade, tipo, origem_destino, usuario="Sistema"):
    novo_log = {"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Produto": produto, "Quantidade": quantidade, "Tipo": tipo, "Detalhe": origem_destino, "Usuario": usuario}
    if not os.path.exists(ARQUIVO_LOG): df_log = pd.DataFrame(columns=["Data", "Produto", "Quantidade", "Tipo", "Detalhe", "Usuario"])
    else: df_log = pd.read_csv(ARQUIVO_LOG)
    df_log = pd.concat([df_log, pd.DataFrame([novo_log])], ignore_index=True)
    df_log.to_csv(ARQUIVO_LOG, index=False)

# --- PDF ---
def criar_pdf_generico(dataframe, titulo_doc, colunas_largura=None):
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
    for i, col in enumerate(cols): pdf.cell(larguras[i], 10, col[:15], 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", size=9)
    for index, row in dataframe.iterrows():
        for i, col in enumerate(cols):
            valor = str(row[col])
            texto = valor.encode('latin-1', 'replace').decode('latin-1')
            align = 'L' if i == 0 else 'C'
            pdf.cell(larguras[i], 10, texto[:45], 1, 0, align)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

def resetar_processos():
    for k in ['df_distribuicao_temp', 'romaneio_final', 'df_compras_temp', 'pedido_compra_final', 'romaneio_pdf_cache']:
        st.session_state[k] = None
    st.session_state['distribuicao_concluida'] = False

def limpar_selecao(): st.session_state['selecao_exclusao'] = []
def selecionar_tudo_loja(): 
    if 'df_loja_atual' in st.session_state: st.session_state['selecao_exclusao'] = st.session_state['df_loja_atual']['Produto'].tolist()

# --- FUNÇÃO ESPECIAL: BAIXA POR ARQUIVO ---
def renderizar_baixa_por_arquivo(df_geral, loja_selecionada):
    st.markdown("---")
    with st.expander("📉 Baixar Vendas do Dia (Upload Relatório)", expanded=True):
        st.info("Suba o relatório de vendas. O sistema vai pedir para você confirmar as colunas.")
        
        arquivo_vendas = st.file_uploader("Relatório de Vendas (Excel/CSV)", type=['csv', 'xlsx'], key="up_vendas")
        
        if arquivo_vendas:
            try:
                if arquivo_vendas.name.endswith('.csv'): df_vendas = pd.read_csv(arquivo_vendas)
                else: df_vendas = pd.read_excel(arquivo_vendas)
                
                st.write("Configuração das Colunas:")
                col1, col2 = st.columns(2)
                
                # Tenta adivinhar as colunas
                cols = df_vendas.columns.tolist()
                idx_nome = next((i for i, c in enumerate(cols) if "nome" in c.lower() or "prod" in c.lower() or "desc" in c.lower()), 0)
                idx_qtd = next((i for i, c in enumerate(cols) if "qtd" in c.lower() or "quant" in c.lower()), 0)
                
                col_nome = col1.selectbox("Coluna do Produto:", cols, index=idx_nome)
                col_qtd = col2.selectbox("Coluna da Quantidade:", cols, index=idx_qtd)
                
                if st.button("🚀 Processar Baixa"):
                    log_sucesso = 0
                    log_erro = []
                    
                    for index, row in df_vendas.iterrows():
                        p_nome = str(row[col_nome]).strip()
                        try: q_venda = float(row[col_qtd])
                        except: q_venda = 0
                        
                        if q_venda > 0:
                            # Busca e Abate
                            mask = (df_geral['Loja'] == loja_selecionada) & (df_geral['Produto'] == p_nome)
                            if mask.any():
                                atual = df_geral.loc[mask, 'Estoque_Atual'].values[0]
                                novo = max(0, atual - q_venda)
                                df_geral.loc[mask, 'Estoque_Atual'] = novo
                                log_sucesso += 1
                            else:
                                log_erro.append(f"{p_nome} (Qtd: {q_venda})")
                    
                    if log_sucesso > 0:
                        df_geral.loc[df_geral['Loja'] == loja_selecionada, 'Ultima_Atualizacao'] = datetime.now().strftime("%d/%m %H:%M")
                        salvar_dados(df_geral)
                        registrar_log("Vários", log_sucesso, "Venda", f"Arquivo em {loja_selecionada}")
                        st.success(f"✅ Baixa realizada em {log_sucesso} itens!")
                        if log_erro:
                            with st.expander("⚠️ Itens não encontrados no estoque:"):
                                st.write(log_erro)
                        st.rerun()
                    else:
                        st.warning("Nenhum item processado. Verifique os nomes dos produtos.")
                        
            except Exception as e: st.error(f"Erro ao ler arquivo: {e}")

# --- INTERFACE ---
st.title("🚀 Sistema de Gestão 27.0")
df_geral = carregar_dados_cache()

# BARRA LATERAL
with st.sidebar:
    st.header("Navegação")
    modo = st.radio("Ir para:", UNIDADES)
    st.divider()
    
    # 1. UPLOAD DE ESTOQUE
    if modo in ["Estoque Central", "Hosp. Santo Amaro", "Hosp. Santa Izabel"]:
        with st.expander("📦 Upload de Estoque (Qtd)"):
            arquivo = st.file_uploader("Planilha Estoque", type=['csv', 'xlsx'], key="up_estoque")
            if arquivo:
                try:
                    df_raw = pd.read_csv(arquivo) if arquivo.name.endswith('.csv') else pd.read_excel(arquivo)
                    mapa = {}
                    for col in df_raw.columns:
                        c = col.lower()
                        if "prod" in c or "nome" in c: mapa[col] = "Produto"
                        elif "estoq" in c or "qtd" in c: mapa[col] = "Estoque_Atual"
                        if modo != "Estoque Central" and ("med" in c or "méd" in c): mapa[col] = "Media_Vendas_Semana"
                    df_proc = df_raw.rename(columns=mapa)
                    if "Produto" in df_proc.columns:
                        if "Estoque_Atual" not in df_proc.columns: df_proc["Estoque_Atual"] = 0
                        if "Media_Vendas_Semana" not in df_proc.columns: df_proc["Media_Vendas_Semana"] = 0
                        df_proc["Loja"] = modo
                        df_proc["Ultima_Atualizacao"] = datetime.now().strftime("%d/%m %H:%M")
                        
                        df_antiga = df_geral[df_geral['Loja'] == modo].set_index('Produto')
                        df_antiga = df_antiga[~df_antiga.index.duplicated(keep='first')]
                        
                        df_proc = df_proc.set_index('Produto')
                        if not df_antiga.empty:
                            df_proc['Fornecedor'] = df_proc.index.map(df_antiga['Fornecedor']).fillna("Geral")
                            df_proc['Custo_Unit'] = df_proc.index.map(df_antiga['Custo_Unit']).fillna(0)
                        else:
                            df_proc['Fornecedor'] = "Geral"; df_proc['Custo_Unit'] = 0
                        
                        df_outras = df_geral[df_geral['Loja'] != modo]
                        df_final = pd.concat([df_outras, df_proc.reset_index()], ignore_index=True)
                        salvar_dados(df_final); resetar_processos(); st.success("Estoque Atualizado!"); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

    # 2. ATUALIZAR PREÇOS
    st.markdown("---")
    with st.expander("💲 Atualizar Tabela de Preços"):
        arq_preco = st.file_uploader("Planilha Preços/Forn", type=['csv', 'xlsx'], key="up_preco")
        if arq_preco and st.button("Confirmar Preços"):
            try:
                df_p = pd.read_csv(arq_preco) if arq_preco.name.endswith('.csv') else pd.read_excel(arq_preco)
                mapa_p = {}
                for col in df_p.columns:
                    c = col.lower()
                    if "prod" in c: mapa_p[col] = "Produto"
                    elif "forn" in c: mapa_p[col] = "Fornecedor"
                    elif "cust" in c or "pre" in c: mapa_p[col] = "Custo_Unit"
                
                df_p = df_p.rename(columns=mapa_p)
                df_p = df_p.drop_duplicates(subset=['Produto'], keep='first')
                df_p = df_p.set_index('Produto')
                
                df_g = df_geral.set_index('Produto')
                if "Fornecedor" in df_p.columns: df_g.update(df_p[['Fornecedor']])
                if "Custo_Unit" in df_p.columns: df_g.update(df_p[['Custo_Unit']])
                
                salvar_dados(df_g.reset_index()); st.success("Preços Atualizados!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    st.markdown("---")
    with st.expander("🗑️ Excluir Itens"):
        df_loja = df_geral[df_geral['Loja'] == modo]
        st.session_state['df_loja_atual'] = df_loja
        c1, c2 = st.columns(2)
        c1.button("Tudo", on_click=selecionar_tudo_loja)
        c2.button("Limpar", on_click=limpar_selecao)
        itens_apagar = st.multiselect("Selecionar:", df_loja['Produto'].unique(), key='selecao_exclusao')
        if st.button("❌ Excluir"):
            if itens_apagar:
                mask = ~((df_geral['Loja'] == modo) & (df_geral['Produto'].isin(itens_apagar)))
                df_geral = df_geral[mask]; salvar_dados(df_geral); resetar_processos(); st.success("Excluído!"); st.rerun()

# --- PÁGINAS ---

if modo == "📊 Dashboard":
    st.subheader("Visão Geral")
    df_calc = df_geral.copy()
    df_calc['Valor_Total'] = df_calc['Estoque_Atual'] * df_calc['Custo_Unit']
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Valor Estoque", f"R$ {df_calc['Valor_Total'].sum():,.2f}")
    k2.metric("📦 Volume Total", f"{df_calc['Estoque_Atual'].sum():,.0f}")
    k3.metric("🔻 Zerados", len(df_calc[df_calc['Estoque_Atual'] <= 0]))
    st.bar_chart(df_calc.groupby('Produto')['Valor_Total'].sum().sort_values(ascending=False).head(10))

elif modo == "📜 Histórico":
    st.subheader("Extrato")
    if os.path.exists(ARQUIVO_LOG): st.dataframe(pd.read_csv(ARQUIVO_LOG).sort_values("Data", ascending=False), use_container_width=True)
    else: st.info("Sem registros.")

elif modo == "🛒 Compras":
    st.subheader("🛒 Setor de Compras")
    if st.session_state['df_compras_temp'] is None:
        df_base = df_geral[df_geral['Loja'] == "Estoque Central"][['Produto', 'Fornecedor', 'Custo_Unit']].copy()
        df_base = df_base.drop_duplicates(subset=['Produto']).sort_values('Produto')
        df_base['Qtd Pedido'] = 0
        st.session_state['df_compras_temp'] = df_base

    df_view = st.session_state['df_compras_temp']
    col_f, _ = st.columns([2, 1])
    f_list = sorted([str(x) for x in df_view['Fornecedor'].unique().tolist()])
    lista_forn = ["Todos"] + f_list
    forn_filtro = col_f.selectbox("Filtrar Fornecedor", lista_forn)
    
    df_edit = df_view[df_view['Fornecedor'] == forn_filtro].copy() if forn_filtro != "Todos" else df_view.copy()
    df_edit['Total'] = df_edit['Qtd Pedido'] * df_edit['Custo_Unit']
    
    edited = st.data_editor(df_edit, column_config={"Produto": st.column_config.TextColumn(disabled=True), "Fornecedor": st.column_config.TextColumn(disabled=True), "Custo_Unit": st.column_config.NumberColumn("Preço", format="R$ %.2f", disabled=True), "Total": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True)}, use_container_width=True, height=500)
    
    if not edited.equals(df_edit):
        df_view.set_index('Produto', inplace=True); edited.set_index('Produto', inplace=True)
        df_view.update(edited); df_view.reset_index(inplace=True)
        st.session_state['df_compras_temp'] = df_view; st.rerun()

    st.divider()
    st.metric("Total do Pedido", f"R$ {edited['Total'].sum():,.2f}")
    if st.button("🖨️ Gerar Pedido PDF", type="primary"):
        itens = st.session_state['df_compras_temp']; itens = itens[itens['Qtd Pedido'] > 0]
        if not itens.empty:
            pdf = criar_pdf_generico(itens[['Produto', 'Fornecedor', 'Qtd Pedido', 'Total']], "PEDIDO DE COMPRA", [90, 50, 25, 30])
            st.download_button("Baixar PDF", pdf, "Pedido.pdf", "application/pdf")
            registrar_log("Vários", len(itens), "Compra", f"Total R$ {edited['Total'].sum():.2f}")
        else: st.warning("Vazio.")

elif modo == "Estoque Central":
    if st.session_state['distribuicao_concluida']:
        st.subheader("✅ Sucesso!"); st.success("Estoque atualizado.")
        if st.session_state.get('romaneio_pdf_cache'): st.download_button("📄 Baixar Romaneio", st.session_state['romaneio_pdf_cache'], "Romaneio.pdf", "application/pdf")
        if st.session_state['romaneio_final'] is not None: st.dataframe(st.session_state['romaneio_final'], use_container_width=True)
        if st.button("🔙 Voltar"): resetar_processos(); st.rerun()
    else:
        st.subheader("Distribuição Logística")
        with st.expander("📝 Ajuste Manual"):
            f_prod = st.selectbox("Produto", df_geral[df_geral['Loja'] == modo]['Produto'].unique())
            c1, c2, c3 = st.columns(3)
            op = c1.radio("Ação", ["➕ Entrada", "➖ Baixa"])
            qtd = c2.number_input("Qtd", 1.0)
            if c3.button("Confirmar"):
                idx = df_geral[(df_geral['Loja'] == modo) & (df_geral['Produto'] == f_prod)].index
                cur = df_geral.loc[idx, 'Estoque_Atual'].values[0]
                if "➕" in op: df_geral.loc[idx, 'Estoque_Atual'] += qtd
                else: df_geral.loc[idx, 'Estoque_Atual'] = max(0, cur - qtd)
                salvar_dados(df_geral); registrar_log(f_prod, qtd, "Manual", "Central"); st.rerun()

        st.divider()
        search = st.text_input("🔍 Buscar (Nome/Código)", placeholder="Digite...")
        
        if st.session_state['df_distribuicao_temp'] is None:
            df_base = df_geral[df_geral['Loja'] == modo][['Produto', 'Estoque_Atual']].copy()
            df_base['Enviar SA'] = 0; df_base['Enviar SI'] = 0
            for loja, sigla in [("Hosp. Santo Amaro", "SA"), ("Hosp. Santa Izabel", "SI")]:
                df_h = df_geral[df_geral['Loja'] == loja].set_index('Produto')
                df_h = df_h[~df_h.index.duplicated(keep='first')]
                df_base[f'Tem {sigla}'] = df_base['Produto'].map(df_h['Estoque_Atual']).fillna(0)
                df_base[f'Media {sigla}'] = df_base['Produto'].map(df_h['Media_Vendas_Semana']).fillna(0)
            st.session_state['df_distribuicao_temp'] = df_base

        df_work = st.session_state['df_distribuicao_temp']
        if search: df_view = df_work[df_work['Produto'].str.contains(search, case=False, na=False)].copy()
        else: df_view = df_work.sort_values('Estoque_Atual', ascending=False).head(50).copy(); st.caption("Mostrando top 50.")

        df_view['Saldo'] = df_view['Estoque_Atual'] - df_view['Enviar SA'] - df_view['Enviar SI']
        cols = ['Produto', 'Estoque_Atual', 'Saldo', 'Tem SA', 'Media SA', 'Enviar SA', 'Tem SI', 'Media SI', 'Enviar SI']
        
        edited = st.data_editor(df_view[cols], column_config={"Estoque_Atual": st.column_config.NumberColumn("Central", disabled=True), "Saldo": st.column_config.NumberColumn("Restante", disabled=True), "Tem SA": st.column_config.NumberColumn("🏠 Tem SA", disabled=True, format="%.0f"), "Media SA": st.column_config.NumberColumn("📈 Méd SA", disabled=True, format="%.1f"), "Tem SI": st.column_config.NumberColumn("🏠 Tem SI", disabled=True, format="%.0f"), "Media SI": st.column_config.NumberColumn("📈 Méd SI", disabled=True, format="%.1f")}, use_container_width=True, height=500)
        
        if not edited.equals(df_view[cols]):
            edited.set_index('Produto', inplace=True); df_work.set_index('Produto', inplace=True)
            df_work.update(edited[['Enviar SA', 'Enviar SI']]); df_work.reset_index(inplace=True)
            st.session_state['df_distribuicao_temp'] = df_work; st.rerun()
            
        st.divider()
        if st.button("✅ Efetivar Distribuição", type="primary"):
            final = st.session_state['df_distribuicao_temp']
            rom = []
            for i, r in final.iterrows():
                sa, si = r['Enviar SA'], r['Enviar SI']
                if sa > 0 or si > 0:
                    idx_c = df_geral[(df_geral['Loja'] == modo) & (df_geral['Produto'] == r['Produto'])].index
                    df_geral.loc[idx_c, 'Estoque_Atual'] -= (sa + si)
                    for loja, qtd, sigla in [("Hosp. Santo Amaro", sa, "SA"), ("Hosp. Santa Izabel", si, "SI")]:
                        if qtd > 0:
                            idx_l = (df_geral['Loja'] == loja) & (df_geral['Produto'] == r['Produto'])
                            if idx_l.any(): df_geral.loc[idx_l, 'Estoque_Atual'] += qtd
                            else:
                                novo = df_geral.loc[idx_c].iloc[0].copy(); novo['Loja'] = loja; novo['Estoque_Atual'] = qtd
                                novo['Media_Vendas_Semana'] = r.get(f'Media {sigla}', 0)
                                df_geral = pd.concat([df_geral, pd.DataFrame([novo])], ignore_index=True)
                    rom.append({"Produto": r['Produto'], "Enviar SA": sa, "Enviar SI": si})
                    registrar_log(r['Produto'], sa+si, "Transf", f"SA:{sa} SI:{si}")
            
            salvar_dados(df_geral)
            if rom:
                df_rom = pd.DataFrame(rom)
                pdf = criar_pdf_generico(df_rom, "ROMANEIO", [90, 50, 50])
                st.session_state['romaneio_final'] = df_rom; st.session_state['romaneio_pdf_cache'] = pdf
                st.session_state['distribuicao_concluida'] = True; st.session_state['df_distribuicao_temp'] = None
                st.rerun()

else:
    st.subheader(f"Gestão: {modo}")
    df_l = df_geral[df_geral['Loja'] == modo].copy()
    if not df_l.empty:
        # AQUI ESTÁ A FUNÇÃO NOVA DE BAIXA POR ARQUIVO
        renderizar_baixa_por_arquivo(df_geral, modo)
        
        st.dataframe(df_l[['Produto', 'Estoque_Atual', 'Media_Vendas_Semana']], use_container_width=True)
    else: st.info("Vazio.")