import pandas as pd 
import os 
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
load_dotenv()



print("🧠 Iniciando a análise de Soft Power com IA...")

df = pd.read_csv('dados_pre_processados.csv')

# 3. Configurar o "Cérebro" (O modelo de IA Gemini, rápido e gratuito)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

prompt_template = PromptTemplate.from_template(
    "Você é um especialista em relações internacionais."
                                "Baseado nos seguintes filmes do país {pais}: {filmes}, "
    "escreva um parágrafo curto (máximo 4 linhas) explicando como este país "
    "usa essas narrativas para projetar seu Soft Power (influência cultural) no mundo.")

#Criar a "Chain" ( corrente do langchain que liga a instrução ao modelo de IA)

chain = prompt_template | llm 

# aplicar a ai aos países usando um loop 

analises = []

for index, row in df.iterrows():
    #juntando titulo e sinopse para ia 
    textos_filmes = row['titulo'] + "-" + row['sinopse']

    #rodando a ia 

    resposta = chain.invoke({"pais": row['pais'], "filmes": textos_filmes})
    analises.append(resposta.content)
#salvar os resultados em uma nova coluna no nosso banco de dados 
df['analise_soft_power'] = analises
df.to_csv('analises_soft_power.csv', index=False)

print("✅ Sucesso! A IA analisou todos os países e o arquivo 'dados_finais_com_ia.csv' foi salvo.")