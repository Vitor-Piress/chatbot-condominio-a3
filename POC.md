# PRD — Chatbot RAG para Condomínio (POC)

Nov 4, 2026 · @João Victor

## 1. Visão geral e objetivos

Moradores fazem perguntas repetidas sobre regras, reservas e horários, e a administração responde uma a uma. O assistente responde essas dúvidas com base apenas nos documentos oficiais do condomínio. O condomínio usado na POC é fictício: Residencial Jardim das Acácias.

**Público:** moradores (usuários) e a administração (destinatária dos encaminhamentos).

**Objetivos mensuráveis:**

- Acertar pelo menos 80% dos casos de teste que têm resposta na base.
- Encaminhar 100% dos casos de emergência e pelo menos 90% dos casos fora de escopo.
- Acertar pelo menos 85% das intenções classificadas.
- Ter zero respostas com regra inexistente na base, verificadas caso a caso.
- Medir e reportar o tempo de resposta. A meta inicial é abaixo de 2 segundos sem LLM.

**Objetivo de controle de alucinação:** o bot não inventa regras. Ele responde somente com trechos recuperados da base, ou encaminha.

## 2. Escopo, intenções e encaminhamento

O assistente trata quatro intenções. Cada uma tem uma fonte definida na base da seção 4.

| Intenção | Exemplos de pergunta | Fonte na base |
| --- | --- | --- |
| Reservas de áreas comuns | Horário do salão? Quanto custa? Com quanto tempo reservar? | Regimento, capítulo de reservas |
| Regras de convivência | Qual o horário de silêncio? Posso ter animal? Pode usar a piscina à noite? | Regimento, capítulo de convivência |
| Mudanças e obras | Como agendar mudança? Em que horário posso fazer obra? | Regimento, capítulo de obras e mudanças |
| Garagem e serviços | Quantas vagas de visitante? Quando o lixo é coletado? | Convenção e regimento, capítulo de serviços |

**Fora do escopo:** cobranças, boleto e 2ª via; abertura de portões; dados pessoais de moradores; aplicação de multas; orientação jurídica; integração com WhatsApp, Telegram ou outros canais, que fica para uma fase futura. Nenhuma integração com sistemas reais é feita na POC.

**Critérios de encaminhamento humano** (verificados nesta ordem):

1. Mensagem com sinal de emergência (vazamento de gás, incêndio, ameaça, socorro médico). A resposta é fixa e indica 190, 192, 193 e a portaria.
2. Pergunta fora de escopo, identificada pelo classificador ou por palavras-chave de exclusão.
3. Confiança do classificador abaixo do limiar.
4. Nenhum trecho recuperado acima do limiar de similaridade.
5. Pedido de decisão sobre sanoção ou exceção. Vai para a administração.

## 3. Arquitetura e técnica de IA

A arquitetura é híbrida. Regras e um classificador próprio decidem a intenção. Uma recuperação própria busca o trecho da base. O LLM é opcional e só redige a partir dos trechos recuperados.

**Fluxo de processamento:**

1. **Pré-processamento:** a mensagem é minúsculizada, sem acentos e sem stopwords em português. Nesta etapa também se mantém o contexto dos últimos 3 turnos.
2. **Regras de emergência:** expressões regulares (regex) verificam sinais de emergência. Se houver match, a resposta fixa é devolvida e o fluxo para.
3. **Classificador de intenção:** TF-IDF com unigramas e bigramas e regressão logística, treinados com scikit-learn. Se a confiança for menor que o limiar, o caso vai para encaminhamento.
4. **Recuperação:** a equipe calcula a similaridade do cosseno entre a pergunta e os trechos da intenção classificada. Os 3 melhores trechos passam se a similaridade for maior que o limiar.
5. **Geração:** se houver chave de API, o Groq redige a resposta usando somente os trechos. Sem chave, o sistema devolve o trecho citado, sem texto gerado.
6. **Resposta ou abstinção:** sem trecho acima do limiar, a resposta é “Não encontrei essa informação na base; procure a administração”, com o contato.

**Fluxograma:** a ser desenhado com as seis etapas e as saídas de encaminhamento.

**Comparação com a alternativa:** a recuperação por embeddings (all-MiniLM-L6-v2 em ChromaDB) é testada contra a versão TF-IDF. A escolha vem da métrica hit@3 da seção 6.

**Descartadas:**

- **LLM puro com prompt:** não tem controle de alucinação e não demonstra técnica própria de IA.
- **Menu fixo de perguntas e respostas:** não escala para perguntas novas e não usa processamento de linguagem.

**Interface:** o Open WebUI pode ser usado como front-end, com login restrito a moradores cadastrados. O núcleo (regras, classificador e recuperação) fica no backend FastAPI, separado da interface.

## 4. Base de conhecimento e dados

