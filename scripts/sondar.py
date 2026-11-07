"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: remuneração dos professores no SIOPE (OData e catálogo do FNDE). Só confere, não grava nada.
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import gzip
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

OD = "https://www.fnde.gov.br/olinda-ide/servico/DADOS_ABERTOS_SIOPE/versao/v1/odata/"
API = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products"


def texto(url, limite=2_000_000):
    with c.abrir(url, tentativas=2, timeout=120) as r:
        return r.read(limite).decode("utf-8", "replace")


c.log("# SIOPE OData: conjuntos disponíveis")
try:
    meta = texto(OD + "$metadata")
    for nome in re.findall(r'EntitySet Name="([^"]+)"', meta) or re.findall(r'FunctionImport Name="([^"]+)"', meta):
        c.log(f"   {nome}")
    for m in re.finditer(r'<EntityType Name="([^"]*[Rr]emun[^"]*)">(.*?)</EntityType>', meta, re.S):
        c.log(f"   campos de {m.group(1)}: {re.findall(r'Property Name=\"([^\"]+)\"', m.group(2))}")
    for m in re.finditer(r'<FunctionImport Name="([^"]*[Rr]emun[^"]*)"(.*?)(/>|</FunctionImport>)', meta, re.S):
        c.log(f"   função {m.group(1)}: {re.findall(r'Parameter Name=\"([^\"]+)\" Type=\"([^\"]+)\"', m.group(2))}")
except Exception as e:  # noqa: BLE001
    c.log(f"   falhou: {e}")

c.log("\n# Catálogo do FNDE: produtos com 'remunera', 'magist', 'profission' ou 'siope'")
achados = {}
for q in ("", "?page=1", "?page=2", "?pageNumber=1", "?offset=10", "?skip=10", "?search=remunera", "?q=remunera", "?name=remunera",
          "?size=200", "?limit=200", "?pageSize=200"):
    try:
        b = c.abrir(API + q, tentativas=1, timeout=60).read()
        try:
            b = gzip.decompress(b)
        except OSError:
            pass
        d = json.loads(b)
        itens = d if isinstance(d, list) else d.get("content") or d.get("items") or d.get("data") or []
        novos = [p for p in itens if p.get("id") not in achados]
        for p in itens:
            achados[p.get("id")] = p
        c.log(f"   {q or '(sem parâmetro)'}: {len(itens)} itens, {len(novos)} novos; chaves {[k for k in d if not isinstance(d, list)][:8] if not isinstance(d, list) else 'lista'}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   {q}: {str(e)[:70]}")
for i in range(1, 121):          # ids conhecidos vão até ~82; testa um a um os que faltam
    if i in achados:
        continue
    try:
        d = c.get_json(f"{API}/{i}", tentativas=1, timeout=30)
        achados[i] = d
    except Exception:  # noqa: BLE001
        pass
c.log(f"   total de produtos conhecidos: {len(achados)}")
for i, p in sorted(achados.items(), key=lambda x: int(x[0] or 0)):
    nome = str(p.get("name") or p.get("title") or "")
    marca = "  <==" if re.search(r"remunera|magist|profission|siope|piso|docente|salar", nome, re.I) else ""
    c.log(f"   {i}: {nome}{marca}")
    if marca:
        try:
            md = c.get_json(f"{API}/{i}/artifact-metadata", tentativas=1, timeout=30)
            c.log(f"        arquivo: {md}")
            with c.abrir(f"{API}/{i}/artifact", tentativas=1, timeout=300) as r:
                t = io.TextIOWrapper(gzip.GzipFile(fileobj=r), encoding="utf-8", errors="replace")
                anos, n, pl = {}, 0, 0
                for k, lin in enumerate(t):
                    if k == 0:
                        cab = lin.strip().split(";")
                        c.log(f"        colunas: {cab}")
                        continue
                    col = lin.strip().split(";")
                    n += 1
                    for j, nm in enumerate(cab):
                        if re.search(r"^an|ano", nm, re.I) and j < len(col):
                            anos[col[j]] = anos.get(col[j], 0) + 1
                            break
                    if "5106752" in lin and pl < 3:
                        # não registra nomes de pessoas: só mostra quais colunas têm valor
                        c.log(f"        exemplo Pontes e Lacerda (só os valores numéricos): {[x for x in col if re.fullmatch(r'[0-9.,-]+', x)][:20]}")
                        pl += 1
                c.log(f"        linhas: {n:,}; anos: {dict(sorted(anos.items())[-8:])}")
        except Exception as e:  # noqa: BLE001
            c.log(f"        leitura falhou: {str(e)[:100]}")
