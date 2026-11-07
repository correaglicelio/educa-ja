"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: professores (AFD, IRD, IED, ICG, remuneração), INSE, prestação de contas do PDDE e Criança Alfabetizada.
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import gzip
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

IND = "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{ano}/{nome}"


def teste(url: str) -> bool:
    try:
        i = c.info(url)
        c.log(f"   OK  {url.split('/')[-2]}/{url.split('/')[-1]}: {i['bytes'] / 1e6:.1f} MB, {i['modificado']}")
        return True
    except Exception as e:  # noqa: BLE001
        c.log(f"   --  {url.split('/')[-2]}/{url.split('/')[-1]}: {str(e)[:60]}")
        return False


c.log("# Indicadores de professores (INEP)")
achados = []
for ano in (2025, 2024):
    for sig in ("AFD", "IRD", "IED", "ICG", "DSU"):
        for suf in ("ESCOLAS", "MUNICIPIOS"):
            for nome in (f"{sig}_{ano}_{suf}.zip", f"{sig.lower()}_{ano}_{suf.lower()}.zip"):
                u = IND.format(ano=ano, nome=nome)
                if teste(u):
                    achados.append(u)
                    break
for u in achados[:3]:
    try:
        z = c.ZipRemoto(u)
        c.log(f"   conteúdo de {u.split('/')[-1]}: {list(z.arquivos)[:6]}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   zip {u}: {e}")

c.log("\n# Remuneração média dos docentes")
for ano in (2025, 2024, 2023, 2022, 2021):
    for nome in (f"remuneracao_media_docentes_{ano}.zip", f"Remuneracao_Media_Docentes_{ano}.zip", f"REMUNERACAO_{ano}.zip",
                 f"remuneracao_docentes_{ano}.zip"):
        teste(IND.format(ano=ano, nome=nome))

c.log("\n# INSE")
for ano in (2023, 2021, 2019):
    for nome in (f"nivel_socioeconomico/INSE_{ano}_escolas.xlsx", f"nivel_socioeconomico/INSE_{ano}.zip",
                 f"nivel_socioeconomico/INSE_{ano}_escolas.zip", f"nivel_socioeconomico/INSE_{ano}_municipios.xlsx",
                 f"INSE_{ano}.zip", f"nivel_socioeconomico/inse_{ano}.zip"):
        teste(IND.format(ano=ano, nome=nome))

c.log("\n# FNDE produto 59 - Consulta Prestação de Contas do PDDE")
API = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products/{id}/"
for pid in (59,):
    try:
        c.log(f"   metadados: {c.get_json(API.format(id=pid) + 'artifact-metadata')}")
        with c.abrir(API.format(id=pid) + "artifact", timeout=300) as r:
            t = io.TextIOWrapper(gzip.GzipFile(fileobj=r), encoding="utf-8", errors="replace")
            linhas = 0
            uf = {}
            for k, lin in enumerate(t):
                if k < 4:
                    c.log(f"   {lin.strip()[:700]}")
                if "MT" in lin.split(";")[:12] and "PONTES E LACERDA" in lin.upper() and k < 10_000_000 and uf.get("pl", 0) < 6:
                    c.log(f"   PL: {lin.strip()[:500]}")
                    uf["pl"] = uf.get("pl", 0) + 1
                linhas += 1
            c.log(f"   linhas: {linhas:,}")
    except Exception as e:  # noqa: BLE001
        c.log(f"   falhou: {e}")
