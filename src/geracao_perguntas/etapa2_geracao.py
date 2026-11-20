"""ETAPA 2. GERAÇÃO DAS PERGUNTAS COM O CLAUDE (API, tem custo)

Envia o texto numerado da etapa 1 ao Claude, uma chamada por tema, e recebe as
perguntas em JSON no formato definido abaixo (saída estruturada: a API garante
que a resposta segue exatamente esse formato). Antes de gastar, mostra o custo
estimado e pede confirmação.
"""

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .configuracao import (ARQUIVO_ENV, CACHE_TTL, ESFORCO, MAX_TOKENS, MIN_NOVA_CLASSIFICACAO, MODELO,
                           PASTAS_TEMAS, PERMITIR_FALLBACK, PRECO_ENTRADA, PRECO_ESCRITA_CACHE, PRECO_ESCRITA_CACHE_1H,
                           PRECO_LEITURA_CACHE, PRECO_SAIDA, RAIZ, TEMAS, arquivo_do_tema)
from .etapa1_extracao import hash_arquivo


# Formato da resposta pedida ao modelo
class Evidencia(BaseModel):
    pagina: int = Field(description="Número da página (marcador '=== PÁGINA N ===').")
    tipo: Literal["paragrafo", "tabela"] = Field(description="'paragrafo' para o marcador '§N' ou 'tabela' para o marcador '[TABELA N]'.")
    numero: int = Field(description="Número do parágrafo (§N) ou da tabela ([TABELA N]) na página.")
    linha_inicial: int = Field(description="Primeira linha do trecho dentro do parágrafo ou da tabela.")
    linha_final: int = Field(description="Última linha do trecho dentro do parágrafo ou da tabela.")
    trecho_literal: str = Field(description="Texto copiado literalmente dessas linhas, sem os números de linha.")


class ParPerguntaResposta(BaseModel):
    pergunta: str = Field(description="Pergunta em linguagem leiga, como um paciente perguntaria.")
    resposta_referencia: str = Field(description="Frase(s) copiada(s) literalmente da diretriz que respondem à pergunta.")
    # default="" permite ler os JSON gravados antes da criação deste campo
    resposta_leiga: str = Field(default="", description="A mesma informação da resposta_referencia, reescrita em linguagem simples para um paciente, em 1 a 3 frases curtas, sem citar a diretriz.")
    secao: str = Field(description="Seção da diretriz de onde veio a resposta (ex.: '3.3. Medida da Pressão Arterial fora do Consultório').")
    sobre_nova_classificacao: bool = Field(description="True se a pergunta trata da mudança de classificação de 2025 (120-129 e/ou 80-84 mmHg).")
    evidencias: list[Evidencia] = Field(description="Localização exata de cada parte da resposta de referência.")


class LotePerguntas(BaseModel):
    itens: list[ParPerguntaResposta]


INSTRUCOES_SISTEMA = """\
Você ajuda a montar um conjunto de teste científico para avaliar sistemas de \
perguntas e respostas sobre a Diretriz Brasileira de Hipertensão Arterial 2025.

O documento vem logo abaixo, com página, parágrafo, tabela e linha numerados:
- "=== PÁGINA N ===" marca o início da página N.
- "# ..." é um título de seção (não é parágrafo).
- "§N" marca o parágrafo N daquela página.
- "[TABELA N]" marca a tabela N daquela página. Cada linha da tabela é uma \
linha numerada, com as células separadas por " | ".
- "K| texto" é a linha K daquele parágrafo ou daquela tabela.

Regras para cada item:
1. Pergunta:
   a) em português, escrita como um paciente ou familiar sem formação em saúde \
falaria, em primeira pessoa quando couber, com palavras do dia a dia;
   b) sem siglas e sem jargão (não use PAS, PAD, PA, HA, CV, MAPA, MRPA, LOA, IMC, \
DCV, "estratificação", "normotensão" etc.). Quando a ideia for necessária, explique \
com palavras simples (ex.: "pressão de cima", "aparelho que mede a pressão durante \
24 horas");
   c) não cite nem pressuponha a diretriz: nada de "diretriz", "documento", \
"tabela", "quadro", "capítulo", "recomendação forte/fraca", "nível de evidência", \
"segundo o texto". A pessoa não sabe que esse documento existe;
   d) escreva valores de pressão no jeito popular quando fizer sentido ("13 por 8", \
"135 por 85").
2. A resposta_referencia deve ser copiada LITERALMENTE da diretriz (uma ou poucas \
frases completas), sem resumir, sem parafrasear e sem os números de linha. Quando \
uma palavra estiver partida com hífen no fim da linha, junte as partes. Dê \
preferência a trechos que não mencionem o próprio documento ("esta diretriz", \
"DBHA", "ver Capítulo", "Quadro"). Se o trecho certo mencionar, mantenha a cópia \
literal mesmo assim.
3. Cada evidência indica a página, o tipo (paragrafo ou tabela), o número do \
parágrafo ou da tabela, a linha inicial e a linha final de onde o trecho foi \
copiado, e o trecho_literal copiado dessas linhas. Em tabelas, copie o texto das \
células sem o separador " | ". Se a resposta ocupar duas unidades (ou duas \
páginas), use uma evidência para cada uma.
4. Use só o corpo da diretriz. Não use capa, lista de autores, declarações de \
conflito de interesse, lista de abreviaturas nem referências bibliográficas.
5. A pergunta deve ter resposta clara e única no trecho citado. Não repita \
perguntas nem use o mesmo trecho em duas perguntas.
6. Prefira recomendações práticas e valores numéricos que um paciente queira saber.
7. A resposta_leiga é a resposta_referencia reescrita para a mesma pessoa leiga:
   a) use só a informação da resposta_referencia, sem acrescentar conselho, dado \
ou opinião;
   b) mantenha todos os números e unidades e não omita nenhuma condição importante \
da resposta literal;
   c) troque siglas e termos técnicos por palavras simples;
   d) não cite a diretriz, tabelas, quadros, capítulos, estudos nem força de \
recomendação;
   e) escreva de 1 a 3 frases curtas, falando diretamente com a pessoa.

=== DOCUMENTO ===
"""