A base é fictícia e escrita pela equipe, no formato de Regimento Interno e Convenção. Nenhum dado real de morador entra na POC. Se a equipe usar um documento real, precisa de autorização escrita do síndico e anonimização prévia.

**Estrutura:**

- Quatro arquivos em Markdown, um por capítulo do regimento, com artigos numerados (Art. 1, Art. 2 e assim por diante).
- Um CSV de perguntas rotuladas, com 80 linhas, 20 por intenção, em colunas: pergunta, intenção, origem (simulada ou da equipe).
- Um CSV de testes, separado do treino, com 24 casos (seção 6).

**Preparação:**

1. Segmentar por artigo, e não por número fixo de caracteres, para preservar a unidade da regra.
2. Testar também o chunking de 1000 caracteres com 200 de sobreposição. A escolha vem da métrica hit@3.
3. Separar 70% das perguntas para treino e 30% para validação. Os 24 casos de teste nunca entram no treino.
4. Versionar a base em Git com a tag `dados-v1`, e registrar a data de cada alteração.

**Privacidade e autorização:** a base não tem nomes, unidades ou valores reais de taxas. Os valores de exemplo são fictícios e marcados como tal.

**Vieses e limites:**

- A base reflete a visão de quem a escreveu, e não a prática real de um síndico.
- Perguntas com gíria, erros de digitação ou sem acentos tendem a ter desempenho pior. Isso deve ser testado nas reformulações.
- A cobertura é limitada aos artigos escritos. Perguntas sobre temas não escritos devem ser encaminhadas, nunca respondidas por suposição.

## 5. Requisitos e fluxo do usuário

**Requisitos funcionais:**

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| RF01 | Receber a mensagem e responder em interface web | Resposta em até 2 s sem LLM |
| RF02 | Manter o contexto dos últimos 3 turnos | Pergunta de acompanhamento (“E no sábado?”) respondida com o tema anterior |
| RF03 | Classificar a intenção entre as 4 categorias | Acurácia de pelo menos 85% no conjunto de validação |
| RF04 | Recuperar os 3 trechos mais similares dentro da intenção | Hit@3 de pelo menos 80% |
| RF05 | Citar o artigo usado em cada resposta | 100% das respostas com referência ao artigo |
| RF06 | Encaminhar emergências, fora de escopo e casos sem base | 100% das emergências e 90% dos fora de escopo |
| RF07 | Registrar cada decisão (intenção, score, trecho, resultado) em log | Log com todos os casos de teste |
| RF08 | Atualizar a base sem alterar código, reexecutando a ingestão | Mudança em um artigo refletida na resposta após a reexecução |
| RF09 | Acesso restrito a moradores cadastrados e aprovados | Usuário sem cadastro não acessa o chat |

**Requisitos não funcionais:**

- **Custo zero na POC:** o sistema roda localmente com Python 3.11 e sem API paga. O LLM pode usar o tier gratuito da Groq.
- **Chaves fora do repositório:** chaves ficam em arquivo `.env`, que não entra no Git.
- **Privacidade no LLM:** quando o Groq for usado, só trafega o prompt com os trechos recuperados, por TLS. Os documentos não são enviados a terceiros. A política de retenção de dados da Groq deve ser conferida na documentação vigente e citada, não assumida.
- **Modelo:** a equipe confirma a disponibilidade do modelo na Groq e registra o nome e a data de uso.
- **Desacoplamento:** o núcleo não depende da interface. Um canal futuro, como WhatsApp, usaria o mesmo endpoint.
- **Implantação:** execução por `requirements.txt` e Python 3.11 é obrigatória. Docker Compose é opcional, com o Open WebUI e o backend em contêineres separados e o `./chroma_db` mapeado como volume.

**Fluxo do usuário:**

1. O morador faz login e pergunta na interface, por exemplo: “Posso fazer churrasco na sexta?”
2. O sistema verifica emergência, classifica a intenção e recupera o artigo.
3. Se houver resposta, o sistema responde com o artigo citado.
4. Se não houver, o sistema diz que não encontrou a informação e oferece o contato da administração.
5. O morador pode pedir encaminhamento à administração em qualquer momento.

## 6. Plano de testes e métricas

Os testes usam 24 casos, guardados em planilha e separados do treino. Cada caso registra a pergunta, a categoria, a intenção esperada, o trecho esperado, a resposta obtida e o resultado.

| Categoria | Casos | Exemplo |
| --- | --- | --- |
| Pergunta esperada | 8 | Qual o horário de silêncio? |
| Reformulação | 6 | “até que horas pode fazer barulho” |
| Ambígua | 4 | “pode usar o espaço?”, sem dizer qual |
| Fora de escopo | 4 | “qual o valor do boleto de agosto?” |
| Emergência | 2 | “tem vazamento de gás no bloco B” |

**Métricas:**

