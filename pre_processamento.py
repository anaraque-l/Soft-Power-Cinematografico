import pandas as pd
import requests
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

print('🚀 Iniciando extração de dados do TMDB e criação do banco...')

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# 1. Nossa lista base de polos culturais (Substitui o CSV)
# Usamos o código ISO 3166-1 do país (ex: 'BR', 'KR', 'FR', 'US') para a API entender
paises_alvo = [
    {'codigo': 'BR', 'pais': 'Brasil', 'polo_cultural': 'América Latina', 'latitude': -14.235, 'longitude': -51.925},
    {'codigo': 'KR', 'pais': 'Coreia do Sul', 'polo_cultural': 'Ásia Oriental', 'latitude': 35.907, 'longitude': 127.766},
    {'codigo': 'FR', 'pais': 'França', 'polo_cultural': 'Europa Ocidental', 'latitude': 46.227, 'longitude': 2.213},
    {'codigo': 'US', 'pais': 'Estados Unidos', 'polo_cultural': 'América do Norte', 'latitude': 37.090, 'longitude': -95.712},
    {'codigo' : 'JP', 'pais': 'Japão', 'polo_cultural': 'Ásia Oriental', 'latitude': 36.204, 'longitude': 138.252}
]

dados_filmes = []

# 2. Loop para buscar os dados na API
for local in paises_alvo:
    print(f"🎬 Buscando filmes do país: {local['pais']}...")
    
    # Endpoint 'discover' da API: Traz os filmes mais populares do país escolhido
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_origin_country={local['codigo']}&language=pt-BR&sort_by=popularity.desc"
    
    resposta = requests.get(url)
    
    if resposta.status_code == 200:
        # Pega apenas os 5 filmes mais populares 
        filmes = resposta.json().get('results', [])[:5] 
        
        for filme in filmes:
            # Só adiciona se o filme tiver sinopse
            if filme.get('overview'): 
                dados_filmes.append({
                    'pais': local['pais'],
                    'polo_cultural': local['polo_cultural'],
                    'latitude': local['latitude'],
                    'longitude': local['longitude'],
                    'titulo': filme.get('title'),
                    'sinopse': filme.get('overview'),'popularidade': filme.get('popularity'),
            'poster': f"https://image.tmdb.org/t/p/w500{filme.get('poster_path')}" if filme.get('poster_path') else None
                })
    else:
        print(f"⚠️ Erro ao buscar {local['pais']}. Código: {resposta.status_code}")

# 3. Transformar em Pandas DataFrame
df = pd.DataFrame(dados_filmes)

# 4. Agrupamento (igual você já fazia)
df_agrupado = df.groupby(['pais', 'polo_cultural', 'latitude', 'longitude']).agg({
    'titulo': lambda x: ' | '.join(x),
    'sinopse': lambda x: ' '.join(x),'popularidade': 'mean',
    'poster': 'first' # Pega a imagem do filme mais popular da lista
}).reset_index()

# 5. Salvar no Banco de Dados SQLite
engine = create_engine('sqlite:///soft_power.db')
df_agrupado.to_sql('filmes_limpos', engine, if_exists='replace', index=False)

print(f"✅ Sucesso! O banco 'soft_power.db' foi atualizado com {len(df_agrupado)} polos culturais direto da API.")