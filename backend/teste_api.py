import os
from groq import Groq
from dotenv import load_dotenv

# 1. Carrega a chave de API do arquivo .env (crie um arquivo .env com GROQ_API_KEY=sua_chave_aqui)
load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 2. Simulando o RAG: este é o texto que o Supabase teria encontrado no banco
contexto_recuperado = """
Art. 5 - As mudanças e obras nas unidades devem ser agendadas previamente com a administração. 
Os horários permitidos são de segunda a sexta-feira, das 08h00 às 18h00, e aos sábados das 08h00 às 12h00. 
É proibido realizar mudanças e obras aos domingos e feriados.
"""

# 3. A pergunta feita pelo morador no Front-end
pergunta_usuario = "Posso fazer minha mudança na segunda-feira de manhã?"

# 4. Construção do Prompt (O cérebro do assistente)
prompt_sistema = f"""
Você é o assistente virtual do Residencial Jardim das Acácias.
Responda à dúvida do morador utilizando APENAS a regra fornecida no contexto abaixo.
Se a resposta não estiver no contexto, diga que não encontrou a informação e oriente a procurar a administração.
Não invente informações. Seja educado e direto.

CONTEXTO RECUPERADO DO REGIMENTO:
{contexto_recuperado}
"""

print("Enviando pergunta para a IA (Groq - Llama 3)...")

# 5. Chamada à API
resposta = client.chat.completions.create(
    messages=[
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": pergunta_usuario}
    ],
    model="qwen/qwen3.8-27b", # Modelo super leve e rápido da Meta
    temperature=0.0,        # Zero criatividade = zero alucinação
    max_tokens=150
)

# 6. Exibe a resposta
print("\n🤖 Resposta do Bot:")
print(resposta.choices[0].message.content)