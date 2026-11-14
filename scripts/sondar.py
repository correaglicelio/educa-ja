"""Sonda RÁPIDA: Portal da Transparência para o Contas Já."""
from __future__ import annotations
import csv, io, sys, zipfile, collections, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

P = "https://portaldatransparencia.gov.br/download-de-dados/"
def vr(t):
    try: return float(t.strip().replace(".", "").replace(",", "."))
    except ValueError: return 0.0
t0 = time.time()
c.log("# transferências 202609")
with c.abrir(P + "transferencias/202609", timeout=300) as r:
    raw = r.read()
c.log(f"   zip {len(raw)/1e6:.1f} MB em {time.time()-t0:.0f}s")
z = zipfile.ZipFile(io.BytesIO(raw))
c.log("   arquivos: " + str(z.namelist()))
with z.open(z.namelist()[0]) as f:
    rd = csv.reader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
    cab = next(rd); c.log("   colunas: " + " | ".join(cab))
    ix = {k: i for i, k in enumerate(cab)}
    n = 0; porf = collections.Counter(); pl = collections.Counter(); tot_mun = collections.Counter(); ufs = collections.Counter(); ex = []
    for l in rd:
        n += 1
        v = vr(l[ix["VALOR TRANSFERIDO"]])
        ufs[l[ix["UF"]]] += v
        if l[ix["UF"]] == "MT" and "PONTES E LACERDA" in l[ix["NOME MUNICÍPIO"]].upper():
            porf[(l[ix.get("NOME FUNÇÃO", ix["AÇÃO"])] if "NOME FUNÇÃO" in ix else "", l[ix["AÇÃO"]], l[ix.get("NOME AÇÃO", ix["AÇÃO"])] if "NOME AÇÃO" in ix else "")] += v
            pl[l[ix["TIPO FAVORECIDO"]]] += v
            if len(ex) < 2: ex.append(l)
    c.log(f"   linhas {n:,}; UFs com valor {len(ufs)}")
    c.log("   exemplo PL: " + str(ex))
    c.log("   PL por tipo de favorecido: " + str(pl.most_common(5)))
    for k, v in porf.most_common(12): c.log(f"   PL {v:12,.2f}  {k}")
for ref in ("202610", "202611"):
    for ds in ("novo-bolsa-familia", "transferencias"):
        try:
            with c.abrir(P + f"{ds}/{ref}", metodo="HEAD", tentativas=1, timeout=60) as r:
                c.log(f"# HEAD {ds}/{ref}: {r.status} {r.headers.get('Content-Length')} bytes")
        except Exception as e:  # noqa: BLE001
            c.log(f"# HEAD {ds}/{ref}: {str(e)[:80]}")
        time.sleep(5)
