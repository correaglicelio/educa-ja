"""Sonda RÁPIDA: cabeçalho e exemplo dos anuais do satélite de referência."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

B = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/"
for ano in (2025, 2023, 2019):
    u = f"{B}anual/Brasil_sat_ref/focos_br_ref_{ano}.zip"
    c.log(f"\n# {ano}")
    try:
        with c.abrir(u, tentativas=1, timeout=90) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        with z.open(z.namelist()[0]) as f:
            t = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
            for i, l in enumerate(t):
                if i < 3:
                    c.log("   " + l.rstrip()[:260])
                else:
                    break
            n = 3 + sum(1 for _ in t)
        c.log(f"   linhas: {n:,}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:140]}")
