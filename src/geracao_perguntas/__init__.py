"""Processo de geração do conjunto de perguntas e respostas de referência.

Cada etapa fica em um módulo próprio e é chamada pelo script principal
src/gerar_perguntas.py, na ordem:

    configuracao.py         parâmetros do experimento (modelo, temas, preços, caminhos)
    etapa1_extracao.py      lê o PDF e numera página, parágrafo, tabela e linha (sem IA)
    etapa2_geracao.py       pede as perguntas ao Claude pela API
    etapa3_conferencia.py   confere no PDF cada localização informada (sem IA)
    etapa4_resultados.py    grava CSV, JSON e metadados da execução
"""
