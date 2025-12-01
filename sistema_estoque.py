import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Sistema Gestão 2.0", layout="wide")
ARQUIVO_DADOS = "banco_dados.csv"

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        # Criando colunas essenciais para o cadastro
        cols = ["Produto", "Categoria", "Local", "Saldo", "Minimo", "Custo", "Fornecedor"]
        df = pd.DataFrame(columns=cols)
        df.to_csv(ARQUIVO_DADOS, index=False)
        return df
    return pd.read_csv(ARQUIVO_DADOS)

def salvar_novo_produto(produto, categoria, fornecedor, custo, minimo):
    df = carregar_dados()
    if produto in df['Produto'].values:
        return False, "Produto já existe!"
    
    # Cria a nova linha
    novo_item = {
        "Produto": produto,
        "Categoria": categoria,
        "Local": "Estoque Central", # Todo cadastro nasce no Central
        "Saldo": 0, # Começa zerado
        "Minimo": minimo,
        "Custo": custo,
        "Fornecedor": fornecedor
    }
    
    df = pd.concat([df, pd.DataFrame([novo_item])], ignore_index=True)
    df.to_csv(ARQUIVO_DADOS, index=False)
    return True, "Produto cadastrado com sucesso!"

def excluir_produto(produto):
    df = carregar_dados()
    df = df[df['Produto'] != produto]
    df.to_csv(ARQUIVO_DADOS, index=False)

# --- INTERFACE PRINCIPAL ---
df_atual = carregar_dados()

st.sidebar.title("📍 Navegação")
escolha = st.sidebar.radio(
    "Menu Principal",
    [
        "1. 📦 Estoque",
        "2. 🚚 Transferência",
        "3. 🛒 Compras",
        "4. 📋 Controle de Produtos",
        "5. 📉 Vendas",
        "6. 💡 Sugestões"
    ],
    index=3 # Já começa na tela 4 para facilitar o cadastro
)
st.sidebar.divider()

# --- LÓGICA DAS TELAS ---

# ... (Telas 1, 2, 3 ficam vazias por enquanto) ...
if "1." in escolha: st.title("📦 Estoque"); st.info("Em breve...")
elif "2." in escolha: st.title("🚚 Transferência"); st.info("Em breve...")
elif "3." in escolha: st.title("🛒 Compras"); st.info("Em breve...")

# --- TELA 4: CONTROLE DE PRODUTOS (O FOCO AGORA) ---
elif "4. 📋 Controle de Produtos" in escolha:
    st.header("📋 Cadastro e Controle de Produtos")
    
    aba_cafe, aba_pereciveis = st.tabs(["☕ Café & Insumos", "🍎 Perecíveis"])
    
    # Função para desenhar a tela dentro de cada aba (evita repetir código)
    def renderizar_aba(categoria_nome):
        # 1. Área de Cadastro
        with st.expander(f"➕ Cadastrar Novo Item em {categoria_nome}"):
            with st.form(key=f"form_{categoria_nome}"):
                c1, c2 = st.columns(2)
                nome = c1.text_input("Nome do Produto")
                forn = c2.text_input("Fornecedor Principal")
                
                c3, c4 = st.columns(2)
                custo = c3.number_input("Custo Unitário (R$)", min_value=0.0, step=0.10)
                minimo = c4.number_input("Estoque Mínimo (Alerta)", min_value=1, step=1)
                
                if st.form_submit_button("💾 Salvar Produto"):
                    if nome:
                        sucesso, msg = salvar_novo_produto(nome, categoria_nome, forn, custo, minimo)
                        if sucesso: st.success(msg); st.rerun()
                        else: st.error(msg)
                    else:
                        st.warning("Preencha o nome do produto.")

        # 2. Tabela de Visualização
        st.divider()
        st.markdown(f"**Itens Cadastrados: {categoria_nome}**")
        
        # Filtra apenas os produtos dessa aba
        df_filtro = df_atual[df_atual['Categoria'] == categoria_nome]
        
        if not df_filtro.empty:
            # Mostra tabela simples
            st.dataframe(
                df_filtro[['Produto', 'Fornecedor', 'Custo', 'Minimo']], 
                use_container_width=True,
                hide_index=True
            )
            
            # Área de Exclusão
            prod_excluir = st.selectbox("Selecione para Excluir:", df_filtro['Produto'].unique(), key=f"del_{categoria_nome}", index=None, placeholder="Selecione um item...")
            if prod_excluir:
                if st.button(f"🗑️ Excluir {prod_excluir}", key=f"btn_del_{categoria_nome}"):
                    excluir_produto(prod_excluir)
                    st.success("Excluído!")
                    st.rerun()
        else:
            st.info("Nenhum produto cadastrado nesta categoria.")

    # Executa a função para cada aba
    with aba_cafe:
        renderizar_aba("Café")
        
    with aba_pereciveis:
        renderizar_aba("Perecíveis")

# ... (Telas 5 e 6 vazias por enquanto) ...
elif "5." in escolha: st.title("📉 Vendas"); st.info("Em breve...")
elif "6." in escolha: st.title("💡 Sugestões"); st.info("Em breve...")
