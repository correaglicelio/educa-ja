"""Sonda RÁPIDA: pastas do INPE (anual / satélite de referência) e mistura de satélites. Lê pouco."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

B = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/"


def listar(sub):
    c.log(f"\n# pasta {sub}")
    try:
        with c.abrir(B + sub, tentativas=1, timeout=30) as r:
            t = r.read(400_000).decode("utf-8", "replace")
        itens = re.findall(r'href="([^"?/][^"]*)"', t)
        c.log(f"   {len(itens)} itens; primeiros {itens[:4]}; últimos {itens[-4:]}")
        return itens
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:120]}")
        return []


listar("")
for sub in ("anual/", "anual/Brasil_todos_sats/", "anual/Brasil_sat_ref/", "mensal/", "mensal/Brasil/"):
    listar(sub)

for u in [B + "anual/Brasil_sat_ref/focos_br_ref_2025.zip", B + "anual/Brasil_sat_ref/focos_br_ref_2019.zip"]:
    try:
        with c.abrir(u, tentativas=1, timeout=30) as r:
            c.log(f"\n# {u.split('/')[-1]}: tipo={r.headers.get('Content-Type')} tamanho={r.headers.get('Content-Length')}")
    except Exception as e:  # noqa: BLE001
        c.log(f"\n# {u.split('/')[-1]}: FALHOU {str(e)[:80]}")

c.log("\n# mistura de satélites e estados nos primeiros ~6 MB de focos_mensal_br_202510.csv")
try:
    with c.abrir(B + "mensal/Brasil/focos_mensal_br_202510.csv", tentativas=1, timeout=60) as r:
        t = r.read(6_000_000).decode("utf-8", "replace").splitlines()[1:-1]
    sat, uf = Counter(), Counter()
    for l in t:
        p = l.split(",")
        sat[p[4]] += 1
        uf[p[6]] += 1
    c.log(f"   linhas lidas: {len(t):,}; satélites: {dict(sat.most_common(8))}; MT: {uf.get('MATO GROSSO', 0)}")
except Exception as e:  # noqa: BLE001
    c.log(f"   FALHOU: {str(e)[:120]}")
