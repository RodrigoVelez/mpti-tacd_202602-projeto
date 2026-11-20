"""ETAPA 4. GRAVAÇÃO DOS RESULTADOS

Grava em data/perguntas/:
    metadados.json            dados gerais da geração (PDF, modelo, prompt, versões, custo)
    01-Classificacao/
        01-Classificacao.json todas as informações do tema: perguntas, evidências,
                              conferência e a resposta original da API (auditoria)
        01-Classificacao.txt  só a pergunta, a resposta e onde achar a resposta no PDF
    02-Diagnostico-e-Medicao/ ... (uma pasta por tema)
Também refaz a conferência dos temas já gerados, sem usar a API (opção --verificar).
"""

import hashlib
import json
import platform
from datetime import datetime
from pathlib import Path

import anthropic
import pymupdf

from . import etapa3_conferencia
from .configuracao import (CACHE_TTL, ESFORCO, MIN_NOVA_CLASSIFICACAO, MODELO, PASTA_SAIDA, PASTAS_TEMAS,
                           PERMITIR_FALLBACK, RAIZ, TEMAS, arquivo_do_tema)
from .etapa1_extracao import hash_arquivo
from .etapa2_geracao import INSTRUCOES_SISTEMA


def localizacao_texto(item: dict) -> str:
    """Ex.: 'Página 36, seção 3.2.3. Classificação, parágrafo 2, linhas 1 a 4'."""
    partes = []
    for ev in item["evidencias"]:
        loc = ev.get("localizacao_verificada")
        if not loc:
            partes.append("não encontrada no PDF")
            continue
        linhas = (f"linha {loc['linha_inicial']}" if loc["linha_inicial"] == loc["linha_final"]
                  else f"linhas {loc['linha_inicial']} a {loc['linha_final']}")
        unidade = "parágrafo" if loc["tipo"] == "paragrafo" else "tabela"
        secao = f", seção {loc['secao']}" if loc.get("secao") else ""
        partes.append(f"Página {loc['pagina']}{secao}, {unidade} {loc['numero']}, {linhas}")
    return " e ".join(partes)


def salvar_txt(dados: dict, caminho: Path) -> None:
    blocos = []
    for item in dados["itens"]:
        bloco = [f"Id: {item['id']} | Status: {item.get('status_verificacao', '')}",
                 f"Pergunta: {item['pergunta']}",
                 f"Resposta: {item['resposta_referencia']}"]
        if item.get("resposta_leiga"):
            bloco.append(f"Resposta leiga: {item['resposta_leiga']}")
        bloco.append(f"Localização: {localizacao_texto(item)}")
        if item.get("status_verificacao") == "revisar":
            bloco.append("Atenção: resposta não confirmada no PDF. Revisar manualmente.")
        blocos.append("\n".join(bloco))
    caminho.write_text("\n\n".join(blocos) + "\n", encoding="utf-8")


def salvar_tema(chave: str, dados: dict) -> None:
    """Grava o JSON (com a resposta original da API no fim) e o TXT do tema."""
    ordem = ["tema", "descricao", "chamadas", "itens", "respostas_api"]
    ordenado = {k: dados[k] for k in ordem if k in dados}
    ordenado.update({k: v for k, v in dados.items() if k not in ordenado})
    arquivo_json = arquivo_do_tema(chave, "json")
    arquivo_json.write_text(json.dumps(ordenado, ensure_ascii=False, indent=2), encoding="utf-8")
    salvar_txt(dados, arquivo_do_tema(chave, "txt"))


def executar(resultado: dict, caminho_pdf: Path, texto_numerado: str) -> None:
    """Grava os arquivos de cada tema e o metadados.json geral."""
    print("[4/4] Gravando os resultados...")
    temas = resultado["temas"]
    for chave, dados in temas.items():
        salvar_tema(chave, dados)

    custo = sum(c["custo_usd"] for d in temas.values() for c in d["chamadas"])
    metadados = {
        "ultima_execucao": resultado["momento"].isoformat(timespec="seconds"),
        "pdf": caminho_pdf.name,
        "pdf_sha256": hash_arquivo(caminho_pdf),
        "texto_numerado_sha256": hashlib.sha256(texto_numerado.encode("utf-8")).hexdigest(),
        "modelo_solicitado": MODELO,
        "esforco": ESFORCO,
        "fallback_permitido": PERMITIR_FALLBACK,
        "cache_ttl": CACHE_TTL,
        "min_nova_classificacao": MIN_NOVA_CLASSIFICACAO,
        "temas": {PASTAS_TEMAS[c]: {"descricao": TEMAS[c], "perguntas": len(d["itens"]),
                                    "custo_usd": round(sum(x["custo_usd"] for x in d["chamadas"]), 4),
                                    "chamadas": d["chamadas"]} for c, d in temas.items()},
        "custo_total_usd": round(custo, 4),
        "instrucoes_sistema": INSTRUCOES_SISTEMA,
        "versoes": {"python": platform.python_version(), "anthropic": anthropic.__version__,
                    "pymupdf": pymupdf.VersionBind},
    }
    (PASTA_SAIDA / "metadados.json").write_text(json.dumps(metadados, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(d["itens"]) for d in temas.values())
    print(f"\nConcluído. {total} perguntas em {len(temas)} temas. Custo total das chamadas: US$ {custo:.2f}")
    print(f"Resultados em: {PASTA_SAIDA.relative_to(RAIZ)}/")
    for chave in temas:
        print(f"   {PASTAS_TEMAS[chave]}/  ({PASTAS_TEMAS[chave]}.txt e {PASTAS_TEMAS[chave]}.json)")
    print("   metadados.json  dados gerais da geração")


def executar_verificacao(unidades: list[dict]) -> None:
    """Refaz a conferência de todos os temas já gerados e regrava o JSON e o TXT. Não usa a API."""
    from .etapa2_geracao import ler_tema_gravado
    gerados = [c for c in TEMAS if arquivo_do_tema(c, "json").exists()]
    if not gerados:
        print(f"Nenhum tema gerado em {PASTA_SAIDA.relative_to(RAIZ)}/ para conferir.")
        return
    indice = etapa3_conferencia.indexar(unidades)
    todos = []
    for chave in gerados:
        dados = ler_tema_gravado(chave)
        for item in dados["itens"]:
            etapa3_conferencia.conferir_item(item, indice, unidades)
        salvar_tema(chave, dados)
        todos.extend(dados["itens"])
    print(f"Conferência refeita em {len(gerados)} tema(s): {', '.join(PASTAS_TEMAS[c] for c in gerados)}")
    print(etapa3_conferencia.resumo_verificacao(todos))
