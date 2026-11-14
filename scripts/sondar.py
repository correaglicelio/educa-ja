"""Sonda RÁPIDA dos arquivos de focos do INPE: tamanho, colunas e 3 linhas de exemplo (lê só o começo)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

B = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/"
ARQ = [B + "mensal/Brasil/focos_mensal_br_202610.csv", B + "mensal/Brasil/focos_mensal_br_201901.csv",
       B + "mensal/Brasil/focos_mensal_br_202511.csv", B + "diario/Brasil/focos_diario_br_20261113.csv",
       B + "anual/Brasil_todos_sats/focos_br_todos-sats_2025.zip"]
for u in ARQ:
    c.log(f"\n# {u.split('/')[-1]}")
    try:
        with c.abrir(u, tentativas=1, timeout=40) as r:
            c.log(f"   tipo={r.headers.get('Content-Type')} tamanho={r.headers.get('Content-Length')} bytes")
            ini = r.read(3000)
        if u.endswith(".zip"):
            continue
        linhas = ini.decode("utf-8", "replace").splitlines()
        for l in linhas[:4]:
            c.log("   " + l[:300])
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:140]}")
