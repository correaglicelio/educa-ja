"""
Educa Já - Endereço, telefone e localização (latitude/longitude) das escolas.

Fonte: INEP, Catálogo de Escolas (InepData). O painel é um Oracle Analytics com acesso anônimo:
  1) abre o portal (o servidor cria uma sessão anônima e devolve cookies);
  2) pede a análise "Tabela da lista das escolas - Detalhado" em CSV (todas as escolas do Brasil, ~210 mil).

Gera public/data/locais/<código UF>.json e meta.json:
  {escola: [latitude, longitude, "endereço", "telefone"]}

Uso: python scripts/coletar_locais.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import csv
import http.cookiejar
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

BASE = "https://anonymousdata.inep.gov.br/analytics/saw.dll"
PORTAL = BASE + "?Portal&PortalPath=" + urllib.parse.quote("/shared/Censo da Educação Básica/_portal/Catálogo de Escolas")
ANALISE = "/shared/Censo da Educação Básica/Catálogo das Escolas/Análises/Lista das Escolas/Análise - Tabela da lista das escolas - Detalhado"
CSV_URL = BASE + "?Go&Path=" + urllib.parse.quote(ANALISE) + "&Action=Download&Format=csv&Extension=.csv"
SAIDA = c.DADOS_PUBLICOS / "locais"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def baixar_catalogo(ufs: list[str]) -> str:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    ultimo = None
    for tentativa in range(4):
        try:
            # a página inicial devolve um formulário escondido (caj_token) que cria a sessão anônima
            pagina = op.open(urllib.request.Request(PORTAL, headers=UA), timeout=120).read().decode("utf-8", "replace")
            m = re.search(r"onLoggingInPageLoad\('([^']+)',(\{.*?\})\)", pagina)
            if m:
                campos = json.loads(m.group(2))
                destino = urllib.parse.urljoin(BASE, m.group(1))
                corpo = urllib.parse.urlencode(campos).encode()
                resp = op.open(urllib.request.Request(destino, data=corpo, headers={**UA, "Content-Type": "application/x-www-form-urlencoded"}), timeout=120).read().decode("utf-8", "replace")
                titulo = re.search(r"<title>(.*?)</title>", resp, re.S)
                c.log(f"   sessão: {sorted(k.name for k in jar)}; resposta: {titulo.group(1).strip() if titulo else resp[:80]!r}")
            else:
                c.log(f"   página inicial sem formulário de acesso: {pagina[:200]!r}")
            partes = []
            for uf in ufs:   # a exportação do INEP para em 100 mil linhas: pedimos um estado por vez
                url = CSV_URL + "&P0=1&P1=eq&P2=" + urllib.parse.quote('"D - Localidade Escola"."Sigla Uf"') + "&P3=" + uf
                with op.open(urllib.request.Request(url, headers=UA), timeout=600) as r:
                    tipo = r.headers.get("Content-Type", "")
                    dados = r.read()
                if "csv" not in tipo:
                    break
                txt = dados.decode("utf-8-sig", errors="replace")
                partes.append(txt if not partes else txt.split("\n", 1)[1] if "\n" in txt else "")
                c.log(f"      {uf}: {txt.count(chr(10)) - 1:,} escolas")
                time.sleep(2)
            else:
                return "\n".join(p.rstrip("\r\n") for p in partes)
            if "csv" not in tipo:
                visivel = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", dados.decode("utf-8", "replace"), flags=re.S)
                raise RuntimeError(f"o INEP devolveu {tipo} em vez de CSV: {' '.join(visivel.split())[:300]}")
        except Exception as e:  # noqa: BLE001
            ultimo = e
            c.log(f"   tentativa {tentativa + 1} falhou: {str(e)[:120]}")
    raise RuntimeError(f"Não consegui baixar o Catálogo de Escolas: {ultimo}")


OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
PALAVRAS_FRACAS = {"ESCOLA", "ESC", "E", "EM", "EE", "EMEF", "EMEI", "EMEIEF", "EEEF", "EEEM", "MUNICIPAL", "ESTADUAL",
                   "CEI", "CMEI", "CENTRO", "EDUCACIONAL", "EDUCACAO", "INFANTIL", "DE", "DA", "DO", "DOS", "DAS",
                   "PROF", "PROFESSOR", "PROFESSORA", "ENSINO", "FUNDAMENTAL", "MEDIO", "CRECHE", "COLEGIO", "UNIDADE"}


def nucleo(nome: str) -> str:
    """'EM Professora Rosilei Pereira dos Santos' -> 'ROSILEI PEREIRA SANTOS' (sem prefixos e palavras de ligação)."""
    palavras = re.sub(r"[^A-Z0-9 ]", " ", c.sem_acento(nome or "").upper()).split()
    return " ".join(w for w in palavras if w not in PALAVRAS_FRACAS and len(w) > 1)


def escolas_osm(uf: str) -> list[tuple[str, float, float]]:
    q = (f'[out:json][timeout:180];area["ISO3166-2"="BR-{uf}"]->.a;'
         '(nwr["amenity"~"^(school|kindergarten|college)$"](area.a););out tags center;')
    for srv in OVERPASS:
        try:
            req = urllib.request.Request(srv, data=("data=" + urllib.parse.quote(q)).encode(), headers={"User-Agent": "EducaJa/1.0 (dados abertos)"})
            with urllib.request.urlopen(req, timeout=240) as r:
                el = json.load(r).get("elements", [])
            out = []
            for e in el:
                nome = (e.get("tags") or {}).get("name")
                lat = e.get("lat") or (e.get("center") or {}).get("lat")
                lon = e.get("lon") or (e.get("center") or {}).get("lon")
                if nome and lat and lon:
                    out.append((nucleo(nome), round(lat, 5), round(lon, 5)))
            return out
        except Exception as e:  # noqa: BLE001
            c.log(f"      OpenStreetMap {uf} ({srv.split('/')[2]}): {str(e)[:80]}")
            time.sleep(10)
    return []


def km(a, b) -> float:
    import math
    dy = (a[0] - b[0]) * 111
    dx = (a[1] - b[1]) * 111 * math.cos(math.radians(a[0]))
    return (dx * dx + dy * dy) ** .5


def coord(v: str) -> float | None:
    try:
        x = float(v.replace(",", "."))
    except (ValueError, AttributeError):
        return None
    return round(x, 5) if x else None


def main() -> None:
    ufs = c.ufs_escolhidas()
    siglas = set(ufs)
    c.log(f"Educa Já - localização das escolas (Catálogo do INEP) - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    texto = baixar_catalogo(ufs)
    por_uf: dict[str, dict] = {}
    nomes: dict[str, tuple] = {}          # escola -> (núcleo do nome, código do município)
    casa = c.CasadorMunicipios()
    total = sem = 0
    for d in csv.DictReader(io.StringIO(texto)):
        uf = (d.get("UF") or "").strip()
        if uf not in siglas:
            continue
        cod = c.inteiro(d.get("Código INEP"))
        if not cod:
            continue
        lat, lon = coord(d.get("Latitude")), coord(d.get("Longitude"))
        # coordenadas fora do Brasil são erro de cadastro
        if lat is None or lon is None or not (-34 < lat < 6 and -74 < lon < -32):
            lat = lon = None
            sem += 1
        end = " ".join((d.get("Endereço") or "").split()).rstrip(".")
        tel = (d.get("Telefone") or "").strip()
        por_uf.setdefault(uf, {})[str(cod)] = [lat, lon, end, tel]
        nomes[str(cod)] = (nucleo(d.get("Escola", "")), casa.codigo(d.get("Município", ""), uf))
        total += 1
    c.log(f"   {total:,} escolas; sem localização válida no Catálogo: {sem:,}")
    # completa com o OpenStreetMap: nome parecido e perto das outras escolas do mesmo município.
    # As localizações achadas ficam guardadas; cada estado só é consultado de novo a cada 90 dias.
    import difflib
    from datetime import date, timedelta
    antigo_meta = c.ler_json(SAIDA / "meta.json", {}) or {}
    tentado = dict(antigo_meta.get("osm_consultado", {}))
    achadas = reaproveitadas = 0
    for uf in ufs:
        velho = c.ler_json(SAIDA / f"{c.SIGLAS[uf]}.json", {}) or {}
        for k, v in por_uf.get(uf, {}).items():
            antes = velho.get(k)
            if v[0] is None and antes and len(antes) > 4 and antes[4] == 1 and antes[0] is not None:
                v[0:2] = antes[0:2]
                v.append(1)
                reaproveitadas += 1
        faltam = [k for k, v in por_uf.get(uf, {}).items() if v[0] is None and nomes[k][0] and nomes[k][1]]
        if not faltam or tentado.get(uf, "") > (date.today() - timedelta(days=90)).isoformat():
            continue
        tentado[uf] = date.today().isoformat()
        centro: dict = {}
        for k, v in por_uf[uf].items():
            if v[0] is not None and nomes[k][1]:
                centro.setdefault(nomes[k][1], []).append((v[0], v[1]))
        centro = {m: (sorted(p[0] for p in ps)[len(ps) // 2], sorted(p[1] for p in ps)[len(ps) // 2]) for m, ps in centro.items()}
        osm = escolas_osm(uf)
        time.sleep(3)
        for k in faltam:
            nome, mun = nomes[k]
            if mun not in centro:
                continue
            perto = [o for o in osm if km(centro[mun], (o[1], o[2])) < 40]
            melhor = max(perto, key=lambda o: difflib.SequenceMatcher(None, nome, o[0]).ratio(), default=None)
            if melhor and difflib.SequenceMatcher(None, nome, melhor[0]).ratio() >= 0.86:
                por_uf[uf][k][0:2] = [melhor[1], melhor[2]]
                por_uf[uf][k].append(1)        # 1 = localização vinda do OpenStreetMap
                achadas += 1
        c.log(f"      {uf}: {len(osm):,} escolas no OpenStreetMap; completadas até agora: {achadas:,}")
    c.log(f"   localizações completadas pelo OpenStreetMap: {achadas:,} novas, {reaproveitadas:,} guardadas de antes")
    gerados = []
    for uf in ufs:
        if uf not in por_uf:
            continue
        cod_uf = c.SIGLAS[uf]
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", por_uf[uf])
        com = sum(1 for v in por_uf[uf].values() if v[0] is not None)
        c.log(f"   {uf}: {len(por_uf[uf]):,} escolas, {com:,} com localização ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)), "osm_consultado": tentado,
        "fonte": "INEP, Catálogo de Escolas (InepData): endereço, telefone e localização informados pelas escolas no Censo Escolar; "
                 "localizações que faltavam completadas pelo OpenStreetMap (© colaboradores do OpenStreetMap, ODbL)",
        "aviso": "A localização é informada pela própria escola e pode ter erros. Confira o endereço antes de ir.",
    })
    pl = por_uf.get("MT", {})
    if pl:
        amostra = {k: pl[k] for k in ("51025892", "51026309") if k in pl}
        c.log(f"Conferência Pontes e Lacerda: {amostra}")
        c.resumo_github([f"**Localização das escolas:** {total:,} escolas, {total - sem:,} com coordenadas."])


if __name__ == "__main__":
    main()
