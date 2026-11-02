"""
Educa Já - testa se cada fonte de dados está respondendo (sem baixar os arquivos grandes).

Para cada fonte: está no ar? qual o tamanho? quando foi atualizada? aceita leitura por
partes (HTTP Range, necessária para ler só um pedaço dos zips do INEP)?
Rodar no PC e no GitHub mostra se os sites respondem de fora do Brasil.

Gera public/data/status_fontes.json (o site mostra essa tabela) e escreve o resumo
no GitHub Actions. Uso: python scripts/testar_fontes.py
"""
from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

INEP = "https://download.inep.gov.br"
ANTONIETA = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products"
SIOPE = ("https://www.fnde.gov.br/olinda-ide/servico/DADOS_ABERTOS_SIOPE/versao/v1/odata/"
         "Indicadores_Siope(Ano_Consulta=@Ano_Consulta,Num_Peri=@Num_Peri,Sig_UF=@Sig_UF)"
         "?@Ano_Consulta=2025&@Num_Peri=6&@Sig_UF='MT'&$format=json&$top=5")

FONTES = [
    # (id, nome, tipo, url)
    ("censo", "Censo Escolar 2025 (INEP)", "zip", f"{INEP}/dados_abertos/microdados_censo_escolar_2025_.zip"),
    ("ideb", "Ideb 2025 por município (INEP)", "zip", f"{INEP}/ideb/resultados/divulgacao_anos_iniciais_municipios_2025.zip"),
    ("rendimento", "Taxas de rendimento 2025 (INEP)", "zip",
     f"{INEP}/informacoes_estatisticas/indicadores_educacionais/2025/tx_rend_municipios_2025.zip"),
    ("tdi", "Distorção idade-série 2025 (INEP)", "zip",
     f"{INEP}/informacoes_estatisticas/indicadores_educacionais/2025/TDI_2025_MUNICIPIOS.zip"),
    ("enem", "ENEM 2025 microdados (INEP)", "zip", f"{INEP}/microdados/microdados_enem_2025.zip"),
    ("siope", "SIOPE, API (FNDE)", "json", SIOPE),
    ("pnae", "PNAE repasses (FNDE)", "antonieta", f"{ANTONIETA}/82"),
    ("pdde", "PDDE execução (FNDE)", "antonieta", f"{ANTONIETA}/66"),
    ("pnate", "PNATE repasses (FNDE)", "antonieta", f"{ANTONIETA}/56"),
    ("cae", "Conselho de Alimentação Escolar (FNDE)", "antonieta", f"{ANTONIETA}/30"),
    ("fundeb", "Matrículas do FUNDEB (FNDE)", "antonieta", f"{ANTONIETA}/36"),
    ("catalogo", "Catálogo de Escolas (INEP)", "pagina",
     "https://anonymousdata.inep.gov.br/analytics/saw.dll?Portal"),
]


def testar(tipo: str, url: str) -> dict:
    t0 = time.time()
    r: dict = {}
    if tipo == "zip":
        i = c.info(url)
        r.update(bytes=i["bytes"], atualizado=i["modificado"])
        with c.abrir(url, 0, 3, tentativas=2, timeout=40) as resp:   # pede 4 bytes: confere o Range
            r["range"] = resp.read(4) == b"PK\x03\x04"
    elif tipo == "json":
        d = c.get_json(url, tentativas=2, timeout=60)
        r["linhas"] = len(d.get("value", []))
    elif tipo == "antonieta":
        m = c.get_json(url + "/artifact-metadata", tentativas=2, timeout=40)
        r.update(bytes=m.get("size"), atualizado=m.get("lastUpdated"), arquivo=m.get("name"))
    else:
        with c.abrir(url, tentativas=2, timeout=40) as resp:
            r["http"] = resp.status
    r["segundos"] = round(time.time() - t0, 1)
    return r


def main() -> None:
    onde = "GitHub (fora do Brasil)" if os.environ.get("GITHUB_ACTIONS") else f"PC ({platform.node() or 'local'})"
    c.log(f"Educa Já - teste das fontes de dados, rodando em: {onde}\n")
    resultado = []
    for fid, nome, tipo, url in FONTES:
        try:
            r = testar(tipo, url)
            r["ok"] = True if tipo != "zip" else bool(r.get("range"))
            if tipo == "zip" and not r.get("range"):
                r["erro"] = "não aceita leitura por partes"
        except Exception as ex:  # noqa: BLE001
            r = {"ok": False, "erro": f"{type(ex).__name__}: {ex}"[:200]}
        r.update(id=fid, nome=nome, url=url)
        resultado.append(r)
        mb = f"{r['bytes'] / 1e6:,.1f} MB" if r.get("bytes") else ""
        c.log(f"  {'OK   ' if r['ok'] else 'FALHA'} {nome:<42} {mb:>12}  {r.get('atualizado') or r.get('erro', '')}")

    anterior = c.ler_json(c.DADOS_PUBLICOS / "status_fontes.json", {}) or {}
    rodadas = {k: v for k, v in (anterior.get("rodadas") or {}).items()}
    rodadas["github" if os.environ.get("GITHUB_ACTIONS") else "pc"] = {
        "quando": c.agora_iso(), "onde": onde, "fontes": resultado}
    c.salvar_json(c.DADOS_PUBLICOS / "status_fontes.json", {"gerado_em": c.agora_iso(), "rodadas": rodadas})

    ok = sum(r["ok"] for r in resultado)
    c.log(f"\n{ok} de {len(resultado)} fontes responderam.")
    linhas = [f"### Fontes de dados ({onde}): {ok} de {len(resultado)} responderam", "",
              "| Fonte | Resultado | Tamanho | Atualizado / erro |", "|---|---|---|---|"]
    for r in resultado:
        mb = f"{r['bytes'] / 1e6:,.1f} MB" if r.get("bytes") else ""
        linhas.append(f"| {r['nome']} | {'✅' if r['ok'] else '❌'} | {mb} | {r.get('atualizado') or r.get('erro', '')} |")
    c.resumo_github(linhas)


if __name__ == "__main__":
    main()
