# Notas para o artigo

Decisões e ideias tomadas durante o projeto que precisam entrar no artigo (modelo SBC, até 6 páginas
de conteúdo + 1 de referências). Organizado pelas seções exigidas na diretriz da Tarefa 10.
Cada item diz de onde veio e quando.

## Metodologia

### Escolha dos LLMs (26 e 27/11/2026)

Decisão: **três modelos avaliados** — Qwen 2.5 7B, Llama 3.1 8B e Gemma 3 4B — mais o bge-m3
(embeddings) e o Claude Opus 5.5 (geração das perguntas e juiz). O Llama 3.1 8B foi incluído em
27/11 porque passa em todos os critérios e é o modelo pequeno mais usado na literatura; sem ele,
a pergunta "por que não o Llama?" ficaria sem resposta. Total: 3 modelos × 2 condições × 50
perguntas = 300 respostas e 300 avaliações do juiz.

**Motivação de origem:** continuidade com Aguzzi et al. (2025), o trabalho relacionado mais próximo
(RAG com modelos pequenos e abertos em hipertensão), que testou as famílias Gemma 3 e Qwen 2.5/3 em
versões de 0,5B a 1,5B. Achados deles: Gemma 3 teve ganhos significativos com RAG; Qwen 3 já ia bem
sem RAG. Aqui as famílias foram levadas ao maior tamanho que roda no computador da pesquisa.

**O que a literatura usa na faixa de 3B a 14B:**

| Estudo | Modelos pequenos usados |
| --- | --- |
| RAG em diretrizes de câncer de mama (PARK et al., 2026) | Qwen2.5-14B, Llama 3 8B, OpenBioLLM-8B |
| Fine-tuning × RAG em saúde (PINGUA et al., 2025) | Llama 3.1 8B, Gemma 2 9B, Mistral 7B, Qwen2.5 7B, Phi-3.5 |
| RAG em diretriz de fibrilação atrial (MACABALES et al., 2026) | Llama 3 8B, Phi-3 Mini, Qwen3 4B (no Colab) |
| Revalida, em português (SEVERINO et al., 2025) | 31 modelos; entre os pequenos, Llama 3 8B foi o melhor (53,9%) |
| ENAMED 2026, em português (DA SILVA et al., 2026) | 7 modelos abertos; Gemma 3 4B foi o mais fraco (47,47%) |

Leitura da tabela:
- Qwen 2.5 e Gemma 3 aparecem na literatura, inclusive em português.
- Llama 3.1 8B é o modelo pequeno mais usado e o melhor entre os pequenos no Revalida. Em Pingua et
  al. (2025), o Qwen ficou atrás dos demais na maioria das métricas (registrar com honestidade).
- O Gemma 3 4B ser o mais fraco em português médico é um argumento a favor de incluí-lo: em
  diretrizes clínicas, o ganho do RAG se concentra nos modelos-base mais fracos (VOLLMER et al.,
  2026). Ter modelos fortes e um fraco mostra se esse padrão se repete.

**Critérios de seleção definidos antes do experimento:**

| Critério | Por quê | Qwen 2.5 7B | Llama 3.1 8B | Gemma 3 4B | Mistral 7B | Qwen 3 8B | Meditron 7B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pesos abertos e execução local em 16 GB | Privacidade e custo zero (Aguzzi) | Sim | Sim | Sim | Sim | Sim | Sim |
| Português oficialmente suportado pelo fabricante | Perguntas e diretriz em português | Sim | Sim | Sim | Não | Sim | Não |
| Treinado antes da diretriz de 2025 | Medir o conhecimento antigo (P1) | Sim | Sim | Sim | Sim | Sim | Sim |
| Contexto de pelo menos 8 mil tokens | Cabem a pergunta e os 4 trechos | Sim | Sim | Sim | Sim | Sim | Não (2 mil) |
| Sem "modo de raciocínio" por padrão | Respostas diretas e comparáveis | Sim | Sim | Sim | Sim | Não | Sim |
| Já usado em estudos de RAG ou saúde | Comparabilidade | Sim | Sim | Sim | Sim | Sim | Sim |

Resultado: passam em todos os critérios o Qwen 2.5 7B, o Llama 3.1 8B e o Gemma 3 4B. Mistral e
Meditron saem por não terem português oficial (o Meditron também pelo contexto de 2 mil tokens). O
Qwen 3 sai pelo modo de raciocínio (gera texto longo de "pensamento" antes da resposta) e fica como
trabalho futuro, já que Aguzzi et al. (2025) mostraram que ele depende menos do RAG.

