"""CONFIGURAÇÃO DO EXPERIMENTO

Altere aqui, e somente aqui, se precisar mudar algum parâmetro.
Todos os valores ficam registrados nos metadados de cada execução.
"""

from pathlib import Path

# Pastas do projeto (este arquivo fica em src/geracao_perguntas/)
RAIZ = Path(__file__).resolve().parents[2]
PDF_PADRAO = RAIZ / "docs" / "Diretriz" / "Diretrizes Brasileiras de Hipertensão Arterial – 2025.pdf"
PASTA_PROCESSADO = RAIZ / "data" / "processado"
PASTA_SAIDA = RAIZ / "data" / "perguntas"
ARQUIVO_ENV = RAIZ / ".env"

# Modelo e geração
MODELO = "claude-opus-5-5"
ESFORCO = "medium"           # profundidade do raciocínio do modelo: low, medium, high, xhigh ou max
MAX_TOKENS = 64000           # limite de tokens da resposta de cada chamada
PERGUNTAS_POR_TEMA = 30      # 5 temas x 30 = 150 perguntas (a proposta seleciona 10 por tema)
MIN_NOVA_CLASSIFICACAO = 12  # mínimo de perguntas sobre a nova classificação (120-129 / 80-84 mmHg)

# Se o modelo principal recusar a tarefa por política de segurança, a API pode
# repetir a mesma chamada em outro modelo. O modelo que de fato respondeu fica
# registrado nos metadados. Mude para False para desligar esse comportamento.
PERMITIR_FALLBACK = True

# Preços por milhão de tokens em US$ (conferir em https://www.anthropic.com/pricing)
PRECO_ENTRADA = 4.00
PRECO_SAIDA = 20.00
PRECO_ESCRITA_CACHE = 5.00      # cache de 5 minutos: 1,25 x o preço de entrada
PRECO_ESCRITA_CACHE_1H = 8.00   # cache de 1 hora: 2 x o preço de entrada
PRECO_LEITURA_CACHE = 0.20

# Duração do cache do documento. Com 1 hora, todas as chamadas de uma execução
# leem o documento do cache, mesmo que cada chamada demore vários minutos.
CACHE_TTL = "1h"

# Temas da proposta do projeto (Tarefa 6)
TEMAS = {
    "classificacao": "Classificação da pressão arterial (normal, pré-hipertensão, estágios 1, 2 e 3, hipertensão sistólica e diastólica isolada) e o que mudou em relação à diretriz de 2020",
    "diagnostico_medicao": "Diagnóstico e medição da pressão arterial (técnica de medida, consultório, MAPA, MRPA, avental branco, hipertensão mascarada, exames)",
    "metas_tratamento": "Metas de tratamento (valores de pressão a alcançar, quando iniciar remédio, acompanhamento)",
    "nao_medicamentoso": "Medidas sem remédio (sal, alimentação, peso, atividade física, álcool, tabagismo, sono, estresse)",
    "situacoes_especiais": "Situações especiais (idosos, gestantes, crianças e adolescentes, diabetes, doença renal, AVC, urgência e emergência hipertensiva)",
}

# Limites da página (em pontos) onde ficam cabeçalho e rodapé desta diretriz
LIMITE_CABECALHO = 60
LIMITE_RODAPE = 760

# Pasta e nome dos arquivos de cada tema em data/perguntas/ (na ordem dos temas)
PASTAS_TEMAS = {
    "classificacao": "01-Classificacao",
    "diagnostico_medicao": "02-Diagnostico-e-Medicao",
    "metas_tratamento": "03-Metas-de-Tratamento",
    "nao_medicamentoso": "04-Medidas-sem-Remedio",
    "situacoes_especiais": "05-Situacoes-Especiais",
}


def arquivo_do_tema(chave: str, extensao: str) -> Path:
    """Ex.: arquivo_do_tema("classificacao", "json") -> data/perguntas/01-Classificacao/01-Classificacao.json"""
    nome = PASTAS_TEMAS[chave]
    return PASTA_SAIDA / nome / f"{nome}.{extensao}"
