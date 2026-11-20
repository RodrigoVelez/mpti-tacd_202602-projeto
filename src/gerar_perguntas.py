"""
GERADOR DE PERGUNTAS E RESPOSTAS DE REFERÊNCIA A PARTIR DA DIRETRIZ (PDF)
=========================================================================

O que este script faz
---------------------
1. Lê o PDF da Diretriz Brasileira de Hipertensão Arterial 2025 e numera cada
   página, parágrafo e linha do texto.
2. Envia o texto numerado para o Claude (API da Anthropic) e pede perguntas em
   linguagem leiga, cada uma com a resposta de referência copiada LITERALMENTE da
   diretriz, a mesma resposta em linguagem simples e a localização exata (página,
   parágrafo e linha). Nem a pergunta nem a resposta simples citam a diretriz.
3. Confere, sem usar IA, se cada trecho citado existe de fato no local indicado.
   Se não existir, procura o trecho no documento inteiro e registra a localização
   correta.
4. Salva tudo em data/perguntas/, uma pasta por tema, por exemplo:
       data/perguntas/01-Classificacao/01-Classificacao.txt   pergunta, resposta e localização
       data/perguntas/01-Classificacao/01-Classificacao.json  todas as informações do tema
       data/perguntas/01-Classificacao/prompt.txt             prompt enviado ao Claude
   Temas que já têm o JSON gravado são reaproveitados sem custo. Para gerar de novo
   um tema, apague a pasta dele.


PASSO A PASSO PARA QUEM NUNCA USOU PYTHON
-----------------------------------------
Ambiente usado na pesquisa (use as mesmas versões para reproduzir):
    Python 3.14.7
    Bibliotecas: versões fixadas em src/requirements.txt

Onde digitar os comandos:
    macOS:    aplicativo Terminal (Aplicativos > Utilitários > Terminal)
    Windows:  PowerShell (menu Iniciar > digite "PowerShell")

Passo 1. Instale o Python 3.14.7 (exatamente esta versão).
    Página oficial da versão: https://www.python.org/downloads/release/python-3147/
    macOS:
        Baixe e instale https://www.python.org/ftp/python/3.14.7/python-3.14.7-macos11.pkg
        Para conferir, digite:
        > python3.14 --version
    Windows:
        Baixe e instale https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe
        (computadores com processador ARM: python-3.14.7-arm64.exe)
        Na primeira tela do instalador, marque "Add python.exe to PATH".
        Para conferir, digite:
        > py -3.14 --version
    O resultado deve ser:   Python 3.14.7

Passo 2. Entre na pasta raiz do projeto.
    A pasta raiz é "Tarefa 10 - Projeto Final", a que contém as pastas "src",
    "docs" e "data". TODOS os comandos dos passos seguintes são digitados nela,
    nunca dentro de "src".
    Igual no macOS e no Windows: digite cd seguido de um espaço, arraste a pasta
    raiz do Finder (ou Explorador de Arquivos) para a janela do terminal e tecle Enter.
    O comando fica parecido com:
        macOS:
        > cd "/Users/seu_nome/.../Tarefa 10 - Projeto Final"
        Windows:
        > cd "C:\\Users\\seu_nome\\...\\Tarefa 10 - Projeto Final"
    Se você estiver dentro de "src", basta digitar:
    > cd ..
    Conferir (deve listar docs, src e data):
        macOS:
        > ls
        Windows:
        > dir

Passo 3. Crie o ambiente virtual (uma "caixa" isolada para as bibliotecas).
    Este passo é feito uma única vez e cria a pasta .venv dentro da pasta raiz.
    macOS:
    > python3.14 -m venv .venv
    Windows:
    > py -3.14 -m venv .venv
    Conferir (deve aparecer a pasta .venv):
        macOS:
        > ls -a
        Windows:
        > dir -Force

Passo 4. Ative o ambiente virtual.
    Repita este passo sempre que abrir um novo terminal (antes, faça o Passo 2).
    macOS:
    > source .venv/bin/activate
    Windows:
    > .venv\\Scripts\\Activate.ps1
        Se aparecer erro de "execução de scripts desabilitada", rode uma única vez:
        > Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
        Responda "S" e repita o comando de ativação.
    O início da linha do terminal passa a mostrar "(.venv)".
    Conferir (igual no macOS e no Windows), deve mostrar Python 3.14.7:
    > python --version

Passo 5. Instale as bibliotecas nas versões exatas usadas na pesquisa.
    Com o ambiente ativo, o comando é igual no macOS e no Windows:
    > python -m pip install -r src/requirements.txt
    Conferir:
    > python -m pip list
    A lista deve conter anthropic 2.8.0, PyMuPDF 2.1 e python-dotenv 1.2.4.

Passo 6. Crie a sua chave da API da Anthropic (pelo navegador, igual no macOS e no Windows).
    a) Acesse https://platform.claude.com e entre com a sua conta. Abre o "Claude Console".
    b) Adicione créditos no botão preto "Adicionar saldo", no canto superior direito.
       O saldo atual aparece ao lado do botão (ex.: US$ 0,00). A API é cobrada à
       parte da assinatura do Claude, então o saldo começa zerado.
    c) No menu da esquerda, na seção "Organização", clique em "Chaves". Na tela
       "Chaves de API", clique no botão "Criar chave" (canto superior direito).
    d) Na janela "Conectar-se à Claude API", escolha "Em outro lugar" (a opção que
       usa uma chave de API). As outras opções não geram chave e não servem para
       este script.
    e) Siga as telas seguintes e copie a chave gerada (começa com "sk-ant-").
       A chave só aparece uma vez. Guarde em local seguro e NUNCA a publique.

Passo 7. Grave a chave no arquivo .env (fica só no seu computador).
    O .env é um arquivo de texto simples, chamado exatamente ".env" (com o ponto
    no início e sem extensão), que fica na pasta raiz do projeto. Ele tem uma
    única linha, no formato:
        ANTHROPIC_API_KEY=sua_chave
    Regras: sem espaços antes ou depois do sinal de igual, sem aspas e com a
    chave inteira (começa com "sk-ant-"). Exemplo:
        ANTHROPIC_API_KEY=sk-ant-api03-AbCdEf123...
    a) Crie o arquivo já com a linha no formato certo:
        macOS:
        > echo "ANTHROPIC_API_KEY=cole_sua_chave_aqui" > .env
        Windows:
        > Set-Content -Path .env -Value "ANTHROPIC_API_KEY=cole_sua_chave_aqui" -Encoding ascii
    b) Abra o arquivo para editar:
        macOS:
        > open -e .env
        Windows:
        > notepad .env
    c) Apague "cole_sua_chave_aqui", cole a sua chave no lugar e salve.
    Atenção: no macOS, arquivos que começam com ponto ficam ocultos no Finder
    (Cmd + Shift + . mostra os ocultos). Isso é normal.
    Se o projeto estiver no Git, confira que o .env está no .gitignore. Assim a
    chave nunca vai para o GitHub.

Passo 8. Execute o script.
    Com o ambiente ativo, o comando é igual no macOS e no Windows:
    > python src/gerar_perguntas.py
    Antes de gastar qualquer crédito, o script mostra o custo estimado e pede
    confirmação. Digite "s" e Enter para continuar.

Opções úteis (todas opcionais)
    Só numera o PDF e salva o texto numerado. Não usa a API nem gasta créditos:
    > python src/gerar_perguntas.py --apenas-extrair
    Gera menos perguntas em cada um dos 5 temas (de 1 até o máximo de 30, que é o
    padrão definido em PERGUNTAS_POR_TEMA, no arquivo configuracao.py). Útil para
    um piloto mais barato, por exemplo 2 perguntas por tema (10 no total):
    > python src/gerar_perguntas.py --qtde-por-tema 2
    Refaz só a conferência das localizações dos temas já gerados e regrava o JSON
    e o TXT de cada um. Não usa a API. Qualquer pessoa pode auditar o conjunto
    publicado assim:
    > python src/gerar_perguntas.py --verificar
    Grava em data/perguntas/<pasta do tema>/prompt.txt o prompt que seria enviado
    ao Claude em cada tema (instruções, formato de saída e pedido). Não usa a API
    nem pede a chave. Toda execução que chama a API também grava esses arquivos:
    > python src/gerar_perguntas.py --log-prompt
    Se a execução for interrompida (erro ou queda de internet), basta rodar o
    mesmo comando de novo: os temas já gerados são reaproveitados sem custo.


Sobre reprodutibilidade
-----------------------
* A extração e a numeração do PDF são determinísticas: o mesmo PDF gera sempre o
  mesmo texto numerado (o hash SHA-256 do PDF fica registrado nos metadados).
* A conferência das localizações também é determinística (opção --verificar).
* A geração das perguntas usa um LLM. O modelo usado (Claude Opus 5.5) não aceita
  o parâmetro temperature, então duas execuções podem gerar perguntas diferentes.
  Por isso o script guarda, para cada execução, o prompt completo, o modelo que
  respondeu, os identificadores das requisições, o consumo de tokens e a resposta
  bruta da API. O conjunto de perguntas publicado é o artefato reprodutível: a
  partir dele qualquer pessoa confere cada resposta no PDF.


Como a localização é definida (definição operacional)
-----------------------------------------------------
* Página: número da página do arquivo PDF, começando em 1. Nesta diretriz ele é
  igual ao número impresso no rodapé.
* Parágrafo: bloco de texto identificado pela biblioteca PyMuPDF, contado de cima
  para baixo na ordem de leitura do arquivo (coluna da esquerda, depois coluna da
  direita). Cabeçalho, rodapé, títulos de seção e tabelas NÃO contam como
  parágrafo. Itens de lista, legendas e notas de rodapé de tabelas contam.
* Tabela: tabela ou quadro identificado pelo PyMuPDF (find_tables), com contagem
  própria na página (tabela 1, tabela 2...), separada da contagem de parágrafos.
* Linha: num parágrafo, a linha de texto, começando em 1. Numa tabela, a linha
  da tabela (o cabeçalho é a linha 1), com as células separadas por " | ".

Arquivos gerados em data/processado/ (recriados a cada execução)
-----------------------------------------------------------------
* diretriz_2025_numerado.txt: texto numerado que é enviado ao Claude.
* diretriz_2025_estrutura.jsonl: a mesma numeração em JSON Lines (um registro
  por título, parágrafo ou tabela), usada na conferência das localizações.
O script confere a integridade da extração: o total de letras e números do corpo
do PDF deve ser igual ao total extraído (nada perdido e nada duplicado).
"""

