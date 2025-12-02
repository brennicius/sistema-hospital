import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Configuração Básica
st.set_page_config(page_title="Teste de Conexão", layout="wide")

st.title("🟢 O Sistema Reviveu!")
st.write("Se você está lendo isso, o erro de instalação acabou.")

# Teste de Conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.success("✅ Conexão com o Robô do Google: OK")
    
    # Tenta ler
    df = conn.read(worksheet="Estoque", ttl=0)
    st.write("### Dados da sua Planilha:")
    st.dataframe(df)

except Exception as e:
    st.error(f"❌ O site abriu, mas a conexão falhou: {e}")
    st.info("Verifique se o arquivo secrets.toml está configurado no painel do Streamlit.")
