import streamlit as st 
import pandas as pd 
import plotly.express as px

#configuração da página do stremlit 
st.set_page_config(page_title="Mapa do Soft Power", page_icon="🌍", layout="wide")


st.title("🌍 Mapa Global do Soft Power Cinematográfico")
st.markdown("Como os países usam o cinema e suas narrativas para projetar influência cultural no mundo.")

st.divider()
#carregar os dados com as análises de soft power
#decorar para maior fluidez do site 
@st.cache_data
def carregar_dados():
    return pd.read_csv('analises_soft_power.csv')
df = carregar_dados()

#criar globo terrest 3d com plotly 

fig = px.scatter_geo(
    df, lat= 'latitude', lon='longitude', hover_name='pais', projection="orthographic", # Essa é a palavra mágica que transforma o mapa em um Globo 3D!
)

# estilização cyberpunk/dark no globo

fig.update_traces(marker=dict(size=15, color='#FF4B4B', line=dict(width=2, color='white')))
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

# 4. Dividir a tela em duas colunas (Esquerda: Globo | Direita: Análises)
col1, col2 = st.columns([2, 1])

with col1:
    # Mostra o Globo na tela
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Análise Diplomática 🔎")
    # Cria um menu para você escolher o país
    pais_selecionado = st.selectbox("Selecione um país:", df['pais'].tolist())
    
    # Filtra os dados apenas para o país que você selecionou
    dados_pais = df[df['pais'] == pais_selecionado].iloc[0]
    
    # Mostra os resultados na tela
    st.markdown(f"**📍 Polo Cultural:** {dados_pais['polo_cultural']}")
    st.markdown(f"**🎬 Filmes Analisados:** {dados_pais['titulo']}")
    
    # Coloca a análise da IA numa caixa de destaque
    st.info(dados_pais['analise_soft_power'])