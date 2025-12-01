import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sistema Gestão 31.0", layout="wide", initial_sidebar_state="collapsed")
ARQUIVO_DADOS = "banco_dados.csv"
ARQUIVO_LOG = "historico_log.csv"

# --- INICIALIZAÇÃO DE ESTADO ---
def init_state():
    if 'romaneio_pdf' not in st.session_state: st.session_state['romaneio_pdf'] = None
    if 'tela_atual' not in st.session_state: st.session_state['tela_atual'] = "Transferencia"
    if 'selecao_exclusao' not in st.session_state: st.session_state['selecao_exclusao'] = []
    # Estado para o editor de dados (para limpar após envio)
    if 'editor_transf' not in st.session_state: st.session_state['editor_transf'] = None

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

def criar_pdf_romaneio(dataframe, destino):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt=f"ROMANEIO DE TRANSFERENCIA - {destino.upper()}", ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(190, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(5)
        
        # Cabeçalho
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(120, 10, "Produto", 1, 0, 'C')
        pdf.cell(30, 10, "Qtd", 1, 0, 'C')
        pdf.cell(40, 10, "Unid", 1, 1, 'C')
        
        # Dados
        pdf.set_font("Arial", size=10)
        for index, row in dataframe.iterrows():
            prod = str(row['Produto']).encode('latin-1', 'replace').decode('latin-1')[:50]
            padrao = str(row.get('Padrao', '-')).encode('latin-1', 'replace').decode('latin-1')
            qtd = str(row['Quantidade'])
            
            pdf.cell(120, 10, prod, 1, 0, 'L')
            pdf.cell(30, 10, qtd, 1, 0, 'C')
            pdf.cell(40, 10, padrao, 1, 1, 'C')
            
        pdf.ln(20)
        pdf.cell(90, 10, "_"*30, 0, 0, 'C'); pdf.cell(10, 10, "", 0, 0, 'C'); pdf.cell(90, 10, "_"*30, 0, 1, 'C')
        pdf.cell(90, 5, "Expedicao (Central)", 0, 0, 'C'); pdf.cell(10, 5, "", 0, 0, 'C'); pdf.cell(90, 5, "Recebedor", 0, 1, 'C')
        
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
# 🚚 TELA DE TRANSFERÊNCIA (EM GRADE/LISTA)
# =================================================================================
if tela == "Transferencia":
    st.header("🚚 Transferência em Lote")
    
    # 1. Seletor de Loja
    lojas_opcoes = ["Hospital Santo Amaro", "Hospital Santa Izabel"]
    destino_sel = st.selectbox("Selecione o Destino:", lojas_opcoes)
    
    # Define colunas baseado no destino
    if "Amaro" in destino_sel:
        col_estoque_loja = "Estoque_SA"
        col_minimo = "Min_SA"
    else:
        col_estoque_loja = "Estoque_SI"
        col_minimo = "Min_SI"
        
    st.info(f"Você está enviando do **Central** para **{destino_sel}**.")
    
    # 2. Prepara os dados para a tabela
    # Cria uma cópia para edição
    df_view = df_db[['Produto', 'Padrao', 'Estoque_Central', col_estoque_loja, col_minimo]].copy()
    
    # Renomeia para ficar bonito na tabela
    df_view = df_view.rename(columns={
        'Estoque_Central': 'Disponível Central',
        col_estoque_loja: 'Atual na Loja',
        col_minimo: 'Mínimo Ideal'
    })
    
    # Adiciona coluna de envio zerada (se não existir no estado)
    if st.session_state['editor_transf'] is None:
        df_view['➡️ Enviar'] = 0.0
    else:
        # Se já tiver editado algo, tenta manter (mas cuidado com troca de loja)
        df_view['➡️ Enviar'] = 0.0 

    # 3. Tabela Editável (Data Editor)
    # Filtro de busca para facilitar
    busca = st.text_input("🔍 Buscar produto na lista:", "")
    if busca:
        df_view = df_view[df_view['Produto'].str.contains(busca, case=False, na=False)]
    
    edited_df = st.data_editor(
        df_view,
        column_config={
            "Produto": st.column_config.TextColumn(disabled=True),
            "Padrao": st.column_config.TextColumn("Unid.", disabled=True, width="small"),
            "Disponível Central": st.column_config.NumberColumn(disabled=True, format="%.0f"),
            "Atual na Loja": st.column_config.NumberColumn(disabled=True, format="%.0f"),
            "Mínimo Ideal": st.column_config.NumberColumn(disabled=True, format="%.0f"),
            "➡️ Enviar": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.0f")
        },
        use_container_width=True,
        hide_index=True,
        height=500,
        key=f"editor_{destino_sel}" # Chave única por loja para resetar ao trocar
    )
    
    st.divider()
    
    # 4. Botão de Processar
    if st.button("✅ Confirmar Envio e Gerar Romaneio", type="primary"):
        # Filtra apenas o que tem quantidade > 0
        itens_enviar = edited_df[edited_df['➡️ Enviar'] > 0]
        
        if itens_enviar.empty:
            st.warning("Nenhuma quantidade preenchida para envio.")
        else:
            erro_saldo = False
            lista_romaneio = []
            
            # Validação e Processamento
            for index, row in itens_enviar.iterrows():
                prod = row['Produto']
                qtd = row['➡️ Enviar']
                disponivel = row['Disponível Central']
                
                if qtd > disponivel:
                    st.error(f"Erro: '{prod}' tem apenas {disponivel} no Central. Você tentou enviar {qtd}.")
                    erro_saldo = True
                else:
                    # Atualiza o DataFrame Principal (df_db)
                    idx_db = df_db[df_db['Produto'] == prod].index[0]
                    
                    df_db.at[idx_db, 'Estoque_Central'] -= qtd # Tira do Central
                    
                    # Soma no destino correto
                    if "Amaro" in destino_sel:
                        df_db.at[idx_db, 'Estoque_SA'] += qtd
                    else:
                        df_db.at[idx_db, 'Estoque_SI'] += qtd
                        
                    lista_romaneio.append({"Produto": prod, "Quantidade": qtd, "Padrao": row['Padrao']})
                    registrar_log(prod, qtd, "Transferência", f"Central -> {destino_sel}")
            
            if not erro_saldo:
                salvar_banco(df_db)
                
                # Gera PDF
                df_rom = pd.DataFrame(lista_romaneio)
                pdf_bytes = criar_pdf_romaneio(df_rom, destino_sel)
                st.session_state['romaneio_pdf'] = pdf_bytes
                
                st.success("Transferência realizada com sucesso!")
                
    # 5. Download (Se houver PDF gerado)
    if st.session_state['romaneio_pdf']:
        st.download_button(
            label="📄 Baixar Romaneio (PDF)",
            data=st.session_state['romaneio_pdf'],
            file_name=f"Romaneio_{destino_sel[:3]}_{datetime.now().strftime('%H%M')}.pdf",
            mime="application/pdf"
        )
        if st.button("🔄 Nova Transferência"):
            st.session_state['romaneio_pdf'] = None
            st.rerun()

# =================================================================================
# 📦 TELA DE ESTOQUE (MANTIDA)
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
                    if any("código" in str(x).lower() or "produto" in str(x).lower() for x in r.values): 
                        hr = i; break
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
                    for i, r in df_n.iterrows():
                        bar.progress((i+1)/len(df_n))
                        cod = str(r[cc]).strip(); nom = str(r[cn]).strip(); qtd = limpar_numero(r[cq])
                        if not nom or nom=='nan': continue
                        m = df_db[(df_db['Codigo']==cod)|(df_db['Codigo_Unico']==cod)]
                        if m.empty: m = df_db[df_db['Produto']==nom]
                        if not m.empty:
                            df_db.at[m.index[0], col_dest] = qtd; att+=1
                        else:
                            n = {"Codigo": cod, "Produto": nom, "Categoria": "Novo", "Fornecedor": "Geral", "Padrao": "Un", "Custo": 0, "Min_SA":0, "Min_SI":0, "Estoque_Central":0, "Estoque_SA":0, "Estoque_SI":0}
                            n[col_dest] = qtd; df_db = pd.concat([df_db, pd.DataFrame([n])], ignore_index=True); novos.append(nom)
                    salvar_banco(df_db); bar.empty()
                    st.success(f"{att} Atualizados!"); 
                    if novos: st.warning(f"{len(novos)} Novos cadastrados.")
            except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    filt = st.text_input("Filtrar:", placeholder="Nome...")
    v = df_db[df_db['Produto'].str.contains(filt, case=False, na=False)] if filt else df_db
    st.dataframe(v[['Codigo', 'Produto', 'Padrao', col_dest]], use_container_width=True, hide_index=True)

# =================================================================================
# 📋 TELA DE PRODUTOS (MANTIDA)
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
                    d = {
                        "Codigo": str(r[cc]) if cc else "", "Produto": p, "Categoria": cat,
                        "Fornecedor": str(r[cf]) if cf else "", "Padrao": str(r[cp]) if cp else "",
                        "Custo": limpar_numero(r[ccst]) if ccst else 0, "Min_SA": limpar_numero(r[cma]) if cma else 0, "Min_SI": limpar_numero(r[cmi]) if cmi else 0
                    }
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
    with a1: show("Café"); 
    with a2: show("Perecíveis"); 
    with a3: show("Todos")

# --- OUTRAS TELAS ---
elif tela == "Compras": st.title("🛒 Compras"); st.info("Próxima etapa...")
elif tela == "Vendas": st.title("📉 Vendas"); st.info("Em breve...")
elif tela == "Sugestoes": st.title("💡 Sugestões"); st.info("Em breve...")
