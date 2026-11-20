"""ETAPA 1. EXTRAÇÃO E NUMERAÇÃO DO PDF (determinística, sem IA)

Lê o PDF e divide o texto em unidades: títulos, parágrafos e tabelas, cada uma
com página, número e linhas numeradas. Gera os arquivos de data/processado/:
    <nome>_numerado.txt     texto numerado, enviado ao Claude na etapa 2
    <nome>_estrutura.jsonl  a mesma numeração em JSON Lines, usada na etapa 3
Também confere a integridade: o total de letras e números do corpo do PDF deve
ser igual ao total extraído (nada perdido e nada duplicado).
"""

import hashlib
import json
import re
from pathlib import Path

import pymupdf

from .configuracao import LIMITE_CABECALHO, LIMITE_RODAPE, PASTA_PROCESSADO, RAIZ

PADRAO_TITULO = re.compile(r"^\d+(\.\d+)*\.\s+\S")


def hash_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _dentro(x: float, y: float, area) -> bool:
    return area[0] <= x <= area[2] and area[1] <= y <= area[3]


def _palavras_da_area(palavras: list, area) -> list[int]:
    """Índices das palavras cujo centro fica dentro da área."""
    return [i for i, w in enumerate(palavras) if _dentro((w[0] + w[2]) / 2, (w[1] + w[3]) / 2, area)]


def _juntar(palavras: list, indices: list[int]) -> str:
    """Junta as palavras na ordem de leitura (bloco, linha, posição da palavra)."""
    return " ".join(palavras[i][4] for i in sorted(indices, key=lambda i: palavras[i][5:8]))


def extrair_documento(caminho_pdf: Path) -> list[dict]:
    """Devolve as unidades do documento (títulos, parágrafos e tabelas) na ordem de leitura.

    Cada unidade é um dicionário com:
        pagina, tipo ("titulo", "paragrafo" ou "tabela"), numero (na página),
        secao, linhas e, só nas tabelas, celulas (lista de linhas, cada uma com suas células).
    Nas tabelas, cada linha da tabela é uma linha numerada, com as células separadas por " | ".
    """
    unidades = []
    secao_atual = ""
    with pymupdf.open(caminho_pdf) as doc:
        for pagina in doc:
            num_pagina = pagina.number + 1
            contador = {"paragrafo": 0, "tabela": 0}
            palavras = pagina.get_text("words")
            tabelas = [tb for tb in pagina.find_tables().tables
                       if LIMITE_CABECALHO <= tb.bbox[1] < LIMITE_RODAPE]
            tabelas_emitidas = set()

            def emitir_paragrafo(linhas: list[str]) -> None:
                nonlocal secao_atual
                if not linhas:
                    return
                if len(linhas) <= 3 and PADRAO_TITULO.match(linhas[0]):
                    secao_atual = " ".join(linhas)
                    unidades.append({"pagina": num_pagina, "tipo": "titulo", "numero": None,
                                     "secao": secao_atual, "linhas": linhas})
                    return
                contador["paragrafo"] += 1
                unidades.append({"pagina": num_pagina, "tipo": "paragrafo", "numero": contador["paragrafo"],
                                 "secao": secao_atual, "linhas": linhas})

            def emitir_tabela(indice: int) -> None:
                tabelas_emitidas.add(indice)
                linhas, celulas = [], []
                # Às vezes o PyMuPDF reconhece a linha da tabela mas não uma das células.
                # Nesse caso a célula é reconstruída com a largura da mesma coluna nas outras linhas.
                colunas = {}
                for linha_tabela in tabelas[indice].rows:
                    for k, c in enumerate(linha_tabela.cells):
                        if c and k not in colunas:
                            colunas[k] = (c[0], c[2])
                usadas = set()  # palavras já atribuídas a alguma célula desta tabela
                for linha_tabela in tabelas[indice].rows:
                    _, ry0, _, ry1 = linha_tabela.bbox
                    por_celula = {k: [i for i in _palavras_da_area(palavras, c) if i not in usadas]
                                  for k, c in enumerate(linha_tabela.cells) if c}
                    usadas.update(i for indices in por_celula.values() for i in indices)
                    for k, c in enumerate(linha_tabela.cells):
                        if c is None and k in colunas:  # célula não reconhecida: só palavras ainda sem célula
                            area = (colunas[k][0], ry0, colunas[k][1], ry1)
                            por_celula[k] = [i for i in _palavras_da_area(palavras, area) if i not in usadas]
                            usadas.update(por_celula[k])
                    textos = [_juntar(palavras, por_celula[k]) for k in sorted(por_celula)]
                    textos = [x for x in textos if x]
                    if textos:
                        celulas.append(textos)
                        linhas.append(" | ".join(textos))
                if linhas:
                    contador["tabela"] += 1
                    unidades.append({"pagina": num_pagina, "tipo": "tabela", "numero": contador["tabela"],
                                     "secao": secao_atual, "linhas": linhas, "celulas": celulas})

            for bloco in pagina.get_text("dict")["blocks"]:
                if bloco["type"] != 0:  # imagem
                    continue
                y0 = bloco["bbox"][1]
                if y0 < LIMITE_CABECALHO or y0 >= LIMITE_RODAPE:
                    continue
                pendentes = []
                for linha in bloco["lines"]:
                    x0, y0l, x1, y1 = linha["bbox"]
                    cx, cy = (x0 + x1) / 2, (y0l + y1) / 2
                    indice = next((i for i, tb in enumerate(tabelas) if _dentro(cx, cy, tb.bbox)), None)
                    if indice is not None:
                        # a linha pertence a uma tabela: fecha o parágrafo anterior e emite a tabela uma vez
                        emitir_paragrafo(pendentes)
                        pendentes = []
                        if indice not in tabelas_emitidas:
                            emitir_tabela(indice)
                        continue
                    texto = " ".join("".join(s["text"] for s in linha["spans"]).split())
                    if texto:
                        pendentes.append(texto)
                emitir_paragrafo(pendentes)
    return unidades