from __future__ import annotations

import platform
import sys

PYTHON_DA_PESQUISA = "3.14.7"
PYTHON_MINIMA = "3.10.0"

if sys.version_info < (3, 10):
    sys.exit(f"ERRO: este script precisa do Python {PYTHON_DA_PESQUISA} (versão ideal) ou {PYTHON_MINIMA} (versão mínima). Veja o Passo 1 no início do arquivo.")

if platform.python_version() != PYTHON_DA_PESQUISA:
    print(f"AVISO: a pesquisa usou o Python {PYTHON_DA_PESQUISA} e você está usando o {platform.python_version()}.\n"
          "O script deve funcionar, mas para reproduzir o ambiente exato siga o Passo 1.\n")

try:
    import anthropic  # noqa: F401  (só confere se as bibliotecas estão instaladas)
    import dotenv  # noqa: F401
    import pydantic  # noqa: F401
    import pymupdf  # noqa: F401
except ImportError as erro:
    sys.exit(
        f"ERRO: biblioteca não encontrada ({erro.name}).\n"
        "Confira se o ambiente virtual está ativo (Passo 4) e instale as bibliotecas (Passo 5):\n"
        "    python -m pip install -r src/requirements.txt"
    )

import argparse
from pathlib import Path

# As etapas do processo ficam em src/geracao_perguntas/ (um arquivo por etapa).
from geracao_perguntas import etapa1_extracao, etapa2_geracao, etapa3_conferencia, etapa4_resultados
from geracao_perguntas.configuracao import PDF_PADRAO, PERGUNTAS_POR_TEMA


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera perguntas e respostas de referência a partir da diretriz.")
    parser.add_argument("--pdf", type=Path, default=PDF_PADRAO, help="Caminho do PDF (padrão: Diretriz 2025).")
    parser.add_argument("--qtde-por-tema", type=int, default=PERGUNTAS_POR_TEMA, help="Quantidade de perguntas por tema.")
    parser.add_argument("--apenas-extrair", action="store_true", help="Só numera o PDF, sem usar a API.")
    parser.add_argument("--verificar", action="store_true", help="Refaz a conferência dos temas já gerados, sem usar a API.")
    parser.add_argument("--log-prompt", action="store_true", help="Grava o prompt de cada tema em prompt.txt, sem usar a API.")
    args = parser.parse_args()

    if not args.pdf.exists():
        sys.exit(f"ERRO: PDF não encontrado em:\n   {args.pdf}")
    if not 1 <= args.qtde_por_tema <= PERGUNTAS_POR_TEMA:
        sys.exit(f"ERRO: --qtde-por-tema deve ser um número de 1 a {PERGUNTAS_POR_TEMA}.")

    # Etapa 1. Extração e numeração do PDF (sem IA, sem custo)
    unidades, texto = etapa1_extracao.executar(args.pdf)

    # Opções que encerram o script logo depois da etapa 1 (não usam a API)
    if args.apenas_extrair:
        print("Pronto. Abra os arquivos acima para ver como o documento foi numerado.")
        return
    if args.verificar:  # refaz as etapas 3 e 4 sobre os temas já gerados
        etapa4_resultados.executar_verificacao(unidades)
        return
    if args.log_prompt:  # grava os prompt.txt dos 5 temas, sem pedir a chave
        etapa2_geracao.executar_log_prompt(texto, args.pdf, args.qtde_por_tema)
        return

    # Etapa 2. Geração das perguntas com o Claude (API, tem custo)
    # Mostra o custo estimado e pede confirmação antes de gastar créditos.
    resultado = etapa2_geracao.executar(texto, args.qtde_por_tema, args.pdf)
    if resultado is None:  # usuário cancelou na confirmação de custo
        return

    # Etapa 3. Conferência das localizações no PDF (sem IA, sem custo)
    etapa3_conferencia.executar([i for d in resultado["temas"].values() for i in d["itens"]], unidades)

    # Etapa 4. Gravação dos resultados e metadados (sem custo)
    etapa4_resultados.executar(resultado, args.pdf, texto)


if __name__ == "__main__":
    main()
