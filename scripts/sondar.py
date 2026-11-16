import json, urllib.request
UA = "Mozilla/5.0 (compatible; HubJa-sonda/1.0)"
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=60) as r: return r.read()
j = json.loads(get("https://apiprevmet3.inmet.gov.br/previsao/5106752"))
def cortar(o, d=0):
    if isinstance(o, dict): return {k: cortar(v, d+1) for k, v in list(o.items())[:12]}
    if isinstance(o, list): return [cortar(v, d+1) for v in o[:2]]
    if isinstance(o, str): return o[:50]
    return o
print("#", json.dumps(cortar(j), ensure_ascii=False)[:3500])