def pedido_do_tema(chave: str, quantidade: int, existentes: list[dict] | None = None) -> str:
    """Pedido de um tema. Com 'existentes', o tema está sendo completado: o modelo recebe
    as perguntas já geradas para não repetir perguntas nem trechos."""
    existentes = existentes or []
    texto = (f"Gere exatamente {quantidade} itens sobre o tema: {TEMAS[chave]}.\n"
             "Distribua as perguntas por diferentes partes da diretriz que tratam desse tema.")
    if chave == "classificacao":
        ja_feitas = sum(1 for e in existentes if e.get("sobre_nova_classificacao"))
        minimo = min(max(MIN_NOVA_CLASSIFICACAO - ja_feitas, 0), quantidade)
        if minimo:
            texto += (f"\nPelo menos {minimo} itens devem tratar da mudança de 2025: valores de "
                      "PAS 120-129 mmHg e/ou PAD 80-84 mmHg, que eram 'PA normal' em 2020 e passaram a ser "
                      "'pré-hipertensão', e o fim da categoria 'PA ótima'.")
        texto += "\nMarque com sobre_nova_classificacao = true os itens que tratam dessa mudança de classificação."
    else:
        texto += "\nMarque sobre_nova_classificacao = true só se o item tratar dessa mudança de classificação."
    if existentes:
        texto += (f"\n\nEste tema já tem {len(existentes)} perguntas, listadas abaixo. Gere perguntas NOVAS: "
                  "não repita estas perguntas, nem com outras palavras, e não use os mesmos trechos da diretriz.")
        for e in existentes:
            locais = "; ".join(f"p. {ev['pagina']} {ev['tipo']} {ev['numero']}" for ev in e["evidencias"])
            texto += f"\n- {e['pergunta']} [{locais}]"
    return texto


