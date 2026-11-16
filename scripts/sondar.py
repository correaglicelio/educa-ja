"""Sonda RÁPIDA 2: estrutura do INMET (avisos e previsão) e API JSON da Anvisa (gov.br)."""
from __future__ import annotations
import json, re, sys, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; HubJa-sonda/1.0)"
def get(url, accept="*/*", origin=None, n=400000):
    h = {"User-Agent": UA, "Accept": accept}
    if origin: h["Origin"] = origin
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
            return r.status, r.headers, r.read(n)
    except urllib.error.HTTPError as e:
        return e.code, {}, b""
    except Exception as e:  # noqa: BLE001
        return str(e)[:100], {}, b""

print("# INMET avisos/ativos")
s, h, b = get("https://apiprevmet3.inmet.gov.br/avisos/ativos", "application/json", "https://exemplo.com")
print("  status", s, "ACAO com origem estranha:", h.get("Access-Control-Allow-Origin"), "gzip:", h.get("Content-Encoding"), "bytes", len(b))
try:
    j = json.loads(b); print("  chaves topo:", list(j))
    for k, v in j.items():
        if isinstance(v, list) and v:
            print(f"  {k}: {len(v)} avisos; campos: {list(v[0])}")
            x = {kk: (vv if kk != "poligono" else "...") for kk, vv in v[0].items()}
            print("  exemplo:", json.dumps(x, ensure_ascii=False)[:1400])
            mt = [a for a in v if "MT" in json.dumps(a, ensure_ascii=False) or "Mato Grosso" in json.dumps(a, ensure_ascii=False)]
            print("  avisos que citam MT:", len(mt))
            if mt: print("  um de MT:", json.dumps({kk: vv for kk, vv in mt[0].items() if kk != "poligono"}, ensure_ascii=False)[:1200])
            break
except Exception as e:  # noqa: BLE001
    print("  json falhou", str(e)[:100], b[:200])
print("\n# INMET previsão estrutura")
s, h, b = get("https://apiprevmet3.inmet.gov.br/previsao/5106752", "application/json", "https://hubja.com.br")
print("  status", s, "bytes lidos", len(b), "gzip:", h.get("Content-Encoding"), "length:", h.get("Content-Length"))
try:
    j = json.loads(b)["5106752"]; print("  dias:", list(j)[:10])
    d = next(iter(j.values())); print("  períodos:", list(d))
    p = next(iter(d.values())); print("  campos:", [k for k in p if k != "icone"], "| tamanho do ícone:", len(p.get("icone", "")))
except Exception as e:  # noqa: BLE001
    print("  parcial/erro", str(e)[:100])
print("\n# INMET outras rotas")
for u in ("https://apiprevmet3.inmet.gov.br/previsao/proximosdias/5106752", "https://apiprevmet3.inmet.gov.br/estacoes/proximas/5106752", "https://apiprevmet3.inmet.gov.br/avisos/futuro", "https://apiprevmet3.inmet.gov.br/avisos/5106752"):
    s, h, b = get(u, "application/json", "https://hubja.com.br"); print(" ", u.split("br/")[1], s, len(b), b[:160])
print("\n# Anvisa JSON")
A = "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa"
for u, acc in ((A, "application/json"), (A + "?b_size=10", "application/json"),
               ("https://www.gov.br/anvisa/pt-br/@search?portal_type=News%20Item&sort_on=effective&sort_order=reverse&b_size=5&metadata_fields=effective", "application/json"),
               ("https://www.gov.br/anvisa/++api++/pt-br/@search?portal_type=News%20Item&sort_on=effective&sort_order=reverse&b_size=5&metadata_fields=effective", "application/json"),
               (A + "/@search?sort_on=effective&sort_order=reverse&b_size=5&metadata_fields=effective", "application/json")):
    s, h, b = get(u, acc); t = b.decode("utf-8", "replace")
    print("\n ", u[-110:], "->", s, h.get("Content-Type") if h else "", len(b)); print("   ", re.sub(r"\s+", " ", t[:500]))
