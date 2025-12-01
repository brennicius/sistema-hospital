import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Gestão 37.1 (Fix)", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO DE ESTADO ---
def init_state():
    if 'romaneio_pdf' not in st.session_state: st.session_state['romaneio_pdf'] = None
    if 'romaneio_xlsx' not in st.session_state: st.session_state['romaneio_xlsx'] = None
    if 'pedido_pdf' not in st.session_state: st.session_state['pedido_pdf'] = None
    if 'pedido_xlsx' not in st.session_state: st.session_state['pedido_xlsx'] = None
    
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Compras"
    
    if 'selecao_exclusao' not in st.session_state: st.session_state['selecao_exclusao'] = []
    if 'carga_acumulada' not in st.session_state: st.session_state['carga_acumulada'] = []
    
    # Estados de Cache
    if 'transf_df_cache' not in st.session_state: st.session_state['transf_df_cache'] = None
    if 'transf_key_ver' not in st.session_state: st.session_state['transf_key_ver'] = 0
    
    if 'compras_df_cache' not in st.session_state: st.session_state['compras_df_cache'] = None
    if 'compras_key_ver' not in st.session_state: st.session_state['compras_key_ver'] = 0
    if 'ultimo_fornecedor' not in st.session_state: st.session_state['ultimo_fornecedor'] = "Todos"

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
    try: return pd.read_csv(ARQUIVO_DADOS)
    except: return pd.DataFrame(columns=colunas)

def salvar_banco(df):
    df.to_csv(ARQUIVO_DADOS, index=False)
    carregar_dados.clear()

