"""
Educa Já - Merenda escolar (PNAE, FNDE - Plataforma Antonieta de Barros).

  - produto 82: repasses do PNAE por ano, com alunos e escolas atendidas (2009 até o ano atual)
  - produto 30: Conselho de Alimentação Escolar (CAE): situação e datas do mandato e composição
  - produto 29: nutricionistas vinculados ao programa

Dados pessoais (nomes, e-mails, telefones, CRN) NÃO são publicados: só situação, datas e contagens.

Gera public/data/merenda/<código UF>.json e meta.json:
  "m": {ibge: {"r": {ano: [alunos, escolas, valor]},           # prefeitura
               "cae": {"sit", "ini", "fim", "tit": n, "sup": n, "cat": {categoria: titulares}},
               "nut": {"ativos": n, "rt": 0|1, "horas": n}}}
  "estado": {"r": {...}, "nut": {...}}                           # secretaria estadual

Uso: python scripts/coletar_merenda.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import gzip
import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

API = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products/{id}/"
SAIDA = c.DADOS_PUBLICOS / "merenda"
HOJE = date.today().isoformat()


def ler(produto: int):
    """Linhas (dicionários) do arquivo .txt.gz de um produto da Plataforma Antonieta."""
    with c.abrir(API.format(id=produto) + "artifact", timeout=180) as resp:
        texto = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8", errors="replace")
        cab = None
        for linha in texto:
            col = linha.rstrip("\n").rstrip("\r").split(";")
            if cab is None:
                cab = [x.strip() for x in col]
                continue
            if len(col) >= len(cab):
                yield dict(zip(cab, (x.strip() for x in col)))


def atualizado(produto: int) -> str | None:
    try:
        return (c.get_json(API.format(id=produto) + "artifact-metadata") or {}).get("lastUpdated")
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ufs = c.ufs_escolhidas()
    siglas = set(ufs)
    c.log(f"Educa Já - merenda (PNAE) - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    casa = c.CasadorMunicipios()
    m: dict[str, dict] = {}
    est: dict[str, dict] = {}

    # 1) repasses
    n = 0
    for d in ler(82):
        uf = d.get("UF", "")
        if uf not in siglas:
            continue
        ano = c.inteiro(d.get("Ano_Exercicio"))
        ent = c.sem_acento(d.get("Entidade_Responsavel", "")).upper()
        vals = [c.inteiro(d.get("Quantidade_Alunos")) or 0, c.inteiro(d.get("Quantidade_Escolas")) or 0,
                c.numero(d.get("Valor_Repasse")) or 0.0]
        if "PREF" in ent or "MUNIC" in ent:
            cod = casa.codigo(d.get("Municipio", ""), uf)
            if not cod:
                continue
            alvo = m.setdefault(str(cod), {}).setdefault("r", {})
        else:   # secretaria estadual de educação (e outras entidades estaduais)
            alvo = est.setdefault(str(c.SIGLAS[uf]), {}).setdefault("r", {})
        a = alvo.setdefault(str(ano), [0, 0, 0.0])
        for i in range(3):
            a[i] += vals[i]
        n += 1
    c.log(f"   repasses: {n:,} linhas")

    # 2) Conselho de Alimentação Escolar: fica o mandato que termina por último em cada município
    caes: dict[str, dict] = {}
    for d in ler(30):
        uf = d.get("UF", "")
        if uf not in siglas:
            continue
        cod = casa.codigo(d.get("NO_MUNICIPIO", ""), uf)
        if not cod:
            continue
        fim = (d.get("DT_TERMINO_MANDATO") or "")[:10]
        ini = (d.get("DT_INICIO_MANDATO") or "")[:10]
        atual = caes.get(str(cod))
        if atual is None or fim > atual["fim"]:
            atual = caes[str(cod)] = {"sit": d.get("DS_SITUACAO_MANDATO", "").strip().upper(), "ini": ini, "fim": fim,
                                      "tit": 0, "sup": 0, "cat": {}}
        elif fim < atual["fim"]:
            continue
        if c.sem_acento(d.get("TP_MEMBRO", "")).lower().startswith("titular"):
            atual["tit"] += 1
            cat = d.get("DS_CATEGORIA_MEMBRO_CONSELHO", "").strip().capitalize() or "Outros"
            atual["cat"][cat] = atual["cat"].get(cat, 0) + 1
        else:
            atual["sup"] += 1
    for cod, cae in caes.items():
        # a situação no arquivo pode estar desatualizada: se o mandato já terminou, é vencido
        if cae["fim"] and cae["fim"] < HOJE:
            cae["sit"] = "VENCIDO"
        m.setdefault(cod, {})["cae"] = cae
    c.log(f"   conselhos: {len(caes):,} municípios")

    # 3) nutricionistas com vínculo ativo
    n = 0
    for d in ler(29):
        uf = d.get("SG_UF", "")
        if uf not in siglas:
            continue
        fim = (d.get("DT_VINCULO_FIM") or "")[:10]
        if fim and fim < HOJE:
            continue
        esfera = c.sem_acento(d.get("NO_ESFERA_ADM", "")).upper()
        if "MUNICIPAL" in esfera:
            cod = c.inteiro(d.get("CO_MUNICIPIO_IBGE"))
            if not cod:
                continue
            alvo = m.setdefault(str(cod), {}).setdefault("nut", {"ativos": 0, "rt": 0, "horas": 0})
        else:
            alvo = est.setdefault(str(c.SIGLAS[uf]), {}).setdefault("nut", {"ativos": 0, "rt": 0, "horas": 0})
        alvo["ativos"] += 1
        alvo["horas"] += c.inteiro(d.get("NU_CARGA_HORARIA_SEMANAL")) or 0
        if "RESPONSAVEL" in c.sem_acento(d.get("DS_FUNCAO_NUTRICIONISTA", "")).upper():
            alvo["rt"] = 1
        n += 1
    c.log(f"   nutricionistas ativos: {n:,}")
    if casa.faltando:
        c.log(f"   {len(casa.faltando)} nomes de município sem correspondência: {sorted(casa.faltando)[:30]}")

    for reg in list(m.values()) + list(est.values()):
        for a in reg.get("r", {}).values():
            a[2] = round(a[2], 2)
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
        "gerado_em": c.agora_iso(), "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)),
        "atualizado": {"repasses": atualizado(82), "cae": atualizado(30), "nutricionistas": atualizado(29)},
        "fonte": "FNDE, Programa Nacional de Alimentação Escolar (PNAE): repasses, Conselhos de Alimentação Escolar "
                 "e cadastro de nutricionistas (Plataforma Antonieta de Barros)",
        "aviso": "O valor do ano em curso vai só até a última atualização do FNDE. Nomes e contatos de conselheiros "
                 "e nutricionistas não são mostrados.",
    })
    pl = m.get("5106752")
    if pl:
        r = pl.get("r", {})
        txt = (f"repasse 2025 R$ {r.get('2025', [0, 0, 0])[2]:,.2f} para {r.get('2025', [0])[0]} alunos; "
               f"CAE {pl.get('cae', {}).get('sit')} (fim {pl.get('cae', {}).get('fim')}); "
               f"nutricionistas ativos {pl.get('nut', {}).get('ativos', 0)}")
        c.log(f"Conferência Pontes e Lacerda: {txt}")
        c.resumo_github([f"**Merenda (PNAE):** {len(gerados)} UFs. Pontes e Lacerda: {txt}"])


if __name__ == "__main__":
    main()
