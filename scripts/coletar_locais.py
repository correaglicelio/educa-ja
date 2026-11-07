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
import sys
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
UA = {"User-Agent": "Mozilla/5.0 (EducaJa; dados abertos)"}


def baixar_catalogo() -> str:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    ultimo = None
    for tentativa in range(4):
        try:
            op.open(urllib.request.Request(PORTAL, headers=UA), timeout=120).read()
            with op.open(urllib.request.Request(CSV_URL, headers=UA), timeout=900) as r:
                tipo = r.headers.get("Content-Type", "")
                dados = r.read()
            if "csv" not in tipo:
                raise RuntimeError(f"o INEP devolveu {tipo} em vez de CSV ({dados[:120]!r})")
            c.log(f"   catálogo: {len(dados) / 1e6:.1f} MB")
            return dados.decode("utf-8-sig", errors="replace")
        except Exception as e:  # noqa: BLE001
            ultimo = e
            c.log(f"   tentativa {tentativa + 1} falhou: {str(e)[:120]}")
    raise RuntimeError(f"Não consegui baixar o Catálogo de Escolas: {ultimo}")


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
    texto = baixar_catalogo()
    por_uf: dict[str, dict] = {}
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
        total += 1
    c.log(f"   {total:,} escolas; sem localização válida: {sem:,}")
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
        "gerado_em": c.agora_iso(), "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)),
        "fonte": "INEP, Catálogo de Escolas (InepData): endereço, telefone e localização informados pelas escolas no Censo Escolar",
        "aviso": "A localização é informada pela própria escola e pode ter erros. Confira o endereço antes de ir.",
    })
    pl = por_uf.get("MT", {})
    if pl:
        amostra = {k: pl[k] for k in ("51025892", "51026309") if k in pl}
        c.log(f"Conferência Pontes e Lacerda: {amostra}")
        c.resumo_github([f"**Localização das escolas:** {total:,} escolas, {total - sem:,} com coordenadas."])


if __name__ == "__main__":
    main()
