"""Sonda RÁPIDA: Anvisa (avisos) e tempo (INMET, Open-Meteo): no ar? formato? CORS?"""
from __future__ import annotations
import re, sys, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; HubJa-sonda/1.0)"
def ver(url, n=700, origin=True):
    print(f"\n# {url}", flush=True)
    h = {"User-Agent": UA, "Accept": "*/*"}
    if origin: h["Origin"] = "https://hubja.com.br"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
            b = r.read(400000)
            print(f"   {r.status} {r.headers.get('Content-Type')} ACAO={r.headers.get('Access-Control-Allow-Origin')} bytes>={len(b)}")
            t = b.decode("utf-8", "replace")
            print("   " + re.sub(r"\s+", " ", t[:n]))
            return t
    except urllib.error.HTTPError as e:
        print(f"   HTTP {e.code} {e.reason}")
    except Exception as e:  # noqa: BLE001
        print(f"   FALHOU: {str(e)[:150]}")
    return ""

A = "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa"
t = ver(A, 300)
for m in sorted(set(re.findall(r'href="([^"]*(?:rss|RSS|feed)[^"]*)"', t)))[:5]: print("   link rss na página:", m)
print("   itens com data na página:", len(re.findall(r"\d{2}/\d{2}/\d{4}", t)))
print("   exemplo de links de notícia:", re.findall(r'href="(https://www\.gov\.br/anvisa/pt-br/assuntos/noticias-anvisa/20[^"]+)"', t)[:3])
for u in (A + "/RSS", A + "/rss.xml", "https://www.gov.br/anvisa/pt-br/RSS", "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/@@search?format=rss"):
    ver(u, 500)
I = "https://apiprevmet3.inmet.gov.br"
ver(I + "/avisos/ativos", 600)
ver(I + "/avisos/rss", 400)
ver(I + "/previsao/5106752", 900)
ver("https://api.open-meteo.com/v1/forecast?latitude=-15.23&longitude=-59.34&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weathercode&timezone=America%2FCuiaba&forecast_days=7", 500)
