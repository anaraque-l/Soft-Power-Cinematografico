import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Carrega as variáveis de ambiente (Sua chave do Google)
load_dotenv()

# Configura a IA do Chatbot
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

@st.cache_data
def carregar_dados_do_banco():
    conn = sqlite3.connect('soft_power.db')
    df = pd.read_sql_query("SELECT * FROM analises_geopoliticas", conn)
    conn.close()
    return df

# Configuração da página do Streamlit
st.set_page_config(page_title="Mapa do Soft Power", page_icon="🌍", layout="wide")

df = carregar_dados_do_banco()

st.title("🌍 Mapa Global do Soft Power Cinematográfico")
st.markdown("Como os países usam o cinema e suas narrativas para projetar influência cultural no mundo.")

st.divider()

# Criar globo terrestre 3D com Plotly (Mapa de Calor)
fig = px.scatter_geo(
    df, 
    lat='latitude', lon='longitude', 
    hover_name='pais',
    size='popularidade', # Tamanho muda com o Soft Power
    color='popularidade', # Cor muda com o Soft Power
    color_continuous_scale="Reds", 
    projection="orthographic"
)

# Mantemos a borda branca, mas sem sobrescrever o tamanho e a cor do mapa de calor!
fig.update_traces(marker=dict(line=dict(width=1, color='white')))

fig.update_geos(
    showocean=True, oceancolor="#0E1117",
    showland=True, landcolor="#262730",
    showcountries=True, countrycolor="#454545",
    framecolor="#0E1117", coastlinecolor="#0E1117"
)

fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    paper_bgcolor="#0E1117", geo_bgcolor="#0E1117"
)

# Dividir a tela em duas colunas
col1, col2 = st.columns([2, 1])

with col1:
    # Mostra o Globo na tela
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Análise Diplomática 🔎")
    
    # Menu para escolher o país
    pais_selecionado = st.selectbox("Selecione um país:", df['pais'].tolist())
    dados_pais = df[df['pais'] == pais_selecionado].iloc[0]

    # Mostra a imagem e a métrica lado a lado
    img_col, metric_col = st.columns([1, 1])
    with img_col:
        # Se a coluna 'poster' existir no banco, ele mostra a imagem
        if 'poster' in dados_pais and pd.notna(dados_pais['poster']):
            st.image(dados_pais['poster'], use_container_width=True)
    with metric_col:
        if 'popularidade' in dados_pais:
            st.metric(label="Termômetro Cultural", value=f"{dados_pais['popularidade']:.1f} 🔥")

    # Informações de texto
    st.markdown(f"**📍 Polo Cultural:** {dados_pais['polo_cultural']}")
    st.markdown(f"**🎬 Filmes Populares:** {dados_pais['titulo']}")
    
    # Análise principal
    st.info(dados_pais['analise_soft_power'])

    st.divider()
    
    # 🤖 Agente Especialista (Chatbot RAG)
    st.subheader("🤖 Agente Especialista")
    st.markdown("Faça perguntas cruzando dados de engenharia e geopolítica.")
    
    pergunta = st.chat_input(f"Pergunte sobre os dados de {pais_selecionado}...")
    
    if pergunta:
        # Exibe a pergunta do usuário
        st.chat_message("user").write(pergunta)
        
        # Cria o contexto com os dados brutos que o Pandas puxou do banco
        contexto = f"País: {pais_selecionado}. Polo: {dados_pais['polo_cultural']}. Sinopses reais do país: {dados_pais['sinopse']}."
        
        # Junta a pergunta do usuário com a instrução do sistema e o contexto da base de dados
        prompt_agente = (
            f"Você é um engenheiro de dados e analista geopolítico. "
            f"Responda a esta pergunta: '{pergunta}'. "
            f"Use ESTRITAMENTE este contexto do nosso banco de dados: {contexto}. Seja direto e profissional."
        )
        
        # Chama o modelo e exibe a resposta
        with st.spinner("Analisando o banco de dados..."):
            resposta = llm.invoke(prompt_agente)
            st.chat_message("ai").write(resposta.content)