"""
Educa Já - Fluxo escolar (INEP, Indicadores Educacionais).

  - Taxas de rendimento: aprovação, reprovação e abandono (ano letivo; sai em meados do ano seguinte)
  - Distorção idade-série: alunos com 2 anos ou mais de atraso para a série (Censo Escolar)
  - Alunos por turma (ATU) e horas-aula diárias (HAD) (Censo Escolar)

Planilhas .xlsx dentro de .zip no INEP. Cada uma tem uma linha com os códigos das colunas
(1_CAT_FUN_AI, FUN_AI_CAT_0...), usada para achar cada valor pelo nome.
Só a linha "Total" de localização é usada (urbana + rural).

Gera public/data/fluxo/<código UF>.json, brasil.json e meta.json:
  "m": {município: {rede: {"r": [ano anterior, ano atual], "t": [...], "a": [...], "h": [...]}}}
  "e": {escola: {"r": [...], "ra": [...], "t": [...], "a": [...]}}
  r = [aprovação AI, AF, médio, reprovação AI, AF, médio, abandono AI, AF, médio]
  t = distorção [AI, AF, médio]; a = alunos por turma e h = horas-aula [ed. infantil, AI, AF, médio]

Uso: python scripts/coletar_fluxo.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

BASE = "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{ano}/"
SAIDA = c.DADOS_PUBLICOS / "fluxo"
ARQ = {
    "rend": {"mun": "tx_rend_municipios_{ano}.zip", "esc": "tx_rend_escolas_{ano}.zip", "uf": "tx_rend_brasil_regioes_ufs_{ano}.zip"},
    "tdi": {"mun": "TDI_{ano}_MUNICIPIOS.zip", "esc": "TDI_{ano}_ESCOLAS.zip", "uf": "TDI_{ano}_BRASIL_REGIOES_UFS.zip"},
    "atu": {"mun": "ATU_{ano}_MUNICIPIOS.zip", "esc": "ATU_{ano}_ESCOLAS.zip", "uf": "ATU_{ano}_BRASIL_REGIOES_UFS.zip"},
    "had": {"mun": "HAD_{ano}_MUNICIPIOS.zip", "uf": "HAD_{ano}_BRASIL_REGIOES_UFS.zip"},
}
COLS = {
    "rend": [f"{t}_CAT_{e}" for t in (1, 2, 3) for e in ("FUN_AI", "FUN_AF", "MED")],
    "tdi": ["FUN_AI_CAT_0", "FUN_AF_CAT_0", "MED_CAT_0"],
    "atu": ["ED_INF_CAT_0", "FUN_AI_CAT_0", "FUN_AF_CAT_0", "MED_CAT_0"],
    "had": ["ED_INF_CAT_0", "FUN_AI_CAT_0", "FUN_AF_CAT_0", "MED_CAT_0"],
}
REDES = {"total": "Total", "publica": "Pública", "municipal": "Municipal", "estadual": "Estadual", "federal": "Federal",
         "privada": "Privada", "particular": "Privada"}
UF_POR_NOME = {c.sem_acento(v).lower(): k for k, v in c.NOMES_UF.items()}


def ano_recente(tipo: str) -> int:
    atual = datetime.now(timezone.utc).year
    for a in (atual, atual - 1, atual - 2):
        try:
            c.info(BASE.format(ano=a) + ARQ[tipo]["mun"].format(ano=a))
            return a
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(f"Nenhum arquivo de {tipo} encontrado no INEP")


def linhas(url: str, pasta: Path):
    """Dicionários {código da coluna: valor} a partir da linha de códigos (NU_ANO_CENSO...)."""
    z = c.ZipRemoto(url)
    alvo = z.procurar(".xlsx")
    destino = pasta / Path(alvo).name
    with z.abrir(alvo) as f, open(destino, "wb") as out:
        shutil.copyfileobj(f, out, 1 << 20)
    cods = None
    try:
        for lin in c.ler_xlsx(destino, 0):
            if cods is None:
                if any(str(v).strip() == "NU_ANO_CENSO" for v in lin):
                    cods = [str(v).strip() for v in lin]
                    c.log(f"      colunas: {', '.join(x for x in cods[:12] if x)}...")
                continue
            if any(str(v).strip() for v in lin):
                yield {k: (lin[i] if i < len(lin) else "") for i, k in enumerate(cods) if k}
    finally:
        destino.unlink(missing_ok=True)
    if cods is None:
        raise RuntimeError(f"Linha de códigos não encontrada em {url}")


def valores(d: dict, cols: list[str]) -> list | None:
    out = []
    for k in cols:
        v = c.numero(d.get(k))
        out.append(None if v is None else round(v, 1))
    return out if any(v is not None for v in out) else None


def rede_de(d: dict) -> str | None:
    return REDES.get(c.sem_acento(str(d.get("NO_DEPENDENCIA", ""))).strip().lower())


def total_local(d: dict) -> bool:
    return c.sem_acento(str(d.get("NO_CATEGORIA", "Total"))).strip().lower() == "total"


def main() -> None:
    ufs = c.ufs_escolhidas()
    cod_ufs = {c.SIGLAS[u] for u in ufs}
    c.log(f"Educa Já - fluxo escolar - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    anos = {t: ano_recente(t) for t in ARQ}
    c.log(f"   edições: rendimento {anos['rend']}, distorção {anos['tdi']}, alunos por turma {anos['atu']}, horas-aula {anos['had']}")
    mun: dict[str, dict] = {}
    esc: dict[str, dict] = {}
    ref: dict[str, dict] = {}       # UF e Brasil
    tmp = Path(tempfile.mkdtemp(prefix="fluxo_"))
    try:
        for tipo, arqs in ARQ.items():
            lista_anos = [anos[tipo] - 1, anos[tipo]] if tipo == "rend" else [anos[tipo]]
            for k, ano in enumerate(lista_anos):
                base = BASE.format(ano=ano)
                chave = "r" if tipo == "rend" else {"tdi": "t", "atu": "a", "had": "h"}[tipo]
                pos = k if tipo == "rend" else None

                def guardar(dic, ent, rede, v):
                    reg = dic.setdefault(ent, {}).setdefault(rede, {})
                    if pos is None:
                        reg[chave] = v
                    else:
                        reg.setdefault(chave, [None, None])[pos] = v

                # municípios
                c.log(f"   {tipo} {ano}: municípios")
                n = 0
                for d in linhas(base + arqs["mun"].format(ano=ano), tmp):
                    cod = c.inteiro(d.get("CO_MUNICIPIO"))
                    if not cod or cod // 100000 not in cod_ufs or not total_local(d):
                        continue
                    rede, v = rede_de(d), valores(d, COLS[tipo])
                    if rede and v:
                        guardar(mun, str(cod), rede, v)
                        n += 1
                c.log(f"      {n:,} linhas de município x rede")
                # estados e Brasil
                for d in linhas(base + arqs["uf"].format(ano=ano), tmp):
                    nome = c.sem_acento(str(d.get("UNIDGEO", ""))).strip().lower()
                    ent = "br" if nome == "brasil" else (str(c.SIGLAS[UF_POR_NOME[nome]]) if nome in UF_POR_NOME else None)
                    rede, v = rede_de(d), valores(d, COLS[tipo])
                    if ent and rede and v and total_local(d):
                        guardar(ref, ent, rede, v)
                # escolas (só o ano mais recente de cada tipo, mais o ano anterior do rendimento)
                if "esc" in arqs:
                    c.log(f"   {tipo} {ano}: escolas")
                    n = 0
                    for d in linhas(base + arqs["esc"].format(ano=ano), tmp):
                        cod = c.inteiro(d.get("CO_ENTIDADE"))
                        if not cod or cod // 1000000 not in cod_ufs:
                            continue
                        v = valores(d, COLS[tipo])
                        if v:
                            e = esc.setdefault(str(cod), {})
                            if tipo == "rend":
                                e["r" if k == 1 else "ra"] = v
                            else:
                                e[chave] = v
                            n += 1
                    c.log(f"      {n:,} escolas")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    gerados = []
    for cod_uf in sorted(cod_ufs):
        pref = str(cod_uf)
        m = {k: v for k, v in mun.items() if k.startswith(pref)}
        if not m:
            continue
        e = {k: v for k, v in esc.items() if k.startswith(pref)}
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"m": m, "e": e})
        c.log(f"   {c.SIGLA_DE[cod_uf]}: {len(m):,} municípios, {len(e):,} escolas ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)
    c.salvar_json(SAIDA / "brasil.json", {"uf": ref})
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    mesmos = antigo.get("anos") == anos
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "anos": anos, "anos_rend": [anos["rend"] - 1, anos["rend"]],
        "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)) if mesmos else gerados,
        "fonte": "INEP, Indicadores Educacionais (taxas de rendimento, distorção idade-série, alunos por turma e horas-aula)",
        "aviso": "As taxas de rendimento são do ano letivo indicado e saem em meados do ano seguinte, quando as escolas "
                 "informam a situação final de cada aluno. Os outros indicadores são da data do Censo Escolar.",
    })
    pl = mun.get("5106752", {}).get("Municipal")
    if pl:
        r = (pl.get("r") or [None, None])[1]
        txt = (f"rede municipal, anos iniciais {anos['rend']}: aprovação {r[0]}%, reprovação {r[3]}%, abandono {r[6]}%; "
               f"distorção {pl.get('t', [None])[0]}%") if r else "sem rendimento"
        c.log(f"Conferência Pontes e Lacerda: {txt}")
        c.resumo_github([f"**Fluxo escolar:** {len(gerados)} UFs. Pontes e Lacerda: {txt}"])


if __name__ == "__main__":
    main()
