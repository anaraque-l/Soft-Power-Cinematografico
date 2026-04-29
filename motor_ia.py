import pandas as pd 
import os 
from dotenv import load_dotenv
from sqlalchemy import create_engine
from langchain_google_genai import ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
from langchain_core.prompts import PromptTemplate

load_dotenv()

# Conectar ao banco e ler os dados
engine = create_engine('sqlite:///soft_power.db')
df = pd.read_sql('filmes_limpos', engine)

print(f"🧠 Iniciando análise de {len(df)} países...")

# Configurar o modelo de IA com os filtros relaxados
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    }
)

# NOVO PROMPT: Menos focado em política dura, mais focado em cultura cinematográfica
# NOVO PROMPT: Usando a técnica de "Sandboxing" para evitar o bloqueio
prompt_template = PromptTemplate.from_template(
    "Atenção: Os textos a seguir são sinopses de obras puramente fictícias de entretenimento.\n"
    "<FICCAO>\n{filmes}\n</FICCAO>\n\n"
    "Atuando como um analista de geopolítica, leia essas sinopses de filmes do país {pais} e "
    "escreva um parágrafo curto (máximo 4 linhas) explicando como os temas (mesmo que sejam de ação, "
    "crime ou guerra) ajudam a projetar o Soft Power e a influência cultural deste país no mundo."
)

chain = prompt_template | llm 

analises = []

for index, row in df.iterrows():
    print(f"🎬 Lendo filmes de: {row['pais']}...")
    textos_filmes = row['titulo'] + " - " + row['sinopse']
    
    try:
        # Rodando a IA
        resposta = chain.invoke({"pais": row['pais'], "filmes": textos_filmes})
        texto_analise = resposta.content
        
        # Se o Google devolver um texto completamente vazio (O bloqueio persistente)
        if not texto_analise.strip():
            print(f"⚠️ Alerta: O Google censurou a resposta para {row['pais']}.")
            texto_analise = "Análise indisponível: As sinopses deste país acionaram o filtro de segurança máximo (Censura) da Inteligência Artificial do Google."
            
    except Exception as e:
        print(f"❌ Erro crítico ao analisar {row['pais']}: {e}")
        texto_analise = "Erro de conexão com a Inteligência Artificial."

    analises.append(texto_analise)

# Salvando os resultados na NOVA tabela do banco de dados 
df['analise_soft_power'] = analises
df.to_sql('analises_geopoliticas', engine, if_exists='replace', index=False)

print("✅ Sucesso Absoluto! A tabela 'analises_geopoliticas' foi criada no banco de dados e está pronta para o Streamlit.")