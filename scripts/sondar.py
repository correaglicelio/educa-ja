"""Sonda RÁPIDA: ObrasGov (projetos de investimento) - está no ar? campos? tamanho? datas?"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

B = "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento"
for u in (f"{B}?uf=MT&pagina=0&tamanhoDaPagina=5", f"{B}/geometria?uf=MT&pagina=0&tamanhoDaPagina=2"):
    c.log(f"\n# {u}")
    try:
        with c.abrir(u, tentativas=2, timeout=60) as r:
            raw = r.read()
        j = json.loads(raw)
        c.log(f"   bytes {len(raw)}; chaves {list(j)[:8] if isinstance(j, dict) else type(j)}")
        itens = j.get("content") or j.get("data") or (j if isinstance(j, list) else [])
        for k in ("totalElements", "totalPages", "total", "size"):
            if isinstance(j, dict) and k in j: c.log(f"   {k}: {j[k]}")
        if itens:
            c.log("   campos: " + ", ".join(itens[0].keys()))
            c.log("   exemplo: " + json.dumps(itens[0], ensure_ascii=False)[:1500])
    except Exception as e:  # noqa: BLE001
        c.log(f"   FALHOU: {str(e)[:200]}")