| Métrica | Definição | Meta inicial |
| --- | --- | --- |
| Acurácia de intenção | Acertos / total de casos | 85% |
| Precisão e recall por intenção | Matriz de confusão de 4 classes | Recall de 80% ou mais em cada classe |
| Hit@3 | Casos em que o trecho correto está entre os 3 primeiros | 80% |
| Taxa de acerto da resposta | Respostas corretas e fundamentadas / casos respondíveis | 80% |
| Encaminhamento correto | Encaminhados / casos fora de escopo ou emergência | 100% em emergência, 90% fora de escopo |
| Alucinação | Respostas com afirmação ausente da base / respostas geradas | 0, verificado manualmente |
| Tempo de resposta | Mediana e p90 por pergunta | Medir e reportar |

**Experimentos comparativos:**

- TF-IDF contra embeddings na recuperação, medindo hit@3.
- Com LLM contra sem LLM, medindo taxa de acerto e alucinação.
- Chunking por artigo contra 1000 caracteres com sobreposição de 200.

**Análise de falhas:** os 3 erros analisados são escolhidos entre os casos com resultado “Erro” ou “Parcial”, com uma causa identificada para cada um. Por exemplo: palavra fora do vocabulário, artigo mal segmentado ou limiar mal calibrado.

## 7. Equipe e contribuições

A equipe tem de 2 a 4 integrantes. Cada um assume um papel verificável e explica a parte que fez.

| Papel | Responsabilidades | Evidência | Integrante |
| --- | --- | --- | --- |
| Levantamento e base de conhecimento | Problema, perguntas reais ou simuladas, redação dos artigos | Commits nos arquivos de dados e no PRD | \[nome\] |
| Implementação e integração | Regras, classificador, recuperação, API FastAPI, integração com LLM | Commits no código do backend | \[nome\] |
| Dados e testes | Limpeza, divisão treino e teste, planilha de 24 casos, métricas | Planilha de testes e scripts de avaliação | \[nome\] |
| Interface, documentação e validação | Interface, README, relatório e roteiro de demonstração | README, relatório e roteiro de demonstração | \[nome\] |

**Regras de registro:** cada integrante registra suas tarefas no quadro da equipe e assina sua seção no relatório. Cada um precisa responder a uma pergunta técnica sobre a sua parte.

## 8. Fases, riscos e decisões pendentes

**Fases:** os prazos são definidos pela equipe ou pelo professor.

| Fase | Entrega | Prazo |
| --- | --- | --- |
| 1 Problema | Nome, público, cenário, 3 a 5 problemas e 10 perguntas | \[a definir\] |
| 2 Dados | Base versionada, origem e 80 perguntas rotuladas | \[a definir\] |
| 3 Técnica | Arquitetura, fluxograma e comparação com alternativa | \[a definir\] |
| 4 Protótipo | Código executável, interface e README | \[a definir\] |
| 5 Avaliação | 24 testes, métricas e 3 falhas analisadas | \[a definir\] |
| 6 Defesa | Relatório, repositório, apresentação e demonstração | \[a definir\] |

**Riscos:**

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Modelo Groq descontinuado | Geração indisponível | Modo sem LLM é o padrão |
| Base pequena | Muitas abstensões | Ampliar perguntas e artigos antes de ajustar limiares |
| Limiar mal calibrado | Respostas erradas ou excesso de encaminhamentos | Calibrar no conjunto de validação, não no de teste |
| Tempo curto para a defesa | Demo incompleta | Gravar um vídeo de backup |

**Evolução prevista:** a base pode mudar sem alteração de código (RF08). Novas intenções, como 2ª via de boleto sem integração real, entram como fora de escopo até haver aprovação.

**Decisões pendentes:** nome do condomínio fictício, uso ou não do Groq e interface final (Open WebUI ou página própria).

## 9. Referências e declaração de uso de IA

**Referências (a conferir antes da entrega):**

- Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. arXiv:2005.11401.
- Manning, C., Raghavan, P., Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press. Capítulos sobre TF-IDF e similaridade do cosseno.
- Pedregosa, F. et al. (2011). *Scikit-learn: Machine Learning in Python*. JMLR, 12.
- Reimers, N.; Gurevych, I. (2019). *Sentence-BERT*. arXiv:1908.10084.
- Modelo all-MiniLM-L6-v2, ficha técnica no Hugging Face.
- Documentação da Groq, com política de dados e lista de modelos vigentes.
- Lei nº 10.406/2002 (Código Civil), título sobre condomínio edilício.

**Recursos externos e modelos usados:** scikit-learn, FastAPI, ChromaDB e sentence-transformers, se a comparação com embeddings for mantida. O Groq só entra se a equipe usar a geração.

**Declaração de uso de IA generativa:** \[descrever o uso, como revisão de texto, sugestão de código ou geração de perguntas simuladas\]. Todo código e texto foi revisado e testado pela equipe.
