"""Sonda 4: itens da API JSON da Anvisa."""
import json, urllib.request
UA = "Mozilla/5.0 (compatible; HubJa-sonda/1.0)"
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=60) as r:
        return r.status, r.read()
for base in ("https://www.gov.br/anvisa/pt-br/@search", "https://www.gov.br/anvisa/++api++/pt-br/@search"):
    u = base + "?portal_type=News%20Item&sort_on=effective&sort_order=reverse&b_size=6&metadata_fields=effective&metadata_fields=description"
    try:
        s, b = get(u); j = json.loads(b)
        print("#", base, s, len(b), "total", j.get("items_total"))
        print("campos:", list(j["items"][0]))
        for it in j["items"][:6]: print(" ", it.get("effective", "")[:10], "|", it.get("title"), "|", it.get("@id"))
        s, b = get(u + "&SearchableText=recolhimento"); j = json.loads(b)
        print("recolhimento:", j.get("items_total"))
        for it in j["items"][:3]: print(" ", it.get("effective", "")[:10], "|", it.get("title"))
    except Exception as e: print("ERRO", base, str(e)[:150])
