import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Gestão 3.3", layout="wide")
ARQUIVO_DADOS = "banco_dados.csv"

# --- ESTADO DA NAVEGAÇÃO ---
if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = "Estoque" # Começa no Estoque agora

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        cols = ["Produto", "Categoria", "Local", "Saldo", "Minimo", "Custo", "Fornecedor"]
        df = pd.DataFrame(columns=cols)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    return pd.read_csv(ARQUIVO_DADOS)

def salvar_novo_produto(produto, categoria, fornecedor, custo, minimo):
    df = carregar_dados()
    if produto in df['Produto'].values:
        return False, "Produto já existe!"
    novo_item = {
        "Produto": produto, "Categoria": categoria, "Local": "Estoque Central",
        "Saldo": 0, "Minimo": minimo, "Custo": custo, "Fornecedor": fornecedor
    }
    pd.concat([df, pd.DataFrame([novo_item])], ignore_index=True).to_csv(ARQUIVO_DADOS, index=False)
    return True, "Cadastrado!"

def excluir_produto(produto):
    df = carregar_dados()
    df = df[df['Produto'] != produto]
    df.to_csv(ARQUIVO_DADOS, index=False)

def atualizar_estoque(produto, quantidade, tipo_operacao):
    df = carregar_dados()
    # Encontra a linha do produto
    index = df[df['Produto'] == produto].index
    
    if not index.empty:
        idx = index[0]
        saldo_atual = df.at[idx, 'Saldo']
        
        if tipo_operacao == "entrada":
            df.at[idx, 'Saldo'] = saldo_atual + quantidade
            msg = f"Adicionado +{quantidade} ao estoque de {produto}."
            tipo_msg = "sucesso"
        elif tipo_operacao == "baixa":
            if quantidade > saldo_atual:
                return False, "Erro: Você está tentando baixar mais do que tem no estoque!"
            df.at[idx, 'Saldo'] = saldo_atual - quantidade
            msg = f"Removido -{quantidade} do estoque de {produto}."
            tipo_msg = "sucesso"
            
        df.to_csv(ARQUIVO_DADOS, index=False)
        return True, msg
    return False, "Produto não encontrado."

# --- MENU DE ÍCONES (CARROSSEL FIXO) ---
st.markdown("<h1 style='text-align: center; color: #4F8BF9;'>Sistema Integrado</h1>", unsafe_allow_html=True)
st.write("")

c1, c2, c3, c4, c5, c6 = st.columns(6)

def criar_botao(coluna, nome, icone):
    # Se for a página atual, destaca o botão (deixa primário)
    tipo = "primary" if st.session_state['pagina_atual'] == nome else "secondary"
    with coluna:
        if st.button(f"{icone}\n{nome}", use_container_width=True, type=tipo):
            st.session_state['pagina_atual'] = nome

criar_botao(c1, "Estoque", "📦")
criar_botao(c2, "Transferência", "🚚")
criar_botao(c3, "Compras", "🛒")
criar_botao(c4, "Produtos", "📋")
criar_botao(c5, "Vendas", "📉")
criar_botao(c6, "Sugestões", "💡")

st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)

# --- CONTEÚDO DAS TELAS ---
pagina = st.session_state['pagina_atual']
df_atual = carregar_dados()

# 1. TELA DE ESTOQUE (AGORA FUNCIONANDO!)
if pagina == "Estoque":
    st.subheader("📦 Movimentação de Estoque")
    
    if df_atual.empty:
        st.warning("Nenhum produto cadastrado. Vá em 'Produtos' primeiro.")
    else:
        # Colunas para organizar a tela: Esquerda (Ação) | Direita (Visualização)
        col_acao, col_view = st.columns([1, 2])
        
        with col_acao:
            with st.container(border=True):
                st.markdown("**Registrar Movimentação**")
                
                # Seletor de Produto
                lista_prods = df_atual['Produto'].unique()
                prod_sel = st.selectbox("Selecione o Produto:", lista_prods)
                
                # Mostra saldo atual pequeno para ajudar
                saldo_atual = df_atual.loc[df_atual['Produto'] == prod_sel, 'Saldo'].values[0]
                st.caption(f"Saldo Atual: **{saldo_atual}** unidades/kg")
                
                # Input de Quantidade
                qtd = st.number_input("Quantidade:", min_value=1, value=1)
                
                # Botões de Ação lado a lado
                b1, b2 = st.columns(2)
                if b1.button("➕ Entrada", use_container_width=True):
                    ok, msg = atualizar_estoque(prod_sel, qtd, "entrada")
                    if ok: st.success("Entrada realizada!"); st.rerun()
                    else: st.error(msg)
                    
                if b2.button("➖ Baixa", use_container_width=True):
                    ok, msg = atualizar_estoque(prod_sel, qtd, "baixa")
                    if ok: st.success("Baixa realizada!"); st.rerun()
                    else: st.error(msg)

        with col_view:
            st.markdown("**Visão Geral do Estoque**")
            # Tabela limpa apenas com o essencial
            st.dataframe(
                df_atual[['Produto', 'Saldo', 'Categoria', 'Local']], 
                use_container_width=True, 
                hide_index=True,
                height=400
            )

# 2. TELA DE TRANSFERÊNCIA
elif pagina == "Transferência":
    st.info("🚧 Em breve: Mover produtos do Central para Hospitais.")

# 3. TELA DE COMPRAS
elif pagina == "Compras":
    st.info("🚧 Em breve: Gerar lista do que precisa comprar.")

# 4. TELA DE PRODUTOS
elif pagina == "Produtos":
    st.subheader("📋 Cadastro")
    aba_cafe, aba_pereciveis = st.tabs(["☕ Café", "🍎 Perecíveis"])
    
    def renderizar_cadastro(categoria_nome):
        with st.container(border=True):
            c_nome, c_forn = st.columns(2)
            nome = c_nome.text_input("Produto", key=f"n_{categoria_nome}")
            forn = c_forn.text_input("Fornecedor", key=f"f_{categoria_nome}")
            c_custo, c_min, c_btn = st.columns([1, 1, 1])
            custo = c_custo.number_input("Custo", 0.0, step=0.1, key=f"c_{categoria_nome}")
            minimo = c_min.number_input("Mínimo", 1, key=f"m_{categoria_nome}")
            st.write("") 
            if c_btn.button("Salvar", key=f"b_{categoria_nome}", use_container_width=True):
                ok, msg = salvar_novo_produto(nome, categoria_nome, forn, custo, minimo)
                if ok: st.success("Salvo!"); st.rerun()
                else: st.error(msg)
        
        df_filtro = df_atual[df_atual['Categoria'] == categoria_nome]
        if not df_filtro.empty:
            st.dataframe(df_filtro[['Produto', 'Saldo', 'Minimo']], use_container_width=True, hide_index=True)
            p_del = st.selectbox("Excluir:", df_filtro['Produto'].unique(), key=f"del_{categoria_nome}", index=None)
            if p_del and st.button("Confirmar Exclusão", key=f"bd_{categoria_nome}"):
                excluir_produto(p_del); st.rerun()

    with aba_cafe: renderizar_cadastro("Café")
    with aba_pereciveis: renderizar_cadastro("Perecíveis")

# 5. TELA DE VENDAS
elif pagina == "Vendas":
    st.info("🚧 Em breve: Upload de planilha.")

# 6. TELA DE SUGESÕES
elif pagina == "Sugestões":
    st.info("🚧 Em breve: IA de gestão.")
