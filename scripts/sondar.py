"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: arquivo mensal de transferências do Portal da Transparência (CGU).
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

for mes in ("202610", "202609"):
    url = f"https://portaldatransparencia.gov.br/download-de-dados/transferencias/{mes}"
    try:
        with c.abrir(url, timeout=300) as r:
            dados = r.read()
            c.log(f"{mes}: {len(dados) / 1e6:.1f} MB baixados de {getattr(r, 'url', url)}")
    except Exception as e:  # noqa: BLE001
        c.log(f"{mes}: falhou ({e})")
        continue
    z = zipfile.ZipFile(io.BytesIO(dados))
    for i in z.infolist():
        c.log(f"   {i.filename}: {i.file_size / 1e6:.1f} MB")
    nome = z.namelist()[0]
    with z.open(nome) as f:
        leitor = csv.reader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
        cab = next(leitor)
        c.log("   colunas: " + " | ".join(cab))
        acoes, n, pl = Counter(), 0, []
        for lin in leitor:
            n += 1
            txt = ";".join(lin).upper()
            if "FNDE" in txt or "EDUCA" in txt:
                acoes[" / ".join(lin[i] for i, k in enumerate(cab) if "AÇÃO" in k.upper() or "PROGRAMA" in k.upper())[:150]] += 1
            if "PONTES E LACERDA" in txt:
                pl.append(lin)
        c.log(f"   {n:,} linhas; linhas de Pontes e Lacerda: {len(pl)}")
        for lin in pl[:40]:
            c.log("   PL> " + " | ".join(lin))
        c.log("   ações de educação mais comuns:")
        for a, k in acoes.most_common(25):
            c.log(f"      {k:6d}  {a}")
    break
