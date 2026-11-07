"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: procura dados novos (indicadores do INEP, alfabetização, INSE, catálogo do FNDE, obras, conectividade, Pé-de-Meia).
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36", "Accept-Language": "pt-BR"}


def pegar(url: str, limite: int = 3_000_000) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, dict(r.headers), r.read(limite)


def cabeca(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            return f"{r.status} {int(r.headers.get('Content-Length') or 0) / 1e6:.1f} MB {r.headers.get('Last-Modified', '')}"
    except Exception as e:  # noqa: BLE001
        return f"ERRO {str(e)[:80]}"


def links(url: str, filtro: str) -> None:
    try:
        st, h, b = pegar(url)
        html = b.decode("utf-8", "replace")
        achados = sorted(set(re.findall(r'href="([^"]+)"', html)))
        achados = [a for a in achados if re.search(filtro, a, re.I)]
        c.log(f"\n## {url} ({st}): {len(achados)} links com /{filtro}/")
        for a in achados[:60]:
            c.log(f"   {a}")
    except Exception as e:  # noqa: BLE001
        c.log(f"\n## {url}: ERRO {str(e)[:120]}")


# 1) Indicadores educacionais do INEP (2025): o que existe além de rendimento, TDI, ATU e HAD
IND = "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{ano}/{nome}"
c.log("# Indicadores educacionais (arquivos por escola)")
for ano in (2025, 2024):
    for sig in ("AFD", "IRD", "IED", "ICG", "DSU", "TNR"):
        for nome in (f"{sig}_{ano}_ESCOLAS.zip", f"{sig}_{ano}_MUNICIPIOS.zip"):
            c.log(f"   {ano} {nome}: {cabeca(IND.format(ano=ano, nome=nome))}")
links("https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais", r"\.zip|\.xlsx|indicador")

# 2) INSE (nível socioeconômico) e Criança Alfabetizada
links("https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/nivel-socioeconomico", r"inse|\.zip|\.xlsx")
for u in ("https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/2021/nivel_socioeconomico/INSE_2021_escolas.xlsx",
          "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/2023/nivel_socioeconomico/INSE_2023_escolas.xlsx",
          "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/2023/nivel_socioeconomico/INSE_2023.zip"):
    c.log(f"   {u}: {cabeca(u)}")
links("https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/compromisso-nacional-crianca-alfabetizada", r"alfabetiz|\.xlsx|\.zip|\.csv|resultado")
links("https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/avaliacao-da-alfabetizacao", r"\.zip|\.xlsx|\.csv")

# 3) Catálogo de produtos de dados do FNDE (Plataforma Antonieta de Barros)
API = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products"
c.log("\n# FNDE - produtos de dados")
try:
    st, h, b = pegar(API)
    if h.get("Content-Encoding") == "gzip":
        b = gzip.decompress(b)
    d = json.loads(b)
    itens = d if isinstance(d, list) else d.get("content") or d.get("items") or d.get("data") or []
    c.log(f"   {len(itens)} produtos (chaves: {list(itens[0].keys()) if itens else d if not isinstance(d, list) else ''})"[:400])
    for p in itens:
        c.log(f"   {p.get('id')}: {p.get('name') or p.get('title') or p.get('nome')}")
except Exception as e:  # noqa: BLE001
    c.log(f"   lista falhou ({str(e)[:100]}); testando ids 1-120")
    for i in range(1, 121):
        try:
            st, h, b = pegar(f"{API}/{i}", 200_000)
            d = json.loads(b)
            c.log(f"   {i}: {d.get('name') or d.get('title') or d.get('nome')} | {str(d.get('description') or '')[:90]}")
        except Exception as e2:  # noqa: BLE001
            if "404" not in str(e2):
                c.log(f"   {i}: {str(e2)[:60]}")

# 4) Obras (ObrasGov, API pública) e conectividade das escolas
for u in ("https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?uf=MT&pagina=0&tamanhoDaPagina=3",
          "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?uf=MT&municipio=Pontes%20e%20Lacerda&pagina=0&tamanhoDaPagina=20"):
    try:
        st, h, b = pegar(u)
        c.log(f"\n## {u} ({st}): {b[:1500].decode('utf-8', 'replace')}")
    except Exception as e:  # noqa: BLE001
        c.log(f"\n## {u}: ERRO {str(e)[:120]}")
links("https://www.gov.br/mec/pt-br/escolas-conectadas/painel-de-monitoramento", r"\.csv|\.xlsx|\.zip|dados|painel|powerbi|app\.")

# 5) Portal da Transparência: bases para baixar (Pé-de-Meia, Bolsa Família, etc.)
links("https://portaldatransparencia.gov.br/download-de-dados", r"download-de-dados/")
