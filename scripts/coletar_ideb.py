"""
Educa Já - Ideb e Saeb (INEP, planilhas de divulgação do Ideb).

O Ideb junta duas coisas: a nota da prova do Saeb (português e matemática, aplicada no fim
do ano) e a taxa de aprovação do Censo Escolar. Sai a cada 2 anos (2005, 2007 ... 2025).

Lê as planilhas do INEP (só biblioteca padrão; o .xlsx é baixado para uma pasta temporária):
  - municípios: anos iniciais, anos finais e ensino médio, por rede (Estadual, Municipal, Pública...)
  - escolas: as 3 etapas, por escola (código INEP)
  - estados e Brasil: para comparação
Cada planilha tem uma linha com os códigos das colunas (VL_OBSERVADO_2025 etc.), que usamos
para achar cada valor pelo nome, e não pela posição.

Gera:
  public/data/ideb/<código UF>.json  {"m": {município: {etapa: {rede: série}}}, "e": {escola: {etapa: série}}}
  public/data/ideb/brasil.json      estados e Brasil, por etapa e rede
  public/data/ideb/meta.json
Série = [ideb, meta, nota_mat, nota_port, nota_padronizada, rendimento], cada um uma lista alinhada a "anos".

Uso: python scripts/coletar_ideb.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

BASE = "https://download.inep.gov.br/ideb/resultados/"
SAIDA = c.DADOS_PUBLICOS / "ideb"
ETAPAS = {"ai": "anos_iniciais", "af": "anos_finais", "em": "ensino_medio"}
NOMES_ETAPA = {"ai": "Anos iniciais (1º ao 5º ano)", "af": "Anos finais (6º ao 9º ano)", "em": "Ensino médio"}
ABA_UF = {"ai": "(AI)", "af": "(AF)", "em": "(EM)"}
# o que guardamos de cada ano (prefixo da coluna no INEP)
SERIES = [("ideb", "VL_OBSERVADO_"), ("meta", "VL_PROJECAO_"), ("mat", "VL_NOTA_MATEMATICA_"),
          ("port", "VL_NOTA_PORTUGUES_"), ("n", "VL_NOTA_MEDIA_"), ("p", "VL_INDICADOR_REND_")]
CASAS = {"ideb": 1, "meta": 1, "mat": 1, "port": 1, "n": 2, "p": 3}
UF_POR_NOME = {c.sem_acento(v).lower(): k for k, v in c.NOMES_UF.items()}


def edicao_mais_recente() -> int:
    """O Ideb é de anos ímpares e sai no ano seguinte. Acha a última edição publicada."""
    ano = datetime.now(timezone.utc).year - 1
    ano -= (ano % 2 == 0)
    for a in (ano, ano - 2, ano - 4):
        try:
            c.info(f"{BASE}divulgacao_anos_iniciais_municipios_{a}.zip")
            return a
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("Nenhuma edição do Ideb encontrada no INEP")


def baixar_xlsx(nome_zip: str, pasta: Path) -> Path:
    z = c.ZipRemoto(BASE + nome_zip)
    alvo = z.procurar(".xlsx")
    destino = pasta / Path(alvo).name
    c.log(f"   {nome_zip}: {z.arquivos[alvo]['comp'] / 1e6:.0f} MB")
    with z.abrir(alvo) as f, open(destino, "wb") as out:
        shutil.copyfileobj(f, out, 1 << 20)
    return destino


def linhas_com_codigos(xlsx: Path, aba=0):
    """Gera dicionários {código da coluna: valor} a partir da linha que tem os códigos (VL_...).
    Colunas sem código (rótulos à esquerda nas planilhas de estados) viram '_0', '_1'..."""
    cods = None
    for linha in c.ler_xlsx(xlsx, aba):
        if cods is None:
            if any(str(v).startswith("VL_OBSERVADO_") for v in linha):
                cods = [v.strip() if v.strip() else f"_{i}" for i, v in enumerate(linha)]
            continue
        if any(v.strip() for v in linha):
            yield {k: (linha[i] if i < len(linha) else "") for i, k in enumerate(cods)}


def serie(d: dict, anos: list[int]) -> list:
    out = []
    for nome, pref in SERIES:
        vals = []
        for a in anos:
            v = c.numero(d.get(f"{pref}{a}"))
            vals.append(None if v is None else round(v, CASAS[nome]))
        out.append(vals)
    # corta Nones no fim de séries vazias (economiza espaço)
    return [s if any(x is not None for x in s) else [] for s in out]


def rede_limpa(txt: str) -> str:
    return re.sub(r"\s*\(\d+\)\s*$", "", (txt or "").strip())


def main() -> None:
    ufs = set(c.ufs_escolhidas())
    c.log(f"Educa Já - Ideb e Saeb - UFs: {'todas' if len(ufs) == 27 else ', '.join(sorted(ufs))}")
    ano = edicao_mais_recente()
    anos = list(range(2005, ano + 1, 2))
    c.log(f"   edição mais recente: Ideb {ano} (série {anos[0]}-{anos[-1]})")
    cod_ufs = {c.SIGLAS[u] for u in ufs}
    muns: dict[int, dict] = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    escolas: dict[int, dict] = defaultdict(lambda: defaultdict(dict))
    estados: dict = defaultdict(lambda: defaultdict(dict))
    tmp = Path(tempfile.mkdtemp(prefix="ideb_"))
    try:
        for et, arq in ETAPAS.items():
            x = baixar_xlsx(f"divulgacao_{arq}_municipios_{ano}.zip", tmp)
            n = 0
            for d in linhas_com_codigos(x):
                cod = c.inteiro(d.get("CO_MUNICIPIO"))
                if cod and cod // 100000 in cod_ufs:
                    muns[cod][et][rede_limpa(d.get("REDE"))] = serie(d, anos)
                    n += 1
            c.log(f"      {NOMES_ETAPA[et]}: {n:,} linhas de município x rede")
            x.unlink()

            x = baixar_xlsx(f"divulgacao_{arq}_escolas_{ano}.zip", tmp)
            n = 0
            for d in linhas_com_codigos(x):
                cod = c.inteiro(d.get("ID_ESCOLA"))
                if cod and cod // 1000000 in cod_ufs:
                    escolas[cod][et] = serie(d, anos)
                    n += 1
            c.log(f"      {NOMES_ETAPA[et]}: {n:,} escolas")
            x.unlink()

        # estados (3 abas) e Brasil
        x = baixar_xlsx(f"divulgacao_regioes_ufs_ideb_{ano}.zip", tmp)
        for et, sufixo in ABA_UF.items():
            aba = next(n for n in abas_xlsx(x) if n.endswith(sufixo))
            atual = None
            for d in linhas_com_codigos(x, aba):
                nome = (d.get("_0") or "").strip()
                if nome:
                    atual = UF_POR_NOME.get(c.sem_acento(nome).lower())   # regiões (Norte...) ficam None
                rede = rede_limpa(d.get("_1"))
                if atual and rede:
                    estados[str(c.SIGLAS[atual])][et][rede] = serie(d, anos)
        x.unlink()
        x = baixar_xlsx(f"divulgacao_brasil_ideb_{ano}.zip", tmp)
        abas = abas_xlsx(x)
        for et, sufixo in ABA_UF.items():
            aba = next((n for n in abas if n.endswith(sufixo)), None)
            if aba is None:
                aba = abas[list(ETAPAS).index(et)] if len(abas) >= 3 else abas[0]
            for d in linhas_com_codigos(x, aba):
                rede = rede_limpa(d.get("_1") or d.get("_0"))
                if rede and not rede.lower().startswith(("norte", "nordeste", "sudeste", "sul", "centro")):
                    estados["br"][et].setdefault(rede, serie(d, anos))
        x.unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # grava por estado
    por_uf_m, por_uf_e = defaultdict(dict), defaultdict(dict)
    for cod, d in muns.items():
        por_uf_m[cod // 100000][str(cod)] = {et: dict(r) for et, r in d.items()}
    for cod, d in escolas.items():
        por_uf_e[cod // 1000000][str(cod)] = dict(d)
    gerados = []
    for uf in sorted(cod_ufs):
        if uf not in por_uf_m:
            continue
        tam = c.salvar_json(SAIDA / f"{uf}.json", {"ano": ano, "anos": anos, "m": por_uf_m[uf], "e": por_uf_e.get(uf, {})})
        c.log(f"   {c.SIGLA_DE[uf]}: {len(por_uf_m[uf]):,} municípios, {len(por_uf_e.get(uf, {})):,} escolas ({tam / 1e6:.2f} MB)")
        gerados.append(uf)
    c.salvar_json(SAIDA / "brasil.json", {"ano": ano, "anos": anos, "uf": {k: {e: dict(r) for e, r in v.items()}
                                                                          for k, v in estados.items()}})
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    todas = sorted(set(antigo.get("ufs", [])) | set(gerados)) if antigo.get("ano") == ano else gerados
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ano": ano, "anos": anos, "ufs": todas,
        "fonte": f"INEP, Índice de Desenvolvimento da Educação Básica (Ideb) {ano} e Saeb {ano}",
        "periodo": f"Saeb aplicado no fim de {ano}; aprovação do Censo Escolar {ano}",
        "series": [s for s, _ in SERIES], "etapas": NOMES_ETAPA,
        "aviso_meta": "As metas do Ideb foram definidas até 2021 (1º ciclo). Depois disso não há meta oficial por município.",
    })

    pl = muns.get(5106752, {})
    if pl:
        ai = pl.get("ai", {}).get("Municipal")
        txt = f"anos iniciais, rede municipal: Ideb {ai[0][-2]} → {ai[0][-1]}" if ai and ai[0] else "sem dado"
        c.log(f"Conferência Pontes e Lacerda: {txt}")
        mt = estados.get("51", {}).get("ai", {}).get("Total")
        c.resumo_github([f"**Ideb {ano}:** {len(muns):,} municípios, {len(escolas):,} escolas. Pontes e Lacerda: {txt}. "
                         f"MT anos iniciais (total): {mt[0][-1] if mt and mt[0] else '?'}"])


def abas_xlsx(xlsx: Path) -> list[str]:
    import xml.etree.ElementTree as ET
    import zipfile
    with zipfile.ZipFile(xlsx) as z:
        livro = ET.fromstring(z.read("xl/workbook.xml"))
    return [s.get("name") for s in livro.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet")]


if __name__ == "__main__":
    main()
