"""
Educa Já - Dinheiro Direto na Escola (PDDE, FNDE - Plataforma Antonieta de Barros).

  - produto 26: escolas que podem receber o PDDE: código INEP, CNPJ da associação (UEx), alunos, valor estimado
  - produto 66: execução financeira do PDDE Básico (rede pública): valor pago por escola e parcela
  - produto 70: saldo acumulado nas contas das associações das escolas públicas

O ano em curso vem dos repasses mês a mês do Portal da Transparência (coletar_transferencias.py), pelo CNPJ
da associação. Nomes de dirigentes NÃO são publicados.

Gera public/data/pdde/<código UF>.json e meta.json:
  "e": {escola: [alunos, índice da UEx, estimado, pago, parcelas, saldo]}
  "uex": [[cnpj, nome da associação], ...]

Uso: python scripts/coletar_pdde.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import gzip
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

API = "https://www.fnde.gov.br/plataforma-antonieta-de-barros-api/products/data-products/{id}/"
SAIDA = c.DADOS_PUBLICOS / "pdde"


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


def so_digitos(x: str) -> str:
    return "".join(ch for ch in (x or "") if ch.isdigit())


def main() -> None:
    ufs = c.ufs_escolhidas()
    cods = {c.SIGLAS[u] for u in ufs}
    c.log(f"Educa Já - PDDE - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    esc: dict[int, list] = {}
    uex_idx: dict[str, int] = {}
    uex_lista: list[list] = []
    anos = {}

    def uex(cnpj: str, nome: str) -> int | None:
        cnpj = so_digitos(cnpj)
        if not cnpj:
            return None
        if cnpj not in uex_idx:
            uex_idx[cnpj] = len(uex_lista)
            uex_lista.append([cnpj, nome.strip()])
        return uex_idx[cnpj]

    def reg(cod: int) -> list:
        return esc.setdefault(cod, [0, None, 0.0, 0.0, 0, 0.0])

    # 1) escolas que podem receber (fica o ano mais recente de cada escola)
    n = 0
    for d in ler(26):
        cod = c.inteiro(d.get("co_escola"))
        if not cod or cod // 1_000_000 not in cods:
            continue
        ano = c.inteiro(d.get("ano_exercicio")) or 0
        if ano < anos.get(("26", cod), 0):
            continue
        anos[("26", cod)] = ano
        r = reg(cod)
        r[0] = c.inteiro(d.get("quantidade_alunos")) or 0
        r[1] = uex(d.get("cnpj_uex", ""), d.get("no_razao_social", ""))
        r[2] = round(c.numero(d.get("vl_total_estimado")) or 0.0, 2)
        anos["26"] = max(anos.get("26", 0), ano)
        n += 1
    c.log(f"   escolas que podem receber: {n:,}")

    # 2) execução do PDDE Básico (rede pública)
    n = 0
    for d in ler(66):
        cod = c.inteiro(d.get("co_escola"))
        if not cod or cod // 1_000_000 not in cods:
            continue
        r = reg(cod)
        if r[1] is None:
            r[1] = uex(d.get("cnpj_uex", ""), d.get("no_uex", ""))
        if not r[0]:
            r[0] = c.inteiro(d.get("qt_alunos")) or 0
        r[3] = round(r[3] + (c.numero(d.get("vl_pago_total")) or 0.0), 2)
        r[4] += 1
        anos["66"] = max(anos.get("66", 0), c.inteiro(d.get("an_exercicio")) or 0)
        n += 1
    c.log(f"   parcelas pagas do PDDE Básico: {n:,}")

    # 3) saldo nas contas (uma escola pode ter mais de uma conta)
    n = 0
    for d in ler(70):
        cod = c.inteiro(d.get("co_escola"))
        if not cod or cod // 1_000_000 not in cods:
            continue
        r = reg(cod)
        r[5] = round(r[5] + (c.numero(d.get("saldo_acumulado")) or 0.0), 2)
        anos["70"] = max(anos.get("70", 0), c.inteiro(d.get("an_exercicio")) or 0)
        n += 1
    c.log(f"   contas com saldo: {n:,}")

    gerados = []
    for cod_uf in sorted(cods):
        e = {str(k): v for k, v in esc.items() if k // 1_000_000 == cod_uf}
        if not e:
            continue
        # renumera as associações só deste estado
        usados = sorted({v[1] for v in e.values() if v[1] is not None})
        novo = {u: i for i, u in enumerate(usados)}
        for v in e.values():
            v[1] = novo.get(v[1])
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"e": e, "uex": [uex_lista[u] for u in usados]})
        c.log(f"   {c.SIGLA_DE[cod_uf]}: {len(e):,} escolas, {len(usados):,} associações ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)),
        "ano_estimado": anos.get("26"), "ano_pago": anos.get("66"), "ano_saldo": anos.get("70"),
        "atualizado": {"escolas": atualizado(26), "execucao": atualizado(66), "saldo": atualizado(70)},
        "fonte": "FNDE, Programa Dinheiro Direto na Escola (PDDE): escolas atendidas, execução financeira e saldos "
                 "das contas (Plataforma Antonieta de Barros)",
        "aviso": "O PDDE vai para a associação de pais e mestres (Unidade Executora) de cada escola. Nomes de "
                 "dirigentes não são mostrados.",
    })
    pl = [(k, v) for k, v in esc.items() if 51025800 <= k < 51070000 and k in {51025892, 51025973, 51026244, 51069415}]
    for k, v in pl:
        c.log(f"Conferência {k}: alunos {v[0]}, estimado {v[2]}, pago {v[3]} em {v[4]} parcelas, saldo {v[5]}")


if __name__ == "__main__":
    main()