**A conferir antes de escrever:** suporte a português e tamanho de contexto de cada modelo nos
cartões oficiais (Qwen/Qwen2.5-7B-Instruct, meta-llama/Llama-3.1-8B-Instruct, google/gemma-3-4b-it,
mistralai/Mistral-7B-Instruct, Qwen/Qwen3-8B, epfl-llm/meditron-7b); nome exato e quantização de
cada modelo usado (`ollama show <modelo>`).

**Outros pontos para a seção:**
- Qwen 2.5 7B (Alibaba, set/2024, Apache 2.0, ~5 GB quantizado); Llama 3.1 8B (Meta, jul/2024,
  licença Llama 3.1 Community, ~5 GB); Gemma 3 4B (Google, mar/2025, ~3 GB). Todos anteriores à
  diretriz de 2025 (publicada em set/2025).
- bge-m3 (BAAI, 2024): embeddings multilíngues feitos para busca, 1.024 dimensões; usado também por
  Vach et al. (2025).
- Os modelos do Ollama são quantizados e podem ter desempenho um pouco menor que o original.
- Ambiente: MacBook Air 13" (Apple M5, 16 GB de memória), Ollama, temperatura 0, zero-shot.

**Referências (completar dados ABNT: volume, número, páginas, DOI):**
- AGUZZI et al. Journal of Medical Systems, v. 49, art. 159, 2025. (já na proposta)
- DA SILVA, F. L. F. et al. Performance of Large Language Models on the Brazilian National Medical
  Education Examination: comparative benchmark study. JMIR Medical Education, 2026.
  https://consensus.app/papers/details/w:67804501-99ae-4222-8541-1fa42177dfe3/
- MACABALES, C. E. M. et al. Open-Source LLMs for Evidence-Grounded Clinical Question Answering: a RAG
  framework based on the 2024 ESC Atrial Fibrillation Guidelines. IEEE CSPA, 2026.
  https://consensus.app/papers/details/w:f2b36cab-53c6-485a-a3c9-29d8efae250a/
- PARK, C. M. et al. Can Small Open-Source Language Models With Retrieval-Augmented Generation Match
  GPT-4 Performance in Breast Cancer Clinical Decision Support? JCO Clinical Cancer Informatics, 2026.
  https://consensus.app/papers/details/w:ae7e0993-96d1-46a4-b152-2d67376246f1/
- PINGUA, B. et al. Medical LLMs: fine-tuning vs. retrieval-augmented generation. Bioengineering, 2025.
  https://consensus.app/papers/details/w:712451ed-7511-4788-9124-92de963727c1/
- SEVERINO, J. V. B. et al. Benchmarking open-source large language models on Portuguese Revalida
  multiple-choice questions. BMJ Health & Care Informatics, 2025.
  https://consensus.app/papers/details/w:98438556-6fad-476c-b914-fac543786a78/
- VOLLMER, A. et al. A Self-Controlled Benchmark of Retrieval-Augmented Generation for Large Language
  Models on Clinical Guideline Questions. Diagnostics, 2026.
  https://consensus.app/papers/details/w:b0f38f30-e11b-4d4b-a9c1-df643e29c45b/
- VACH, M. et al. Clinical Neuroradiology, 2025. (já levantado na Tarefa 6)

### Armazenamento e busca dos vetores (26/11/2026)

- A proposta previa pgvector (Docker). Trocado por matriz numpy salva em arquivo (`data/rag/`):
  busca exata por similaridade de cosseno sobre todos os trechos, mesmo resultado do pgvector sem
  índice aproximado, e roda no Google Colab (que não tem Docker). Explicar a troca em uma frase.

## Considerações e trabalhos futuros

### Modelo especializado em saúde: MedGemma (26/11/2026)

- Ideia: comparar o Gemma 3 4B com sua versão médica, o **MedGemma 4B** (Google, mai/2025), para
  responder "o que ajuda mais um modelo pequeno: treino em medicina ou a diretriz certa via RAG?".
- Por que ficou de fora: o suporte ao português não é documentado. O cartão do modelo diz apenas
  que "a limitation of our evaluations was that they included primarily English language prompts".
  Além disso, foi treinado antes da diretriz de 2025 e acrescentaria 100 respostas e 100 avaliações
  do juiz (custo de API), o que não cabia no prazo.
- Sugestão de texto: "Modelos médicos como o MedGemma não foram incluídos porque o suporte ao
  português não é documentado (as avaliações do fabricante usaram principalmente perguntas em
  inglês). Compará-los ao uso de RAG é um trabalho futuro."
- Referência: GOOGLE. MedGemma 1 model card. Disponível em:
  https://developers.google.com/health-ai-developer-foundations/medgemma/model-card-v1.
  Acesso em: 26 nov. 2026.

### Robustez a erros de digitação e gírias (desde a proposta)

- Mantida como limitação (comentário do Prof. Alex na Tarefa 6). Referência levantada: Cho et al.
  (2024), "Typos that broke the RAG's back".
