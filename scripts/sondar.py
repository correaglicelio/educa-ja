"""Sonda RÁPIDA: qual satélite é a referência (anual) e quanto aparece no mensal de 2026."""
from __future__ import annotations

import io
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

B = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/"


def contar(linhas, rotulo):
    cab = None
    sat, mt = Counter(), Counter()
    n = 0
    for l in linhas:
        l = l.rstrip("\n")
        if cab is None:
            cab = l.split(",")
            i_sat, i_uf = cab.index("satelite"), cab.index("estado")
            c.log(f"   {rotulo}: colunas {cab}")
            continue
        p = l.split(",")
        if len(p) <= max(i_sat, i_uf):
            continue
        n += 1
        sat[p[i_sat]] += 1
        if p[i_uf] == "MATO GROSSO":
            mt[p[i_sat]] += 1
    c.log(f"   {rotulo}: linhas={n:,}; satélites={dict(sat.most_common(6))}; MT por satélite={dict(mt.most_common(6))}")


for ano in (2025, 2019):
    u = f"{B}anual/Brasil_sat_ref/focos_br_ref_{ano}.zip"
    c.log(f"\n# {u.split('/')[-1]}")
    try:
        with c.abrir(u, tentativas=1, timeout=90) as r:
            dados = r.read()
        z = zipfile.ZipFile(io.BytesIO(dados))
        nome = z.namelist()[0]
        c.log(f"   dentro do zip: {z.namelist()}")
        with z.open(nome) as f:
            contar(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), nome)
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:140]}")

for mes in ("202609",):
    u = f"{B}mensal/Brasil/focos_mensal_br_{mes}.csv"
    c.log(f"\n# {u.split('/')[-1]} (arquivo inteiro, só contagem)")
    try:
        with c.abrir(u, tentativas=1, timeout=170) as r:
            contar(io.TextIOWrapper(r, encoding="utf-8", errors="replace"), mes)
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:140]}")
