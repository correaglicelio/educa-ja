import json, urllib.request, time
API="https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
def g(q):
    t=time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(API+"?"+q, headers={"Accept":"application/json","User-Agent":"SaudeJa/1.0"}), timeout=60) as r:
            j=json.loads(r.read()); l=j.get("estabelecimentos", j) if isinstance(j,dict) else j
            return len(l), round(time.time()-t,1), (list(j)[:5] if isinstance(j,dict) else "")
    except Exception as e: return str(e)[:80]

def tudo(q, maxoff=2000):
    n=0; off=0
    while off<maxoff:
        r=g(q+f"&limit=20&offset={off}")
        if not isinstance(r,tuple) or r[0]==0: break
        n+=r[0]; off+=20
        if r[0]<20: break
    return n
for mun in ("510340","510675","510795"):
    print("# mun",mun,"sem tipo",tudo(f"status=1&codigo_municipio={mun}"),"tipo2",tudo(f"status=1&codigo_municipio={mun}&codigo_tipo_unidade=2"),"tipo1",tudo(f"status=1&codigo_municipio={mun}&codigo_tipo_unidade=1"))
print("# uf51 sem tipo", tudo("status=1&codigo_uf=51"))
