"""
Educa Já / Hub Já - sonda RÁPIDA de fontes para novos apps (roda no GitHub).
Só confere: responde? tipo, tamanho informado e um pedaço do começo. Lê no máximo 300 KB de cada. Não grava nada.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

ALVOS = [
    ("Ambiente: INPE focos (lista de arquivos mensais)", "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/"),
    ("Ambiente: INPE focos (lista de arquivos diários)", "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/"),
    ("Obras: ObrasGov API (MT, 3 registros)", "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?pagina=0&tamanhoDaPagina=3&uf=MT"),
    ("Mobilidade: PRF dados abertos (página)", "https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf"),
    ("Assistência: MDS dados abertos (página)", "https://www.gov.br/mds/pt-br/acesso-a-informacao/dados-abertos"),
    ("Assistência: MDS VIS DATA API (Bolsa Família MT)", "https://aplicacoes.cidadania.gov.br/vis/data3/v.php?q[]=oNOclatmtN6xgpyrYWqKbWy3oa2ZmYlzgHx9o3zCiaOd"),
    ("Trabalho: Novo Caged (página)", "https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/estatisticas-trabalho/novo-caged"),
    ("Campo: IBGE SIDRA (PAM soja, Pontes e Lacerda)", "https://apisidra.ibge.gov.br/values/t/1612/n6/5106752/v/216/p/last/c81/2713"),
    ("Clima: INMET (estações)", "https://apitempo.inmet.gov.br/estacoes/T"),
    ("Segurança: SINESP/MJ dados abertos (página)", "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/dados-nacionais-1/base-de-dados-e-notas-metodologicas-dos-gestores-estaduais-sinesp-vde-2022-e-2023"),
]

for nome, url in ALVOS:
    c.log(f"\n# {nome}\n   {url}")
    try:
        with c.abrir(url, tentativas=1, timeout=25) as r:
            tipo = r.headers.get("Content-Type", "?")
            tam = r.headers.get("Content-Length", "?")
            corpo = r.read(300_000)
        txt = corpo.decode("utf-8", "replace")
        c.log(f"   OK  tipo={tipo}  tamanho informado={tam}  lido={len(corpo):,} bytes")
        links = re.findall(r'href="([^"]+\.(?:csv|zip|xlsx|json|gz|7z)[^"]*)"', txt, re.I)
        if links:
            c.log(f"   {len(links)} links de arquivo; últimos: {links[-6:]}")
        if "json" in tipo.lower() or txt.lstrip().startswith(("{", "[")):
            c.log(f"   começo: {re.sub(r'\\s+', ' ', txt)[:500]}")
        elif "csv" in tipo.lower() or ";" in txt[:300] or "," in txt[:200] and "<" not in txt[:50]:
            c.log(f"   começo: {txt[:300]!r}")
        else:
            t = re.search(r"<title>(.*?)</title>", txt, re.S | re.I)
            c.log(f"   título: {re.sub(r'\\s+', ' ', t.group(1)).strip()[:120] if t else '-'}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:160]}")
