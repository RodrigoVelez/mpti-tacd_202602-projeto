"""ETAPA 3. CONFERÊNCIA DAS LOCALIZAÇÕES (determinística, sem IA)

Para cada evidência informada pelo modelo, confere se o trecho citado existe de
fato na página, parágrafo ou tabela e linhas indicados. Se não existir, procura o
trecho no documento inteiro. Cada pergunta recebe um status:
    confere                a localização indicada está correta
    localizacao_corrigida  o trecho existe, mas em outro lugar (localização corrigida)
    revisar                trecho não encontrado ou resposta não literal
"""

import unicodedata


def normalizar(texto: str) -> str:
    """Compara só letras e números, ignorando maiúsculas, espaços, hífens e pontuação."""
    texto = unicodedata.normalize("NFKC", texto).lower()
    return "".join(c for c in texto if c.isalnum())


CAMPOS_LOCAL = ("pagina", "tipo", "numero", "linha_inicial", "linha_final")


def indexar(unidades: list[dict]) -> dict:
    return {(u["pagina"], u["tipo"], u["numero"]): u for u in unidades if u["tipo"] != "titulo"}


def procurar_no_documento(trecho_norm: str, unidades: list[dict]) -> dict | None:
    """Procura o trecho em todo o documento e devolve a menor faixa de linhas que o contém."""
    for u in unidades:
        if u["tipo"] == "titulo":
            continue
        linhas = u["linhas"]
        if trecho_norm not in normalizar(" ".join(linhas)):
            continue
        def contem(ini: int, fim: int) -> bool:
            return trecho_norm in normalizar(" ".join(linhas[ini:fim + 1]))
        fim = next(f for f in range(len(linhas)) if contem(0, f))  # primeira linha final que fecha o trecho
        ini = 0
        while ini < fim and contem(ini + 1, fim):  # avança o início enquanto o trecho continuar contido
            ini += 1
        return {"pagina": u["pagina"], "tipo": u["tipo"], "numero": u["numero"],
                "linha_inicial": ini + 1, "linha_final": fim + 1, "secao": u["secao"]}
    return None


def conferir_item(item: dict, indice: dict, unidades: list[dict]) -> None:
    """Acrescenta ao item o resultado da conferência de cada evidência."""
    textos_confirmados = []
    for ev in item["evidencias"]:
        trecho_norm = normalizar(ev["trecho_literal"])
        u = indice.get((ev["pagina"], ev["tipo"], ev["numero"]))
        texto_local = ""
        if u:
            ini = max(ev["linha_inicial"], 1) - 1
            fim = min(ev["linha_final"], len(u["linhas"]))
            texto_local = " ".join(u["linhas"][ini:fim])
        if trecho_norm and trecho_norm in normalizar(texto_local):
            ev["status"] = "confere"
            ev["localizacao_verificada"] = {**{k: ev[k] for k in CAMPOS_LOCAL}, "secao": u["secao"]}
            textos_confirmados.append(ev["trecho_literal"])
            continue
        achado = procurar_no_documento(trecho_norm, unidades) if trecho_norm else None
        ev["status"] = "corrigida" if achado else "nao_encontrada"
        ev["localizacao_verificada"] = achado
        if achado:
            textos_confirmados.append(ev["trecho_literal"])

    resposta_norm = normalizar(item["resposta_referencia"])
    item["resposta_e_literal"] = bool(resposta_norm) and resposta_norm in normalizar(" ".join(textos_confirmados))
    status = {ev["status"] for ev in item["evidencias"]}
    if status == {"confere"} and item["resposta_e_literal"]:
        item["status_verificacao"] = "confere"
    elif "nao_encontrada" in status or not item["resposta_e_literal"]:
        item["status_verificacao"] = "revisar"
    else:
        item["status_verificacao"] = "localizacao_corrigida"

def resumo_verificacao(itens: list[dict]) -> str:
    total = len(itens)
    contagem = {s: sum(1 for i in itens if i["status_verificacao"] == s)
                for s in ("confere", "localizacao_corrigida", "revisar")}
    return (f"   {contagem['confere']} de {total} conferem exatamente com a localização indicada\n"
            f"   {contagem['localizacao_corrigida']} tinham a localização errada e foram corrigidas\n"
            f"   {contagem['revisar']} precisam de revisão manual (trecho não encontrado ou resposta não literal)")


def executar(itens: list[dict], unidades: list[dict]) -> None:
    """Roda a etapa 3 completa: confere todos os itens e mostra o resumo."""
    print("[3/4] Conferindo no PDF cada localização informada pelo modelo...")
    indice = indexar(unidades)
    for item in itens:
        conferir_item(item, indice, unidades)
    print(resumo_verificacao(itens))
