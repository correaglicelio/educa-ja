"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: colunas dos indicadores de professores (AFD, IRD, IED, ICG) e do INSE, com as linhas de Pontes e Lacerda.
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402
from coletar_fluxo import linhas  # noqa: E402

B = "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/2025/"
tmp = Path(tempfile.mkdtemp())
for sig in ("AFD", "IRD", "IED", "ICG"):
    for nivel, campo, alvo in (("MUNICIPIOS", "CO_MUNICIPIO", "5106752"), ("ESCOLAS", "CO_ENTIDADE", "51026244"),
                               ("BRASIL_REGIOES_UF" + ("" if sig == "AFD" else "S"), "UNIDGEO", "Mato Grosso")):
        c.log(f"\n# {sig} {nivel}")
        try:
            n = 0
            for d in linhas(B + f"{sig}_2025_{nivel}.zip", tmp):
                if n == 0:
                    c.log(f"   códigos: {list(d)}")
                n += 1
                if str(d.get(campo, "")).strip() == alvo or (campo == "UNIDGEO" and n <= 1):
                    c.log("   " + " | ".join(f"{k}={v}" for k, v in d.items() if str(v).strip() not in ("", "--")))
            c.log(f"   {n:,} linhas")
        except Exception as e:  # noqa: BLE001
            c.log(f"   falhou: {e}")

# INSE 2023 (planilha solta, sem zip)
for nome, campo, alvo in (("INSE_2023_escolas.xlsx", "ID_ESCOLA", "51026244"), ("INSE_2023_municipios.xlsx", "ID_MUNICIPIO", "5106752")):
    c.log(f"\n# {nome}")
    try:
        arq = tmp / nome
        with c.abrir(B.replace("2025/", "2023/nivel_socioeconomico/") + nome, timeout=300) as r, open(arq, "wb") as f:
            shutil.copyfileobj(r, f)
        for k, lin in enumerate(c.ler_xlsx(arq, 0)):
            if k < 3:
                c.log(f"   linha {k}: {lin[:30]}")
            elif any(str(v).strip() == alvo for v in lin[:8]):
                c.log(f"   alvo: {lin[:30]}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   falhou: {e}")
shutil.rmtree(tmp, ignore_errors=True)
