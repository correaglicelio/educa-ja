"""Sonda RÁPIDA 2: ObrasGov MT - tamanho, situações, datas, município?"""
from __future__ import annotations
import json, sys, collections, time
T0 = time.time()
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

B = "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento"
tot = []
p = 0
while True:
    try:
        with c.abrir(f"{B}?uf=MT&pagina={p}&tamanhoDaPagina=100", tentativas=2, timeout=120) as r:
            j = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        c.log(f"FALHOU pg {p}: {str(e)[:150]}"); break
    tot += j["content"]
    c.log(f"pg {p}: {len(j['content'])} (total declarado {j.get('totalElements')}, páginas {j.get('totalPages')})")
    p += 1
    if j.get("last") or p >= 60 or time.time() - T0 > 420: break
c.log(f"itens: {len(tot)}; bytes ~{len(json.dumps(tot))//1024} KB")
cnt = lambda f: collections.Counter(f(x) for x in tot).most_common(12)
c.log("situação: " + str(cnt(lambda x: x["situacao"])))
c.log("natureza: " + str(cnt(lambda x: x["natureza"])))
c.log("ano cadastro: " + str(sorted(collections.Counter((x["dataCadastro"] or "")[:4] for x in tot).items())))
c.log("ano situação: " + str(sorted(collections.Counter((x["dataSituacao"] or "")[:4] for x in tot).items())[-6:]))
c.log("com cep: %d, com endereço: %d" % (sum(bool(x["cep"]) for x in tot), sum(bool(x["endereco"]) for x in tot)))
c.log("nome termina '- MT': %d" % sum(x["nome"].strip().upper().endswith("MT") for x in tot))
c.log("com valor previsto: %d; soma R$ %.0f" % (sum(bool(x["fontesDeRecurso"]) for x in tot), sum(f.get("valorInvestimentoPrevisto") or 0 for x in tot for f in x["fontesDeRecurso"])))
c.log("executores: " + str(collections.Counter(e["nome"] for x in tot for e in x["executores"]).most_common(6)))
c.log("tomadores: " + str(collections.Counter(e["nome"] for x in tot for e in x["tomadores"]).most_common(6)))
pl = [x for x in tot if "PONTES E LACERDA" in json.dumps(x, ensure_ascii=False).upper()]
c.log(f"menciona Pontes e Lacerda: {len(pl)}")
for x in pl[:4]: c.log("  " + x["nome"][:110] + " | " + str(x["situacao"]) + " | " + str(x["endereco"]) + " | " + str(x["cep"]))
c.log("chaves extras com endereço: " + str([(x["endereco"], x["cep"]) for x in tot if x["endereco"]][:4]))