def limpar_numero(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).lower().replace('r$', '').replace(' ', '').replace(',', '.')
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
        pdf.cell(190, 10, txt=f"Data Emissao: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(10)
        
        df = pd.DataFrame(lista_carga)
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
            pdf.cell(110, 8, str(r['Produto'])[:55].encode('latin-1','replace').decode('latin-1'), 1, 0, 'L')
            pdf.cell(40, 8, str(int(r[col_sa])) if r[col_sa]>0 else "-", 1, 0, 'C')
            pdf.cell(40, 8, str(int(r[col_si])) if r[col_si]>0 else "-", 1, 1, 'C')
        pdf.ln(20)
        pdf.cell(60, 10, "_"*30, 0, 0, 'C'); pdf.cell(5, 10, "", 0, 0); pdf.cell(60, 10, "_"*30, 0, 0, 'C'); pdf.cell(5, 10, "", 0, 0); pdf.cell(60, 10, "_"*30, 0, 1, 'C')
        pdf.set_font("Arial", size=8)
        pdf.cell(60, 5, "Expedicao (Central)", 0, 0, 'C'); pdf.cell(5, 5, "", 0, 0); pdf.cell(60, 5, "Recebedor (Sto Amaro)", 0, 0, 'C'); pdf.cell(5, 5, "", 0, 0); pdf.cell(60, 5, "Recebedor (Sta Izabel)", 0, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e: return str(e).encode('utf-8')

# --- PDF PEDIDO ---
def criar_pdf_compra(dataframe, fornecedor_nome, total_geral):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=f"PEDIDO DE COMPRA - {fornecedor_nome.upper()}", ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(90, 8, "Produto", 1, 0, 'C', fill=True)
        pdf.cell(30, 8, "Padrao/Emb", 1, 0, 'C', fill=True)
        pdf.cell(25, 8, "Qtd", 1, 0, 'C', fill=True)
        pdf.cell(25, 8, "Custo Unit", 1, 0, 'C', fill=True)
        pdf.cell(20, 8, "Total", 1, 1, 'C', fill=True)
        
        pdf.set_font("Arial", size=9)
        for i, r in dataframe.iterrows():
            pdf.cell(90, 8, str(r['Produto'])[:45].encode('latin-1','replace').decode('latin-1'), 1, 0, 'L')
            pdf.cell(30, 8, str(r.get('Padrao','-')), 1, 0, 'C')
            pdf.cell(25, 8, str(int(r['Qtd Compra'])), 1, 0, 'C')
            pdf.cell(25, 8, f"R$ {r['Custo']:.2f}", 1, 0, 'R')
            pdf.cell(20, 8, f"R$ {r['Total Item']:.2f}", 1, 1, 'R')
            
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 10, txt=f"TOTAL GERAL: R$ {total_geral:,.2f}", ln=True, align='R')
        
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
# 🛒 TELA DE COMPRAS
# =================================================================================
if tela == "Compras":
    st.header("🛒 Gestão de Compras e Abastecimento")
    
    col_forn, col_vazio = st.columns([1, 2])
    lista_fornecedores = ["Todos"] + sorted(list(set(df_db['Fornecedor'].dropna().unique())))
    forn_sel = col_forn.selectbox("Filtrar por Fornecedor:", lista_fornecedores)
    
    if forn_sel != st.session_state['ultimo_fornecedor']:
        st.session_state['compras_df_cache'] = None
        st.session_state['compras_key_ver'] += 1
        st.session_state['ultimo_fornecedor'] = forn_sel
        st.session_state['pedido_pdf'] = None
        st.session_state['pedido_xlsx'] = None

    st.divider()

    if st.button("🪄 Calcular Sugestão (Meta Global - Estoque Total)"):
        if forn_sel == "Todos": df_calc = df_db.copy()
        else: df_calc = df_db[df_db['Fornecedor'] == forn_sel].copy()
            
        df_calc['Meta Global'] = df_calc['Min_SA'] + df_calc['Min_SI']
        df_calc['Estoque Total'] = df_calc['Estoque_Central'] + df_calc['Estoque_SA'] + df_calc['Estoque_SI']
        df_calc['Sugestao'] = df_calc['Meta Global'] - df_calc['Estoque Total']
        df_calc['Sugestao'] = df_calc['Sugestao'].apply(lambda x: max(0, int(x)))
        df_calc['Qtd Compra'] = df_calc['Sugestao']
        
        st.session_state['compras_df_cache'] = df_calc
        st.session_state['compras_key_ver'] += 1
        st.success("Sugestão calculada!")
        st.rerun()

    if st.session_state['compras_df_cache'] is not None:
        df_view = st.session_state['compras_df_cache'].copy()
    else:
        if forn_sel == "Todos": df_view = df_db.copy()
        else: df_view = df_db[df_db['Fornecedor'] == forn_sel].copy()
        df_view['Meta Global'] = df_view['Min_SA'] + df_view['Min_SI']
        df_view['Estoque Total'] = df_view['Estoque_Central'] + df_view['Estoque_SA'] + df_view['Estoque_SI']
        df_view['Qtd Compra'] = 0

    busca_compra = st.text_input("🔍 Buscar Produto na Lista:", "")
    if busca_compra: df_view = df_view[df_view['Produto'].str.contains(busca_compra, case=False, na=False)]

    df_view['Valor Total'] = df_view['Qtd Compra'] * df_view['Custo']

    edited_df = st.data_editor(
        df_view[['Produto', 'Fornecedor', 'Padrao', 'Estoque Total', 'Meta Global', 'Custo', 'Qtd Compra']],
        column_config={
            "Produto": st.column_config.TextColumn(disabled=True),
            "Fornecedor": st.column_config.TextColumn(disabled=True),
            "Padrao": st.column_config.TextColumn("Emb.", disabled=True, width="small"),
            "Estoque Total": st.column_config.NumberColumn("Est. Atual", disabled=True, format="%d"),
            "Meta Global": st.column_config.NumberColumn("Meta", disabled=True, format="%d"),
            "Custo": st.column_config.NumberColumn("Custo Un.", disabled=True, format="R$ %.2f"),
            "Qtd Compra": st.column_config.NumberColumn("🛒 Comprar", min_value=0, step=1, format="%d")
        },
        use_container_width=True, hide_index=True, height=500, key=f"editor_compras_{st.session_state['compras_key_ver']}"
    )
    
    total_itens = edited_df['Qtd Compra'].sum()
    total_valor = (edited_df['Qtd Compra'] * edited_df['Custo']).sum()
    
    st.divider()
    c_tot1, c_tot2 = st.columns(2)
    c_tot1.metric("Itens a Comprar", int(total_itens))
    c_tot2.metric("Valor Estimado", f"R$ {total_valor:,.2f}")
    
    c_act1, c_act2, c_act3 = st.columns(3)
    
    if c_act1.button("📄 Gerar Pedido (Processar)", type="primary"):
        itens_compra = edited_df[edited_df['Qtd Compra'] > 0].copy()
        itens_compra['Total Item'] = itens_compra['Qtd Compra'] * itens_compra['Custo']
        
        if itens_compra.empty: st.warning("Nenhum item.")
        else:
            pdf_bytes = criar_pdf_compra(itens_compra, forn_sel, total_valor)
            st.session_state['pedido_pdf'] = pdf_bytes
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer: itens_compra.to_excel(writer, index=False, sheet_name='Pedido')
            st.session_state['pedido_xlsx'] = buf.getvalue()
            registrar_log("Vários", int(total_itens), "Pedido Compra", f"Forn: {forn_sel} | Valor: R$ {total_valor:.2f}")
            st.rerun()

    if st.session_state['pedido_pdf']:
        c_act2.download_button("⬇️ Baixar PDF", st.session_state['pedido_pdf'], "Pedido_Compra.pdf", "application/pdf")
        c_act3.download_button("⬇️ Baixar Excel", st.session_state['pedido_xlsx'], "Pedido_Compra.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =================================================================================
# 🚚 TELA DE TRANSFERÊNCIA (MANTIDA)
# =================================================================================
elif tela == "Transferencia":
    st.header("🚚 Transferência / Montagem de Carga")
    col_esquerda, col_direita = st.columns([1.5, 1])
    with col_esquerda:
        with st.container(border=True):
            st.markdown("### 1. Adicionar Itens")
            lojas_opcoes = ["Hospital Santo Amaro", "Hospital Santa Izabel"]
            destino_sel = st.selectbox("Para onde vai?", lojas_opcoes)
            if destino_sel != st.session_state['transf_last_dest']:
                st.session_state['transf_df_cache'] = None
                st.session_state['transf_key_ver'] += 1
                st.session_state['transf_last_dest'] = destino_sel
            if "Amaro" in destino_sel: col_estoque_loja = "Estoque_SA"; col_minimo = "Min_SA"
            else: col_estoque_loja = "Estoque_SI"; col_minimo = "Min_SI"
            
            if st.button("🪄 Preencher Sugestão"):
                df_calc = df_db[['Produto', 'Estoque_Central', col_estoque_loja, col_minimo]].copy()
                df_calc['Sugestao'] = df_calc[col_minimo] - df_calc[col_estoque_loja]
                df_calc['Sugestao'] = df_calc['Sugestao'].apply(lambda x: max(0, int(x)))
                df_calc['➡️ Enviar'] = df_calc[['Sugestao', 'Estoque_Central']].min(axis=1).astype(int)
                st.session_state['transf_df_cache'] = df_calc
                st.session_state['transf_key_ver'] += 1
                st.success("Preenchido!"); st.rerun()

            if st.session_state['transf_df_cache'] is not None: df_view = st.session_state['transf_df_cache'].copy()
            else:
                df_view = df_db[['Produto', 'Estoque_Central', col_estoque_loja, col_minimo]].copy()
                df_view['➡️ Enviar'] = 0
            
            busca = st.text_input("🔍 Buscar:", "")
            if busca: df_view = df_view[df_view['Produto'].str.contains(busca, case=False, na=False)]
            
            edited_df = st.data_editor(
                df_view,
                column_config={"Produto": st.column_config.TextColumn(disabled=True), "Estoque_Central": st.column_config.NumberColumn("Central", disabled=True, format="%d"), col_estoque_loja: st.column_config.NumberColumn("Loja", disabled=True, format="%d"), col_minimo: st.column_config.NumberColumn("Meta", disabled=True, format="%d"), "➡️ Enviar": st.column_config.NumberColumn(min_value=0, step=1, format="%d"), "Sugestao": None},
                use_container_width=True, hide_index=True, height=400, key=f"editor_transf_{st.session_state['transf_key_ver']}"
            )
            
            if st.button("📦 Adicionar à Carga", type="primary"):
                itens_enviar = edited_df[edited_df['➡️ Enviar'] > 0]
                if itens_enviar.empty: st.warning("Vazio.")
                else:
                    erro = False; temp_lista = []
                    for idx, row in itens_enviar.iterrows():
                        prod = row['Produto']; qtd = int(row['➡️ Enviar'])
                        idx_db = df_db[df_db['Produto'] == prod].index[0]
                        saldo_real = df_db.at[idx_db, 'Estoque_Central']
                        if qtd > saldo_real: st.error(f"Erro: {prod} só tem {int(saldo_real)}."); erro = True; break
                        df_db.at[idx_db, 'Estoque_Central'] -= qtd
                        if "Amaro" in destino_sel: df_db.at[idx_db, 'Estoque_SA'] += qtd
                        else: df_db.at[idx_db, 'Estoque_SI'] += qtd
                        registrar_log(prod, qtd, "Transferência", f"Central -> {destino_sel}")
                        temp_lista.append({"Destino": destino_sel, "Produto": prod, "Quantidade": qtd})
                    if not erro:
                        salvar_banco(df_db); st.session_state['carga_acumulada'].extend(temp_lista); st.session_state['transf_df_cache'] = None; st.session_state['transf_key_ver'] += 1; st.success(f"{len(temp_lista)} adicionados!"); st.rerun()

    with col_direita:
        with st.container(border=True):
            st.markdown("### 2. Carga Completa")
            if len(st.session_state['carga_acumulada']) > 0:
                with st.expander("❌ Remover Item"):
                    lista_display = [f"{i} | {d['Produto']} -> {d['Destino']} ({d['Quantidade']})" for i, d in enumerate(st.session_state['carga_acumulada'])]
                    itens_remover = st.multiselect("Selecione:", lista_display)
                    if st.button("Confirmar Remoção"):
                        indices = [int(s.split(" | ")[0]) for s in itens_remover]
                        for idx in indices:
                            item = st.session_state['carga_acumulada'][idx]
                            p = item['Produto']; q = item['Quantidade']; dest = item['Destino']
                            idx_db = df_db[df_db['Produto'] == p].index
                            if not idx_db.empty:
                                i_db = idx_db[0]; df_db.at[i_db, 'Estoque_Central'] += q 
                                if "Amaro" in dest: df_db.at[i_db, 'Estoque_SA'] -= q
                                else: df_db.at[i_db, 'Estoque_SI'] -= q
                        st.session_state['carga_acumulada'] = [val for i, val in enumerate(st.session_state['carga_acumulada']) if i not in indices]
                        salvar_banco(df_db); st.success("Estornado!"); st.rerun()

                df_carga = pd.DataFrame(st.session_state['carga_acumulada'])
                try: 
                    df_pivot = df_carga.pivot_table(index='Produto', columns='Destino', values='Quantidade', aggfunc='sum', fill_value=0).reset_index()
                    st.dataframe(df_pivot, use_container_width=True, hide_index=True, height=300)
                except: st.dataframe(df_carga, use_container_width=True)
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("✅ Finalizar"):
                    try:
                        pdf_bytes = criar_pdf_unificado(st.session_state['carga_acumulada'])
                        st.session_state['romaneio_pdf'] = pdf_bytes
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer: 
                            try: df_pivot.to_excel(writer, index=False, sheet_name='Romaneio')
                            except: df_carga.to_excel(writer, index=False, sheet_name='Romaneio')
                        st.session_state['romaneio_xlsx'] = buf.getvalue()
                        st.rerun()
                    except: st.error("Erro ao gerar arquivos.")
                if c_btn2.button("🗑️ Limpar"):
                    st.session_state['carga_acumulada'] = []; st.session_state['romaneio_pdf'] = None; st.rerun()
                if st.session_state['romaneio_pdf']:
                    st.success("Pronto!")
                    c_d1, c_d2 = st.columns(2)
                    c_d1.download_button("📄 PDF", st.session_state['romaneio_pdf'], "Romaneio.pdf", "application/pdf")
                    c_d2.download_button("📊 Excel", st.session_state['romaneio_xlsx'], "Romaneio.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else: st.info("Vazia.")

# =================================================================================
# 📦 TELA DE ESTOQUE
# =================================================================================
elif tela == "Estoque":
    st.header("📦 Atualização de Estoque (Contagem)")
    locais = {"Depósito Geral (Central)": "Estoque_Central", "Hospital Santo Amaro": "Estoque_SA", "Hospital Santa Izabel": "Estoque_SI"}
    c_loc, _ = st.columns([1,2])
    loc_sel = c_loc.selectbox("Local:", list(locais.keys()))
    col_dest = locais[loc_sel]
    
    with st.expander("📂 Importar Planilha de Contagem"):
        arq = st.file_uploader("Arquivo", type=["xlsx", "csv"], key="up_est")
        if arq:
            try:
                if arq.name.endswith('.csv'): df_t = pd.read_csv(arq, header=None)
                else: df_t = pd.read_excel(arq, header=None)
                hr = 0
                for i, r in df_t.head(20).iterrows():
                    if any("código" in str(x).lower() or "produto" in str(x).lower() for x in r.values): hr = i; break
                arq.seek(0)
                if arq.name.endswith('.csv'): df_n = pd.read_csv(arq, header=hr)
                else: df_n = pd.read_excel(arq, header=hr)
                cols = df_n.columns.tolist()
                c1, c2, c3 = st.columns(3)
                ic = next((i for i,c in enumerate(cols) if "cod" in str(c).lower()),0)
                inm = next((i for i,c in enumerate(cols) if "nom" in str(c).lower() or "prod" in str(c).lower()),0)
                iq = next((i for i,c in enumerate(cols) if "qtd" in str(c).lower() or "sald" in str(c).lower()),0)
                cc = c1.selectbox("Col Código", cols, index=ic); cn = c2.selectbox("Col Nome", cols, index=inm); cq = c3.selectbox("Col Qtd", cols, index=iq)
                if st.button("🚀 Processar"):
                    att = 0; novos = []
                    bar = st.progress(0)
                    for i, r in df_n.iterrows():
                        bar.progress((i+1)/len(df_n))
                        cod = str(r[cc]).strip(); nom = str(r[cn]).strip(); qtd = limpar_numero(r[cq])
                        if not nom or nom=='nan': continue
                        m = df_db[(df_db['Codigo']==cod)|(df_db['Codigo_Unico']==cod)]
                        if m.empty: m = df_db[df_db['Produto']==nom]
                        if not m.empty: df_db.at[m.index[0], col_dest] = qtd; att+=1
                        else:
                            n = {"Codigo": cod, "Produto": nom, "Categoria": "Novo", "Fornecedor": "Geral", "Padrao": "Un", "Custo": 0, "Min_SA":0, "Min_SI":0, "Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0}
                            n[col_dest] = qtd; df_db = pd.concat([df_db, pd.DataFrame([n])], ignore_index=True); novos.append(nom)
                    salvar_banco(df_db); bar.empty(); st.success(f"{att} Atualizados!"); 
                    if novos: st.warning(f"{len(novos)} Novos cadastrados.")
            except Exception as e: st.error(f"Erro: {e}")
    st.divider()
    filt = st.text_input("Filtrar:", placeholder="Nome...")
    v = df_db[df_db['Produto'].str.contains(filt, case=False, na=False)] if filt else df_db
    st.dataframe(v[['Codigo', 'Produto', 'Padrao', col_dest]], use_container_width=True, hide_index=True)

# =================================================================================
# 📋 TELA DE PRODUTOS
# =================================================================================
elif tela == "Produtos":
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
                        if any(x in c.lower() for x in k): return c
                    return None
                cc = fnd(['código','codigo']); cn = fnd(['produto 1','nome']); cf = fnd(['fornec']); cp = fnd(['padr']); ccst = fnd(['cust']); cma = fnd(['amaro']); cmi = fnd(['izabel'])
                cnt=0
                for i, r in df_n.iterrows():
                    p = str(r[cn]).strip()
                    if not p or p=='nan': continue
                    d = {"Codigo": str(r[cc]) if cc else "", "Produto": p, "Categoria": cat, "Fornecedor": str(r[cf]) if cf else "", "Padrao": str(r[cp]) if cp else "", "Custo": limpar_numero(r[ccst]) if ccst else 0, "Min_SA": limpar_numero(r[cma]) if cma else 0, "Min_SI": limpar_numero(r[cmi]) if cmi else 0}
                    m = df_db['Produto']==p
                    if m.any(): 
                        for k,v in d.items(): df_db.loc[m, k] = v
                    else: 
                        d.update({"Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0})
                        df_db = pd.concat([df_db, pd.DataFrame([d])], ignore_index=True)
                    cnt+=1
                salvar_banco(df_db); st.success(f"{cnt} processados!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
            
    st.divider()
    
    # BOTÃO ZONA DE PERIGO
    with st.expander("🔥 Apagar Tudo"):
        if st.button("🗑️ ZERAR BANCO"):
            cols = ["Codigo", "Codigo_Unico", "Produto", "Produto_Alt", "Categoria", "Fornecedor", "Padrao", "Custo", "Min_SA", "Min_SI", "Estoque_Central", "Estoque_SA", "Estoque_SI"]
            salvar_banco(pd.DataFrame(columns=cols)); st.success("Zerado!"); st.rerun()

    a1, a2, a3 = st.tabs(["☕ Café", "🍎 Perecíveis", "📋 Todos"])
    def show(c):
        d = df_db if c=="Todos" else df_db[df_db['Categoria']==c]
        if not d.empty:
            st.dataframe(d[['Codigo','Produto','Fornecedor','Padrao','Custo']], use_container_width=True, hide_index=True)
            cd1, cd2 = st.columns([4,1])
            sel = cd1.selectbox(f"Excluir ({c})", d['Produto'].unique(), key=f"d_{c}", index=None)
            if sel and cd2.button("🗑️", key=f"b_{c}"):
                salvar_banco(df_db[df_db['Produto']!=sel]); st.rerun()
        else: st.info("Vazio")
    with a1: show("Café"); with a2: show("Perecíveis"); with a3: show("Todos")

# --- OUTRAS TELAS ---
elif tela == "Vendas": st.title("📉 Vendas"); st.info("Em breve...")
elif tela == "Sugestoes": st.title("💡 Sugestões"); st.info("Em breve...")
