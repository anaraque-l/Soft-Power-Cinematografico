import pandas as pd 

print('Iniciando o processo de pré-processamento dos dados... ')

#carregar os dados brutos 

df = pd.read_csv('filmes.csv')

#remover espaços em brando pré IA
df['sinopse'] = df['sinopse'].str.strip()
df['titulo'] = df['titulo'].str.strip()

#Fazer agrupamento por país. 
#títulos e sinopses do mesmo país em uma única linha. 
df_agrupado = df.groupby(['pais', 'polo_cultural', 'latitude', 'longitude']).agg({
    'titulo': lambda x: ' '.join(x),
    'sinopse': lambda x: ' '.join(x)
}).reset_index()

#salvar dados limpos
df_agrupado.to_csv('dados_pre_processados.csv', index=False)

print("✅ Sucesso! Pipeline finalizado. O arquivo 'dados_limpos.csv' foi criado.")