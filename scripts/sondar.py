import json, urllib.request, time
API="https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
def g(q):
    t=time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(API+"?"+q, headers={"Accept":"application/json","User-Agent":"SaudeJa/1.0"}), timeout=60) as r:
            j=json.loads(r.read()); l=j.get("estabelecimentos", j) if isinstance(j,dict) else j
            return len(l), round(time.time()-t,1), (list(j)[:5] if isinstance(j,dict) else "")
    except Exception as e: return str(e)[:80]
for tipo in (2,1,70):
    for off in (0,20,40,60,100,200):
        print("#", tipo, off, g(f"limit=20&offset={off}&status=1&codigo_uf=51&codigo_tipo_unidade={tipo}"))
print("# limit100", g("limit=100&offset=0&status=1&codigo_uf=51&codigo_tipo_unidade=2"))
