"""
Educa Já - Professores e perfil dos alunos (INEP, Indicadores Educacionais).

  - AFD: adequação da formação docente (professor formado na área da matéria que dá), por etapa
  - IRD: regularidade do corpo docente (o professor continua na escola de um ano para o outro), 0 a 5
  - IED: esforço docente (quantos alunos, turnos, escolas e etapas cada professor atende), níveis 1 a 6
  - ICG: complexidade de gestão da escola (tamanho, turnos e etapas), níveis 1 a 6
  - INSE: nível socioeconômico dos alunos (questionário do Saeb), níveis I a VIII

Gera public/data/professores/<código UF>.json, brasil.json e meta.json:
  "m": {município: {rede: {"afd": [[g1..g5] infantil, anos iniciais, anos finais, médio],
                           "ird": [baixa, média-baixa, média-alta, alta] (% das escolas),
                           "ied": [[n1..n6] anos iniciais, anos finais, médio] (% dos professores),
                           "icg": [n1..n6] (% das escolas), "inse": [média, alunos]}}}
  "e": {escola: {"afd": [g1 infantil, AI, AF, médio], "ird": 0-5, "ied": [[n1..n6] AI, AF, médio],
                 "icg": nível, "inse": [média, nível, alunos]}}

Uso: python scripts/coletar_professores.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402
from coletar_fluxo import BASE, UF_POR_NOME, linhas, rede_de, total_local  # noqa: E402

SAIDA = c.DADOS_PUBLICOS / "professores"
INSE_BASE = "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{ano}/nivel_socioeconomico/"
ETAPAS_AFD = ["ED_INF", "FUN_AI", "FUN_AF", "MED"]
ETAPAS_IED = ["FUN_AI", "FUN_AF", "MED"]
REDE_INSE = {"0": "Total", "1": "Federal", "2": "Estadual", "3": "Municipal", "4": "Privada", "5": "Pública"}
ROMANO = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def num(v, casas=1):
    x = c.numero(v)
    return None if x is None else round(x, casas)


def grupo(d: dict, pref: str, n: int) -> list | None:
    v = [num(d.get(f"{pref}_CAT_{i}")) for i in range(1, n + 1)]
    return v if any(x is not None for x in v) else None


def ano_recente() -> int:
    atual = datetime.now(timezone.utc).year
    for a in (atual, atual - 1, atual - 2):
        try:
            c.info(BASE.format(ano=a) + f"AFD_{a}_MUNICIPIOS.zip")
            return a
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("Nenhum arquivo de AFD encontrado no INEP")


def ano_inse() -> int:
    for a in range(datetime.now(timezone.utc).year, 2018, -1):
        try:
            c.info(INSE_BASE.format(ano=a) + f"INSE_{a}_escolas.xlsx")
            return a
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("Nenhum arquivo do INSE encontrado no INEP")


def main() -> None:
    ufs = c.ufs_escolhidas()
    cod_ufs = {c.SIGLAS[u] for u in ufs}
    c.log(f"Educa Já - professores e INSE - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    ano = ano_recente()
    c.log(f"   indicadores de professores: Censo {ano}")
    mun: dict[str, dict] = {}
    esc: dict[str, dict] = {}
    ref: dict[str, dict] = {}
    tmp = Path(tempfile.mkdtemp(prefix="prof_"))
    base = BASE.format(ano=ano)

    def regm(dic, ent, rede):
        return dic.setdefault(ent, {}).setdefault(rede, {})

    def ler_ref_e_mun(sig: str, extrair):
        n = 0
        for d in linhas(base + f"{sig}_{ano}_MUNICIPIOS.zip", tmp):
            cod = c.inteiro(d.get("CO_MUNICIPIO"))
            if not cod or cod // 100000 not in cod_ufs or not total_local(d):
                continue
            rede, v = rede_de(d), extrair(d)
            if rede and v:
                regm(mun, str(cod), rede)[sig.lower()] = v
                n += 1
        c.log(f"      {sig}: {n:,} linhas de município x rede")
        for nome in (f"{sig}_{ano}_BRASIL_REGIOES_UFS.zip", f"{sig}_{ano}_BRASIL_REGIOES_UF.zip"):
            try:
                for d in linhas(base + nome, tmp):
                    nm = c.sem_acento(str(d.get("UNIDGEO", ""))).strip().lower()
                    ent = "br" if nm == "brasil" else (str(c.SIGLAS[UF_POR_NOME[nm]]) if nm in UF_POR_NOME else None)
                    rede, v = rede_de(d), extrair(d)
                    if ent and rede and v and total_local(d):
                        regm(ref, ent, rede)[sig.lower()] = v
                break
            except Exception as e:  # noqa: BLE001
                c.log(f"      {nome}: {str(e)[:60]}")

    def ler_escolas(sig: str, extrair):
        n = 0
        for d in linhas(base + f"{sig}_{ano}_ESCOLAS.zip", tmp):
            cod = c.inteiro(d.get("CO_ENTIDADE"))
            if not cod or cod // 1000000 not in cod_ufs:
                continue
            v = extrair(d)
            if v is not None:
                esc.setdefault(str(cod), {})[sig.lower()] = v
                n += 1
        c.log(f"      {sig}: {n:,} escolas")

    try:
        c.log("   AFD (formação adequada)")
        ler_ref_e_mun("AFD", lambda d: (lambda g: g if any(g) else None)([grupo(d, e, 5) for e in ETAPAS_AFD]))
        ler_escolas("AFD", lambda d: (lambda g: g if any(x is not None for x in g) else None)([num(d.get(f"{e}_CAT_1")) for e in ETAPAS_AFD]))
        c.log("   IRD (regularidade)")
        ler_ref_e_mun("IRD", lambda d: grupo(d, "EDU_BAS", 4))
        ler_escolas("IRD", lambda d: num(d.get("EDU_BAS_CAT_0"), 2))
        c.log("   IED (esforço)")
        ler_ref_e_mun("IED", lambda d: (lambda g: g if any(g) else None)([grupo(d, e, 6) for e in ETAPAS_IED]))
        ler_escolas("IED", lambda d: (lambda g: g if any(g) else None)([grupo(d, e, 6) for e in ETAPAS_IED]))
        c.log("   ICG (complexidade de gestão)")
        ler_ref_e_mun("ICG", lambda d: grupo(d, "EDU_BAS", 6))
        ler_escolas("ICG", lambda d: c.inteiro("".join(ch for ch in str(d.get("COMPLEX", "")) if ch.isdigit())) or None)

        # INSE (planilhas soltas, sem zip; vem do questionário do Saeb, a cada dois anos)
        try:
            ai = ano_inse()
        except Exception as e:  # noqa: BLE001
            ai = None
            c.log(f"   INSE: {e}")
        b = INSE_BASE.format(ano=ai) if ai else None
        combos = set()
        for nome, nivel in (((f"INSE_{ai}_escolas.xlsx", "esc"), (f"INSE_{ai}_municipios.xlsx", "mun"), (f"INSE_{ai}_estados.xlsx", "uf")) if ai else ()):
            arq = tmp / nome
            try:
                with c.abrir(b + nome, timeout=300) as r, open(arq, "wb") as f:
                    shutil.copyfileobj(r, f, 1 << 20)
            except Exception as e:  # noqa: BLE001
                c.log(f"      {nome}: {str(e)[:80]}")
                continue
            cab = None
            n = 0
            for lin in c.ler_xlsx(arq, 0):
                if cab is None:
                    cab = [str(x).strip() for x in lin]
                    continue
                d = dict(zip(cab, lin))
                media, qtd = num(d.get("MEDIA_INSE"), 2), c.inteiro(d.get("QTD_ALUNOS_INSE"))
                if media is None:
                    continue
                if nivel == "esc":
                    cod = c.inteiro(d.get("ID_ESCOLA"))
                    if cod and cod // 1000000 in cod_ufs:
                        cl = str(d.get("INSE_CLASSIFICACAO", "")).replace("Nível", "").strip()
                        esc.setdefault(str(cod), {})["inse"] = [media, ROMANO.get(cl), qtd]
                        n += 1
                    continue
                rede, loc = str(d.get("TP_TIPO_REDE", "")).strip(), str(d.get("TP_LOCALIZACAO", "")).strip()
                cap = str(d.get("TP_CAPITAL", "")).strip()
                if nivel == "mun":
                    cod = c.inteiro(d.get("CO_MUNICIPIO"))
                    if not cod or cod // 100000 not in cod_ufs:
                        continue
                    if cod == 5106752:
                        combos.add((rede, loc, cap, media, qtd))
                    if loc != "0" or rede not in REDE_INSE:
                        continue
                    regm(mun, str(cod), REDE_INSE[rede])["inse"] = [media, qtd]
                else:
                    cod = c.inteiro(d.get("CO_UF"))
                    if not cod or loc != "0" or cap not in ("0", "") or rede not in REDE_INSE:
                        continue
                    regm(ref, str(cod), REDE_INSE[rede])["inse"] = [media, qtd]
                n += 1
            arq.unlink(missing_ok=True)
            c.log(f"      {nome}: {n:,} linhas")
        if combos:
            c.log(f"      Pontes e Lacerda (rede, localização, capital, média, alunos): {sorted(combos)}")
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
    antigo = c.ler_json(SAIDA / "brasil.json", {}) or {}
    if len(cod_ufs) < 27:      # coleta parcial: mantém as referências dos outros estados
        ref = {**antigo.get("uf", {}), **ref}
    c.salvar_json(SAIDA / "brasil.json", {"uf": ref})
    meta_ant = c.ler_json(SAIDA / "meta.json", {}) or {}
    mesmos = meta_ant.get("ano") == ano
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ano": ano, "ano_inse": ai or meta_ant.get("ano_inse"),
        "ufs": sorted(set(meta_ant.get("ufs", [])) | set(gerados)) if mesmos else gerados,
        "fonte": f"INEP, Indicadores Educacionais do Censo Escolar {ano} (formação, regularidade e esforço dos professores, "
                 f"complexidade de gestão) e Indicador de Nível Socioeconômico (Inse) do Saeb {ai}",
        "aviso": f"Professores: situação na data do Censo Escolar {ano}." + (
            f" Nível socioeconômico: alunos que responderam ao questionário do Saeb {ai}; o Inse é calculado a cada "
            f"Saeb e o de {ai + 2} ainda não saiu." if ai else ""),
    })
    pl = mun.get("5106752", {})
    if pl:
        t = pl.get("Total", {})
        txt = (f"formação adequada (anos iniciais) {((t.get('afd') or [[None]] * 4)[1] or [None])[0]}%; "
               f"Inse rede municipal {(pl.get('Municipal', {}).get('inse') or [None])[0]}")
        c.log(f"Conferência Pontes e Lacerda: {txt}; escola 51026244: {esc.get('51026244')}")
        c.resumo_github([f"**Professores e Inse:** {len(gerados)} UFs. Pontes e Lacerda: {txt}"])


if __name__ == "__main__":
    main()
