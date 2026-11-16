"""Sonda RÁPIDA 3: avisos INMET (tamanho e campos) e itens da API JSON da Anvisa."""
from __future__ import annotations
import json, re, sys, urllib.request, urllib.error, collections
UA = "Mozilla/5.0 (compatible; HubJa-sonda/1.0)"
def get(url, accept="application/json", n=20_000_000):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip"}), timeout=60) as r:
            return r.status, r.headers, r.read(n)
    except Exception as e:  # noqa: BLE001
        return str(e)[:100], {}, b""
s, h, b = get("https://apiprevmet3.inmet.gov.br/avisos/ativos")
print("# avisos/ativos", s, "bytes", len(b), "enc", h.get("Content-Encoding"), "length", h.get("Content-Length"))
j = json.loads(b)
print("chaves:", {k: (len(v) if isinstance(v, list) else v) for k, v in j.items()})
av = [a for v in j.values() if isinstance(v, list) for a in v]
print("campos:", list(av[0]))
x = {k: (v if k not in ("poligono", "geocodes", "municipios") else f"<{type(v).__name__} {len(str(v))} chars>") for k, v in av[0].items()}
print("exemplo:", json.dumps(x, ensure_ascii=False)[:1800])
for k in ("geocodes", "municipios", "estados", "ibge"):
    if k in av[0]: print(k, "->", str(av[0][k])[:300])
print("severidades:", collections.Counter(a.get("severidade") for a in av).most_common(6))
mt = [a for a in av if re.search(r"5106752|Pontes e Lacerda", json.dumps(a, ensure_ascii=False))]
print("avisos que citam Pontes e Lacerda/5106752:", len(mt))
mt2 = [a for a in av if "MT" in str(a.get("estados", "")) or "Mato Grosso" in json.dumps(a, ensure_ascii=False)]
print("avisos que citam MT:", len(mt2))
print("\n# Anvisa @search")
u = "https://www.gov.br/anvisa/++api++/pt-br/@search?portal_type=News%20Item&sort_on=effective&sort_order=reverse&b_size=6&metadata_fields=effective&metadata_fields=description"
s, h, b = get(u); print(s, len(b))
j = json.loads(b); print("total:", j.get("items_total"))
for it in j["items"][:6]: print(" ", json.dumps({k: v for k, v in it.items() if k in ("title", "effective", "@id", "description", "review_state")}, ensure_ascii=False)[:420])
print("campos do item:", list(j["items"][0]))
u2 = u + "&SearchableText=recolhimento"
s, h, b = get(u2); j = json.loads(b); print("\nbusca 'recolhimento':", s, j.get("items_total"))
for it in j["items"][:4]: print(" ", it.get("effective", "")[:10], it.get("title"), it.get("@id"))