def conferir_integridade(caminho_pdf: Path, unidades: list[dict]) -> tuple[int, int]:
    """Conta letras e números do corpo do PDF e da extração. Os dois totais devem ser iguais:
    nenhum texto perdido e nenhum texto duplicado (cabeçalho e rodapé não entram na conta)."""
    def contar(texto: str) -> int:
        return sum(c.isalnum() for c in texto)
    no_pdf = 0
    with pymupdf.open(caminho_pdf) as doc:
        for pagina in doc:
            no_pdf += sum(contar(w[4]) for w in pagina.get_text("words")
                          if LIMITE_CABECALHO <= w[1] < LIMITE_RODAPE)
    na_extracao = sum(contar(" ".join(u["linhas"])) for u in unidades)
    return no_pdf, na_extracao


def montar_texto_numerado(unidades: list[dict]) -> str:
    """Texto enviado ao modelo. Exemplo:
        === PÁGINA 25 ===
        # 1.1. Principais Destaques
        §1
        1| Capítulo 3 – Medida da pressão arterial, diagnóstico e classificação
        [TABELA 1]
        1| Recomendações para medida da pressão arterial ... | Forca da recomendação | Certeza da evidência
        2| Recomenda-se classificar a pré-hipertensão ... | FORTE | MODERADA
    """
    partes = []
    pagina_atual = None
    for u in unidades:
        if u["pagina"] != pagina_atual:
            pagina_atual = u["pagina"]
            partes.append(f"\n=== PÁGINA {pagina_atual} ===")
        if u["tipo"] == "titulo":
            partes.append("# " + " ".join(u["linhas"]))
            continue
        partes.append(f"§{u['numero']}" if u["tipo"] == "paragrafo" else f"[TABELA {u['numero']}]")
        partes.extend(f"{i}| {linha}" for i, linha in enumerate(u["linhas"], start=1))
    return "\n".join(partes).strip() + "\n"


def salvar_extracao(unidades: list[dict], texto: str, nome_base: str) -> tuple[Path, Path]:
    PASTA_PROCESSADO.mkdir(parents=True, exist_ok=True)
    caminho_jsonl = PASTA_PROCESSADO / f"{nome_base}_estrutura.jsonl"
    caminho_txt = PASTA_PROCESSADO / f"{nome_base}_numerado.txt"
    with open(caminho_jsonl, "w", encoding="utf-8") as f:
        for u in unidades:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    caminho_txt.write_text(texto, encoding="utf-8")
    return caminho_jsonl, caminho_txt


def executar(caminho_pdf: Path) -> tuple[list[dict], str]:
    """Roda a etapa 1 completa e mostra o resumo. Devolve as unidades e o texto numerado."""
    print("[1/4] Lendo e numerando o PDF...")
    unidades = extrair_documento(caminho_pdf)
    texto = montar_texto_numerado(unidades)
    nome_base = "diretriz_" + re.sub(r"\D", "", caminho_pdf.stem)[-4:]
    caminho_jsonl, caminho_txt = salvar_extracao(unidades, texto, nome_base)
    n_paginas = max(u["pagina"] for u in unidades)
    n_par = sum(u["tipo"] == "paragrafo" for u in unidades)
    n_tab = sum(u["tipo"] == "tabela" for u in unidades)
    print(f"   {n_paginas} páginas, {n_par} parágrafos, {n_tab} tabelas")
    no_pdf, na_extracao = conferir_integridade(caminho_pdf, unidades)
    situacao = "OK, nenhum texto perdido ou duplicado" if no_pdf == na_extracao else "ATENÇÃO, os totais diferem"
    milhar = lambda n: f"{n:,}".replace(",", ".")
    print(f"   Integridade: {milhar(no_pdf)} letras e números no PDF, {milhar(na_extracao)} na extração ({situacao})")
    print(f"   Texto numerado salvo em: {caminho_txt.relative_to(RAIZ)}")
    print(f"   Estrutura salva em:      {caminho_jsonl.relative_to(RAIZ)}")
    return unidades, texto
