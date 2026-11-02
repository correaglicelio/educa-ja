"""
Educa Já - tabela de municípios (código IBGE, código SIOPE, nome, UF).

Fonte principal: Censo Escolar (INEP), tabela de escolas. Todo município do Brasil tem
escola, então a lista sai completa (5.570). Lemos só a tabela de escolas, direto no zip
do servidor (HTTP Range), sem baixar os 537 MB do arquivo.

Plano B: se o INEP não responder (ex.: rodando fora do Brasil), usa a API do SIOPE (FNDE),
que traz o código de 6 dígitos; o 7º dígito é calculado.

Gera public/data/municipios.json:
  {"gerado_em", "fonte", "ufs": {"51": ["MT", "Mato Grosso"], ...},
   "m": [[ibge7, "Nome", "UF"], ...]}       (código SIOPE = ibge7 // 10)

Uso: python scripts/coletar_municipios.py   (sempre o Brasil inteiro: a lista é pequena)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

CENSO_URLS = [
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip",
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025.zip",
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2024.zip",
]
SIOPE = ("https://www.fnde.gov.br/olinda-ide/servico/DADOS_ABERTOS_SIOPE/versao/v1/odata/"
         "Indicadores_Siope(Ano_Consulta=@Ano_Consulta,Num_Peri=@Num_Peri,Sig_UF=@Sig_UF)"
         "?@Ano_Consulta={ano}&@Num_Peri=6&@Sig_UF='{uf}'&$format=json&$select=COD_MUNI,NOM_MUNI&$top=100000")
SAIDA = c.DADOS_PUBLICOS / "municipios.json"


def pelo_censo() -> tuple[dict, str]:
    ultimo = None
    for url in CENSO_URLS:
        try:
            c.log(f"   abrindo {url.rsplit('/', 1)[-1]} ...")
            z = c.ZipRemoto(url)
            try:
                nome = z.procurar("tabela_escola", ".csv")        # 2025 em diante: tabelas separadas
            except KeyError:
                nome = z.procurar("microdados_ed_basica", ".csv")  # até 2024: um arquivo só
            tam = z.arquivos[nome]["comp"]
            c.log(f"   lendo {nome.rsplit('/', 1)[-1]} ({tam / 1e6:.0f} MB, em fluxo)")
            muns: dict[int, tuple[str, str]] = {}
            with z.abrir(nome) as f:
                for i, linha in enumerate(c.linhas_csv(f), 1):
                    cod = linha.get("CO_MUNICIPIO")
                    if cod and cod.isdigit() and int(cod) not in muns:
                        muns[int(cod)] = (linha["NO_MUNICIPIO"].strip(), linha["SG_UF"].strip())
                    if i % 50000 == 0:
                        c.log(f"   {i:,} escolas lidas, {len(muns):,} municípios")
            ano = re.search(r"(20\d\d)", url.rsplit("/", 1)[-1]).group(1)
            return muns, f"INEP, Censo Escolar {ano}"
        except Exception as ex:  # noqa: BLE001
            ultimo = ex
            c.log(f"   não deu: {ex}")
    raise RuntimeError(f"Censo indisponível: {ultimo}")


def pelo_siope() -> tuple[dict, str]:
    muns: dict[int, tuple[str, str]] = {}
    ano_usado = None
    for uf in c.SIGLAS:
        if uf == "DF":
            muns[5300108] = ("Brasília", "DF")
            continue
        for ano in (2025, 2024):
            dados = c.get_json(SIOPE.format(ano=ano, uf=uf)).get("value", [])
            if dados:
                ano_usado = ano_usado or ano
                for d in dados:
                    if str(d.get("COD_MUNI", "")).isdigit():
                        muns.setdefault(c.codigo_ibge(d["COD_MUNI"]), (d["NOM_MUNI"].strip().title(), uf))
                break
        c.log(f"   {uf}: {sum(1 for v in muns.values() if v[1] == uf)} municípios")
    return muns, f"FNDE, SIOPE {ano_usado} (municípios que enviaram dados)"


def main() -> None:
    c.log("Educa Já - tabela de municípios")
    try:
        muns, fonte = pelo_censo()
    except RuntimeError as ex:
        c.log(f"   {ex}\n   usando o plano B (SIOPE)...")
        muns, fonte = pelo_siope()
    if len(muns) < 5000:
        raise SystemExit(f"Só {len(muns)} municípios encontrados; algo deu errado. Nada foi gravado.")
    lista = sorted(([k, n, u] for k, (n, u) in muns.items()), key=lambda x: (x[2], c.sem_acento(x[1])))
    ufs = {str(c.SIGLAS[u]): [u, c.NOMES_UF[u]] for u in sorted({x[2] for x in lista}, key=c.SIGLAS.get)}
    tam = c.salvar_json(SAIDA, {"gerado_em": c.agora_iso(), "fonte": fonte, "ufs": ufs, "m": lista})
    pl = next((x for x in lista if x[0] == 5106752), None)
    c.log(f"Pronto: {len(lista):,} municípios em {len(ufs)} UFs ({tam / 1024:.0f} KB) -> {SAIDA}")
    c.log(f"Conferência: Pontes e Lacerda = {pl}")
    c.resumo_github([f"**Municípios:** {len(lista):,} ({fonte}); Pontes e Lacerda: `{pl}`"])


if __name__ == "__main__":
    main()
