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


def pegar(url: str, limite: int = 3_000_000):  # noqa: F811  (usa o abridor do projeto, que lida com o certificado do INEP)
    with c.abrir(url, tentativas=2, cabecalhos=UA) as r:
        return r.status, dict(r.headers), r.read(limite)


def cabeca(url: str) -> str:  # noqa: F811
    try:
        with c.abrir(url, tentativas=2, metodo="HEAD", cabecalhos=UA) as r:
            return f"{r.status} {int(r.headers.get('Content-Length') or 0) / 1e6:.1f} MB {r.headers.get('Last-Modified', '')}"
    except Exception as e:  # noqa: BLE001
        return f"ERRO {str(e)[:80]}"


G = "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/"
c.log("# Páginas dos indicadores (links de download)")
for pag in ("adequacao-da-formacao-docente", "complexidade-de-gestao-da-escola", "esforco-docente", "regularidade-do-corpo-docente",
            "remuneracao-media-dos-docentes", "nivel-socioeconomico", "taxas-de-transicao", "percentual-de-docentes-com-curso-superior"):
    links(G + pag, r"download\.inep|\.zip|\.xlsx")
for u in ("https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/saeb/resultados",
          "https://www.gov.br/mec/pt-br/crianca-alfabetizada", "https://www.gov.br/inep/pt-br/assuntos/noticias/saeb"):
    links(u, r"alfabetiz|download\.inep|\.xlsx|\.zip")

c.log("\n# FNDE - todos os produtos")
for pg in range(0, 15):
    try:
        st, h, b = pegar(f"https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products?page={pg}&size=10")
        if h.get("Content-Encoding") == "gzip":
            b = gzip.decompress(b)
        d = json.loads(b)
        itens = d if isinstance(d, list) else d.get("content") or d.get("items") or d.get("data") or []
        if pg == 0 and not isinstance(d, list):
            c.log(f"   chaves da página: {[k for k in d if k not in ('content', 'items', 'data')]} {dict((k, d[k]) for k in d if k in ('totalElements', 'totalPages', 'total'))}")
        if not itens:
            break
        for p in itens:
            c.log(f"   {p.get('id')}: {p.get('name')} | atualizado {p.get('updatedAt')}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   página {pg}: {str(e)[:100]}")
        break

c.log("\n# ObrasGov")
for q in ("uf=MT&pagina=0&tamanhoDaPagina=1", "uf=MT&codigoMunicipio=5106752&pagina=0&tamanhoDaPagina=5",
          "uf=MT&municipio=PONTES%20E%20LACERDA&pagina=0&tamanhoDaPagina=5", "uf=MT&natureza=Obra&pagina=0&tamanhoDaPagina=1"):
    try:
        st, h, b = pegar("https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?" + q)
        d = json.loads(b)
        cont = d.get("content", [])
        c.log(f"   {q}: total {d.get('totalElements') or d.get('totalRegistros')} | chaves {[k for k in d if k != 'content']}")
        for o in cont[:5]:
            c.log("      " + json.dumps(o, ensure_ascii=False)[:900])
    except Exception as e:  # noqa: BLE001
        c.log(f"   {q}: ERRO {str(e)[:100]}")

links("https://portaldatransparencia.gov.br/download-de-dados/pe-de-meia", r"pe-de-meia|\.zip|20\d\d")
links("https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia", r"bolsa|\.zip|20\d\d")
