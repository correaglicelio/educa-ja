"""
Educa Já - Transporte escolar (FNDE - Plataforma Antonieta de Barros).

  - produto 55: estudantes contemplados pelo PNATE (alunos da zona rural transportados), por entidade
  - produto 56: repasses do PNATE: valor por aluno, previsto e a pagar por etapa, delegação da rede estadual
  - produtos 41 e 42: pagamentos do Caminho da Escola (ônibus, lanchas, bicicletas), até 2024 e atual

Os repasses mês a mês vêm do Portal da Transparência (coletar_transferencias.py) e os alunos que usam
transporte escolar em cada escola vêm do Censo Escolar (coletar_escolas.py).

Gera public/data/transporte/<código UF>.json e meta.json:
  "m": {ibge: {"alunos": n, "pc": valor por aluno, "deleg": 0|1, "prev": [infantil, fundamental, médio],
               "pagar": [infantil, fundamental, médio], "cde": {ano: valor pago}}}
  "estado": {mesmo formato, secretaria estadual}

Uso: python scripts/coletar_transporte.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import gzip
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

API = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products/{id}/"
SAIDA = c.DADOS_PUBLICOS / "transporte"


def ler(produto: int):
    with c.abrir(API.format(id=produto) + "artifact", timeout=300) as resp:
        texto = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8", errors="replace")
        cab = None
        for linha in texto:
            col = linha.rstrip("\n").rstrip("\r").split(";")
            if cab is None:
                cab = [x.strip().lower() for x in col]
                continue
            if len(col) >= len(cab):
                yield dict(zip(cab, (x.strip() for x in col)))


def atualizado(produto: int) -> str | None:
    try:
        return (c.get_json(API.format(id=produto) + "artifact-metadata") or {}).get("lastUpdated")
    except Exception:  # noqa: BLE001
        return None


def dig(x: str) -> str:
    return "".join(ch for ch in (x or "") if ch.isdigit())


def eh_estado(entidade: str) -> bool:
    e = c.sem_acento(entidade).upper()
    return "PREF" not in e and ("SEC" in e or "ESTADO" in e or "GOVERNO" in e)


def main() -> None:
    ufs = c.ufs_escolhidas()
    siglas = set(ufs)
    c.log(f"Educa Já - transporte escolar - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    casa = c.CasadorMunicipios()
    m: dict[str, dict] = {}
    est: dict[str, dict] = {}
    por_cnpj: dict[str, dict] = {}

    def alvo(uf: str, entidade: str, cod) -> dict | None:
        if eh_estado(entidade):
            return est.setdefault(str(c.SIGLAS[uf]), {})
        return m.setdefault(str(cod), {}) if cod else None

    # 1) repasses do PNATE (tem o código IBGE e o CNPJ)
    data_arq = None
    for d in ler(56):
        uf = d.get("sigla_uf", "")
        if uf not in siglas:
            continue
        cod = c.inteiro(d.get("cod_ibge")) or casa.codigo(d.get("nome_municipio", ""), uf)
        r = alvo(uf, d.get("entidade_executora", ""), cod)
        if r is None:
            continue
        r["pc"] = round(c.numero(d.get("valor_per_capita")) or 0.0, 2)
        r["deleg"] = 1 if c.sem_acento(d.get("aut_repasse_delegacao_rede", "")).lower().startswith("s") else 0
        r["prev"] = [round(c.numero(d.get(f"prev_{k}")) or 0.0, 2) for k in ("ed_infantil", "ens_fundamental", "ens_medio")]
        r["pagar"] = [round(c.numero(d.get(f"vl_pagar_{k}")) or 0.0, 2) for k in ("ed_infantil", "ens_fundamental", "ens_medio")]
        por_cnpj[dig(d.get("cnpj"))] = r
        data_arq = max(data_arq or "", (d.get("data_arquivo") or "")[:10])
    c.log(f"   repasses PNATE: {len(m):,} municípios (arquivo de {data_arq})")

    # 2) estudantes contemplados
    n = 0
    for d in ler(55):
        uf = d.get("sigla_uf", "")
        if uf not in siglas:
            continue
        r = por_cnpj.get(dig(d.get("cnpj"))) or alvo(uf, d.get("entidade_executora", ""), casa.codigo(d.get("nome_municipio", ""), uf))
        if r is None:
            continue
        r["alunos"] = (r.get("alunos") or 0) + (c.inteiro(d.get("alunos_atendidos")) or 0)
        n += 1
    c.log(f"   estudantes contemplados: {n:,} entidades")

    # 3) Caminho da Escola (pagamentos), ligado pelo CNPJ da prefeitura ou do estado
    n = 0
    for prod in (41, 42):
        try:
            for d in ler(prod):
                if d.get("uf", "") not in siglas:
                    continue
                r = por_cnpj.get(dig(d.get("nu_cgc_favorecida")))
                if r is None:
                    continue
                ano = str(c.inteiro(d.get("an_exercicio")) or "")
                cde = r.setdefault("cde", {})
                cde[ano] = round(cde.get(ano, 0) + (c.numero(d.get("vl_pago")) or 0.0), 2)
                n += 1
        except Exception as e:  # noqa: BLE001
            c.log(f"   Caminho da Escola (produto {prod}): falhou ({e})")
    c.log(f"   pagamentos do Caminho da Escola ligados: {n:,}")

    gerados = []
    for uf in ufs:
        cod_uf = c.SIGLAS[uf]
        mm = {k: v for k, v in m.items() if k.startswith(str(cod_uf))}
        if not mm:
            continue
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"m": mm, "estado": est.get(str(cod_uf), {})})
        c.log(f"   {uf}: {len(mm):,} municípios ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)), "data_arquivo": data_arq,
        "atualizado": {"alunos": atualizado(55), "repasses": atualizado(56), "caminho": atualizado(42)},
        "fonte": "FNDE, Programa Nacional de Apoio ao Transporte do Escolar (PNATE) e Caminho da Escola "
                 "(Plataforma Antonieta de Barros)",
        "aviso": "O PNATE ajuda a pagar o transporte de alunos da zona rural; o resto do custo é da prefeitura e do estado.",
    })
    pl = m.get("5106752")
    if pl:
        c.log(f"Conferência Pontes e Lacerda: {pl}")
        c.resumo_github([f"**Transporte escolar:** {len(gerados)} UFs. Pontes e Lacerda: {pl.get('alunos')} alunos, "
                         f"R$ {pl.get('pc')} por aluno"])


if __name__ == "__main__":
    main()
