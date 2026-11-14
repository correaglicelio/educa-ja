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
    ("Obras: ObrasGov API v2 (MT, 2 registros)", "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?pagina=0&tamanhoDaPagina=2&uf=MT", 70),
    ("Obras: ObrasGov (documentação/swagger)", "https://api.obrasgov.gestao.gov.br/obrasgov/swagger-ui/index.html", 40),
    ("Mobilidade: PRF (links de dados)", "https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf", 40),
    ("Assistência: Transparência, Novo Bolsa Família (página)", "https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia", 40),
    ("Assistência: Transparência, API Bolsa Família por município (precisa chave?)", "https://api.portaldatransparencia.gov.br/api-de-dados/novo-bolsa-familia-por-municipio?mesAno=202509&codigoIbge=5106752&pagina=1", 40),
]

for nome, url, lim in ALVOS:
    c.log(f"\n# {nome}\n   {url}")
    try:
        with c.abrir(url, tentativas=1, timeout=lim) as r:
            tipo = r.headers.get("Content-Type", "?")
            tam = r.headers.get("Content-Length", "?")
            corpo = r.read(300_000)
        txt = corpo.decode("utf-8", "replace")
        c.log(f"   OK  tipo={tipo}  tamanho informado={tam}  lido={len(corpo):,} bytes")
        links = re.findall(r'href="([^"]*(?:datatran|acidente|drive\.google|\.csv|\.zip|\.xlsx|\.7z|download|dados)[^"]*)"', txt, re.I)
        links = [x for x in dict.fromkeys(links) if "gov.br/prf" in x or "drive" in x or "bolsa" in x.lower() or "obrasgov" in x][:12]
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
