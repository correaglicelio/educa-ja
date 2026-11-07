"""
Educa Já - sonda de fontes novas (roda no GitHub, onde os sites do governo respondem).
Hoje: localização das escolas (OpenStreetMap e colunas de endereço do Censo Escolar).
Uso: python scripts/sondar.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

# 1) Censo: colunas de endereço/localização da tabela de escolas
try:
    z, ano = c.censo_escolar()
    nome = c.tabela_censo(z, "Escola")
    with z.abrir(nome) as f:
        linhas = c.linhas_csv(f)
        cab = next(linhas)
        c.log(f"Censo {ano}: colunas de endereço: {[k for k in cab if any(x in k for x in ('CEP', 'END', 'BAIRRO', 'LAT', 'LON', 'COORD', 'TELEF'))]}")
        idx = {k: i for i, k in enumerate(cab)}
        for lin in linhas:
            if lin[idx["CO_ENTIDADE"]] in ("51025892", "51026309"):
                c.log("   " + " | ".join(f"{k}={lin[idx[k]]}" for k in cab if any(x in k for x in ("CEP", "END", "BAIRRO", "LAT", "LON"))))
except Exception as e:  # noqa: BLE001
    c.log(f"Censo: falhou ({e})")

# 2) OpenStreetMap: escolas em MT e quantas têm código INEP
q = '[out:json][timeout:180];area["ISO3166-2"="BR-MT"]->.a;(nwr["amenity"~"school|kindergarten"](area.a););out tags center;'
for srv in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"):
    try:
        req = urllib.request.Request(srv, data=("data=" + urllib.parse.quote(q)).encode(), headers={"User-Agent": "EducaJa/1.0"})
        with urllib.request.urlopen(req, timeout=200) as r:
            el = json.load(r).get("elements", [])
        chaves = Counter(k for e in el for k in e.get("tags", {}) if any(x in k.lower() for x in ("inep", "ref")))
        com = [e for e in el if any("inep" in k.lower() for k in e.get("tags", {}))]
        c.log(f"OSM ({srv}): {len(el)} escolas em MT; com código INEP: {len(com)}; chaves: {dict(chaves)}")
        pl = [e for e in el if e.get("center") and -15.4 < e["center"]["lat"] < -15.1 and -59.5 < e["center"]["lon"] < -59.2]
        for e in pl[:30]:
            t = e["tags"]
            c.log(f"   PL: {t.get('name')} | {[(k, v) for k, v in t.items() if 'inep' in k.lower() or 'ref' in k.lower()]}")
        break
    except Exception as e:  # noqa: BLE001
        c.log(f"OSM {srv}: falhou ({e})")
