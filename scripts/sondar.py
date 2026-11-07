"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: transferências da educação (FNDE) mês a mês no Portal da Transparência (CGU).
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

ACOES = {"00PI": "PNAE", "0969": "PNATE", "0515": "PDDE", "0369": "Salário-educação"}
for ano in (2026, 2025):
    nac = defaultdict(lambda: [0, 0.0])
    pl = defaultdict(float)
    for mes in range(1, 13):
        ref = f"{ano}{mes:02d}"
        try:
            with c.abrir(f"https://portaldatransparencia.gov.br/download-de-dados/transferencias/{ref}", timeout=300) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
        except Exception as e:  # noqa: BLE001
            c.log(f"{ref}: sem arquivo ({str(e)[:60]})")
            continue
        with z.open(z.namelist()[0]) as f:
            leitor = csv.reader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
            cab = next(leitor)
            i_acao, i_val, i_mun, i_uf = cab.index("AÇÃO"), cab.index("VALOR TRANSFERIDO"), cab.index("NOME MUNICÍPIO"), cab.index("UF")
            for lin in leitor:
                a = ACOES.get(lin[i_acao])
                if not a:
                    continue
                v = float(lin[i_val].replace(".", "").replace(",", ".") or 0)
                nac[(ref, a)][0] += 1
                nac[(ref, a)][1] += v
                if lin[i_uf] == "MT" and lin[i_mun] == "PONTES E LACERDA":
                    pl[(ref, a)] += v
    c.log(f"===== {ano}: linhas e valor no Brasil | Pontes e Lacerda")
    for ref in sorted({k[0] for k in nac}):
        partes = [f"{a}: {nac[(ref, a)][0]} linhas R$ {nac[(ref, a)][1] / 1e6:,.1f} mi | PL R$ {pl[(ref, a)]:,.2f}" for a in ACOES.values() if (ref, a) in nac]
        c.log(f"   {ref}  " + " ;; ".join(partes))