def montar_sistema(texto_numerado: str) -> list[dict]:
    # O documento fica no prompt de sistema com cache: a 1a chamada grava o cache
    # e as chamadas seguintes leem do cache, pagando cerca de 5% do preço de entrada.
    return [
        {"type": "text", "text": INSTRUCOES_SISTEMA},
        {"type": "text", "text": texto_numerado, "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}},
    ]


def parametros_extras() -> dict:
    if PERMITIR_FALLBACK:
        return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    return {}


TOKENS_SAIDA_POR_PERGUNTA = 760  # média observada na 1a execução real (10.592 tokens para 14 perguntas)


def custo_da_chamada(c: dict) -> float:
    """Custo em US$ de uma chamada, a partir dos tokens registrados."""
    return (c["tokens_entrada"] * PRECO_ENTRADA + c["tokens_saida"] * PRECO_SAIDA
            + c.get("tokens_escrita_cache_5m", 0) * PRECO_ESCRITA_CACHE
            + c.get("tokens_escrita_cache_1h", 0) * PRECO_ESCRITA_CACHE_1H
            + c["tokens_leitura_cache"] * PRECO_LEITURA_CACHE) / 1e6


def estimar_custo(client: anthropic.Anthropic, sistema: list[dict], pendentes: dict) -> float:
    """pendentes: {tema: (quantidade a gerar, perguntas já existentes)}"""
    primeiro = next(iter(pendentes))
    contagem = client.beta.messages.count_tokens(
        model=MODELO,
        system=sistema,
        messages=[{"role": "user", "content": pedido_do_tema(primeiro, *pendentes[primeiro])}],
    )
    entrada = contagem.input_tokens
    n = len(pendentes)
    preco_escrita = PRECO_ESCRITA_CACHE_1H if CACHE_TTL == "1h" else PRECO_ESCRITA_CACHE
    saida_estimada = TOKENS_SAIDA_POR_PERGUNTA * sum(q for q, _ in pendentes.values())
    # 1a chamada grava o documento no cache, as seguintes leem do cache
    custo = (entrada * preco_escrita + entrada * (n - 1) * PRECO_LEITURA_CACHE + saida_estimada * PRECO_SAIDA) / 1e6
    print(f"   Tamanho do documento + instruções: {entrada:,} tokens".replace(",", "."))
    print(f"   Chamadas à API: {n}")
    for chave, (qtde, existentes) in pendentes.items():
        extra = f" (completando: já tem {len(existentes)})" if existentes else ""
        print(f"      {PASTAS_TEMAS[chave]}: {qtde} perguntas{extra}")
    print(f"   Custo estimado: US$ {custo:.2f} (pode variar conforme o tamanho das respostas)")
    return custo


def gerar_tema(client: anthropic.Anthropic, sistema: list[dict], chave: str, quantidade: int,
               existentes: list[dict]) -> None:
    """Chama a API para um tema e GRAVA a resposta no JSON do tema antes de qualquer
    outra verificação. Assim, uma resposta paga nunca se perde, mesmo que algo falhe depois.
    Cada chamada é acrescentada à lista 'respostas_api' do tema."""
    pedido = pedido_do_tema(chave, quantidade, existentes)
    # streaming evita que a conexão expire enquanto o modelo trabalha
    with client.beta.messages.stream(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        system=sistema,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": ESFORCO},
        output_format=LotePerguntas,
        **parametros_extras(),
    ) as stream:
        mensagem = stream.get_final_message()
        request_id = stream.request_id
    arquivo = arquivo_do_tema(chave, "json")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    dados = _carregar(chave) if arquivo.exists() else {"tema": chave, "descricao": TEMAS[chave], "respostas_api": []}
    dados["respostas_api"].append({"pedido": pedido, "qtde_pedida": quantidade, "request_id": request_id,
                                   "resposta": json.loads(mensagem.to_json())})
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _carregar(chave: str) -> dict:
    """Lê o JSON do tema. Converte o formato antigo (uma única 'resposta_api') para a lista 'respostas_api'."""
    dados = json.loads(arquivo_do_tema(chave, "json").read_text(encoding="utf-8"))
    if "resposta_api" in dados:
        antiga = {"pedido": dados.pop("pedido", None), "qtde_pedida": dados.pop("qtde_solicitada", None),
                  "request_id": dados.pop("request_id", None) or (dados.get("chamada") or {}).get("request_id"),
                  "resposta": dados.pop("resposta_api")}
        dados["respostas_api"] = [antiga]
        dados.pop("chamada", None)
    return dados


def ler_tema_gravado(chave: str) -> dict:
    """Lê o JSON gravado de um tema e devolve os dados com todas as perguntas e o registro
    das chamadas. É o mesmo caminho para respostas novas e para respostas anteriores."""
    dados = _carregar(chave)
    itens, chamadas = [], []
    numero_tema = PASTAS_TEMAS[chave][:2]
    for registro in dados["respostas_api"]:
        bruto = registro["resposta"]
        stop = bruto.get("stop_reason")
        if stop == "refusal":
            detalhe = (bruto.get("stop_details") or {}).get("explanation") or ""
            raise RuntimeError(f"O modelo recusou o pedido do tema '{chave}'. {detalhe}")
        if stop == "max_tokens":
            raise RuntimeError(f"A resposta do tema '{chave}' foi cortada. Aumente MAX_TOKENS (configuracao.py) "
                               "ou use --qtde-por-tema menor.")
        textos = [b["text"] for b in bruto.get("content", []) if b.get("type") == "text"]
        if not textos:
            raise RuntimeError(f"A resposta do tema '{chave}' não trouxe texto.")
        for item in LotePerguntas.model_validate_json(textos[-1]).itens:
            itens.append({"id": f"{numero_tema}-{len(itens) + 1:02d}", **item.model_dump()})
        uso = bruto.get("usage") or {}
        criacao = uso.get("cache_creation") or {}
        chamada = {
            "modelo_que_respondeu": bruto.get("model"),
            "message_id": bruto.get("id"),
            "request_id": registro.get("request_id"),
            "stop_reason": stop,
            "qtde_pedida": registro.get("qtde_pedida"),
            "tokens_entrada": uso.get("input_tokens") or 0,
            "tokens_saida": uso.get("output_tokens") or 0,
            "tokens_escrita_cache_5m": criacao.get("ephemeral_5m_input_tokens",
                                                   0 if criacao else uso.get("cache_creation_input_tokens") or 0),
            "tokens_escrita_cache_1h": criacao.get("ephemeral_1h_input_tokens", 0),
            "tokens_leitura_cache": uso.get("cache_read_input_tokens") or 0,
        }
        chamada["custo_usd"] = round(custo_da_chamada(chamada), 4)
        chamadas.append(chamada)
    dados["itens"] = itens
    dados["chamadas"] = chamadas
    return dados


def obter_cliente() -> anthropic.Anthropic:
    if not ARQUIVO_ENV.exists():
        sys.exit(f"ERRO: arquivo .env não encontrado em:\n   {RAIZ}\n"
                 "Siga o Passo 7 no início de src/gerar_perguntas.py para criá-lo.")
    load_dotenv(ARQUIVO_ENV)
    chave = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
    if not chave.startswith("sk-ant-"):
        sys.exit("ERRO: a chave no arquivo .env não está no formato esperado.\n"
                 "A linha deve ser exatamente   ANTHROPIC_API_KEY=sk-ant-...   (sem espaços e sem aspas).\n"
                 "Siga os Passos 6 e 7 no início de src/gerar_perguntas.py.")
    return anthropic.Anthropic(api_key=chave)


def temas_pendentes(qtde_por_tema: int) -> dict:
    """Temas que ainda não têm a quantidade pedida: {tema: (quantidade a gerar, perguntas já existentes)}."""
    pendentes = {}
    for chave in TEMAS:
        existentes = ler_tema_gravado(chave)["itens"] if arquivo_do_tema(chave, "json").exists() else []
        if len(existentes) < qtde_por_tema:
            pendentes[chave] = (qtde_por_tema - len(existentes), existentes)
    return pendentes


def gravar_prompts(texto_numerado: str, caminho_pdf: Path, qtde_por_tema: int, pendentes: dict,
                   so_pendentes: bool) -> list[Path]:
    """Grava data/perguntas/<pasta do tema>/prompt.txt com o prompt que vai (ou iria) ao Claude.
    Há um pedido diferente por tema, por isso um prompt.txt por pasta. Não usa a API.
    Com so_pendentes=False grava os 5 temas. Um tema completo recebe o pedido de uma geração
    do zero, com um aviso no cabeçalho de que ele não seria enviado na próxima execução."""
    momento = datetime.now().isoformat(timespec="seconds")
    hash_pdf = hash_arquivo(caminho_pdf)
    hash_texto = hashlib.sha256(texto_numerado.encode("utf-8")).hexdigest()
    caracteres = f"{len(texto_numerado):,}".replace(",", ".")
    esquema = json.dumps(LotePerguntas.model_json_schema(), ensure_ascii=False, indent=2)
    gravados = []
    for chave in TEMAS:
        if chave in pendentes:
            qtde, existentes = pendentes[chave]
            aviso = ""
        elif so_pendentes:
            continue
        else:
            qtde, existentes = qtde_por_tema, None
            aviso = "Tema completo: este pedido não seria enviado na próxima execução\n"
        partes = [
            f"Log gerado em: {momento}",
            f"Tema: {PASTAS_TEMAS[chave]} ({TEMAS[chave]})",
            f"Modelo: {MODELO}",
            f"Esforço: {ESFORCO}",
            f"MAX_TOKENS: {MAX_TOKENS}",
            f"CACHE_TTL: {CACHE_TTL}",
            f"Quantidade pedida: {qtde}",
            f"SHA-256 do PDF ({caminho_pdf.name}): {hash_pdf}",
            f"SHA-256 do texto numerado: {hash_texto}",
            aviso,
            "=== MENSAGEM DE SISTEMA ===",
            INSTRUCOES_SISTEMA + f"[DOCUMENTO NUMERADO: conteúdo idêntico a data/processado/diretriz_2025_numerado.txt, "
                                 f"{caracteres} caracteres, SHA-256 {hash_texto}]\n",
            "=== FORMATO DE SAÍDA (JSON SCHEMA) ===",
            esquema + "\n",
            "=== MENSAGEM DO USUÁRIO ===",
            pedido_do_tema(chave, qtde, existentes),
        ]
        arquivo = arquivo_do_tema(chave, "json").parent / "prompt.txt"
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("\n".join(partes) + "\n", encoding="utf-8")
        gravados.append(arquivo)
    return gravados


def executar_log_prompt(texto_numerado: str, caminho_pdf: Path, qtde_por_tema: int) -> None:
    """Opção --log-prompt: grava os 5 prompt.txt sem chamar a API e sem pedir a chave."""
    print("[2/4] Gravando o prompt de cada tema (sem usar a API)...")
    for arquivo in gravar_prompts(texto_numerado, caminho_pdf, qtde_por_tema, temas_pendentes(qtde_por_tema),
                                  so_pendentes=False):
        print(f"   {arquivo.relative_to(RAIZ)}")


def executar(texto_numerado: str, qtde_por_tema: int, caminho_pdf: Path) -> dict | None:
    """Roda a etapa 2 completa. Temas que já têm a quantidade pedida em data/perguntas/ são
    reaproveitados sem custo. Temas com menos perguntas são completados (só o que falta) e
    temas sem nada são gerados. Devolve os dados de cada tema, ou None se o usuário cancelar
    na confirmação de custo. Para gerar de novo um tema, apague a pasta dele."""
    print("[2/4] Gerando as perguntas com o Claude (API)...")
    pendentes = temas_pendentes(qtde_por_tema)  # tema -> (quantidade a gerar, perguntas já existentes)
    prontos = [c for c in TEMAS if c not in pendentes]
    if prontos:
        print(f"   Temas completos (reaproveitados, sem custo): {', '.join(PASTAS_TEMAS[c] for c in prontos)}")

    if pendentes:
        print("   Conectando à API da Anthropic e estimando o custo...")
        client = obter_cliente()
        sistema = montar_sistema(texto_numerado)
        try:
            estimar_custo(client, sistema, pendentes)
        except anthropic.AuthenticationError:
            sys.exit("ERRO: a chave da API foi recusada. Confira se ela foi copiada inteira para o arquivo .env.")
        except anthropic.APIConnectionError:
            sys.exit("ERRO: sem conexão com a internet ou com a API da Anthropic.")
        except anthropic.APIStatusError as erro:  # ex.: saldo insuficiente
            sys.exit(f"ERRO da API ({erro.status_code}): {erro.message}")
        # registra o prompt de cada tema pendente antes de qualquer gasto
        for arquivo in gravar_prompts(texto_numerado, caminho_pdf, qtde_por_tema, pendentes, so_pendentes=True):
            print(f"   Prompt registrado em {arquivo.relative_to(RAIZ)}")
        if input("   Deseja continuar? [s/N] ").strip().lower() not in ("s", "sim"):
            print("Cancelado. Nenhum crédito foi gasto.")
            return None

    momento = datetime.now()
    temas = {}
    for n, chave in enumerate(TEMAS, start=1):
        print(f"   ({n}/{len(TEMAS)}) {PASTAS_TEMAS[chave]}... ", end="", flush=True)
        if chave in pendentes:
            qtde, existentes = pendentes[chave]
            try:
                gerar_tema(client, sistema, chave, qtde, existentes)
            except anthropic.RateLimitError:
                sys.exit(_parada("limite de uso da API atingido. Aguarde alguns minutos"))
            except anthropic.APIStatusError as erro:
                sys.exit(_parada(f"da API ({erro.status_code}): {erro.message}"))
            except anthropic.APIConnectionError:
                sys.exit(_parada("conexão interrompida"))
        try:
            temas[chave] = ler_tema_gravado(chave)
        except Exception as erro:  # resposta gravada, mas com problema: nada se perde
            sys.exit(_parada(f"ao ler a resposta do tema '{chave}': {erro}"))
        total = len(temas[chave]["itens"])
        if chave in pendentes:
            qtde, existentes = pendentes[chave]
            novas = total - len(existentes)
            aviso = "" if novas == qtde else f" (pedidas {qtde}, vieram {novas})"
            print(f"{total} perguntas, {novas} novas{aviso}")
        else:
            print(f"{total} perguntas (reaproveitadas)")

    return {"temas": temas, "momento": momento}


def _parada(motivo: str) -> str:
    return (f"\nERRO {motivo}.\n"
            "As respostas já recebidas estão gravadas em data/perguntas/ e não serão cobradas de novo.\n"
            "Para continuar de onde parou, rode o mesmo comando outra vez:\n"
            "   python src/gerar_perguntas.py")
