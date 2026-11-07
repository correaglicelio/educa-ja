"""
Educa Já - Repasses do FNDE mês a mês (Portal da Transparência, CGU).

Arquivo mensal de transferências do governo federal (um .zip por mês, sem chave de acesso):
  https://portaldatransparencia.gov.br/download-de-dados/transferencias/AAAAMM
Ficamos só com as ações da educação básica, por município e mês:
  00PI PNAE (merenda) · 0969 PNATE (transporte) · 0515 PDDE (dinheiro na escola) · 0369 salário-educação
O PDDE vai para as associações de pais e mestres (UEx) de cada escola: guardamos também por CNPJ.

O site do Portal não responde fora do Brasil a partir de alguns lugares, mas responde ao GitHub.
Os meses antigos ficam em cache (dados/transferencias/); os 3 últimos meses são sempre baixados de novo.

Gera public/data/transferencias/<código UF>.json e meta.json:
  "meses": ["2024-01", ...]
  "m": {ibge: {"pnae": [valor por mês], "pnate": [...], "pdde": [...], "se": [...]}}   (só programas com valor)
  "estado": {mesmo formato, governo do estado}
  "uex": {cnpj: [nome, ibge, {índice do mês: valor}]}                                   (PDDE por associação)

Uso: python scripts/coletar_transferencias.py [--uf MT | --uf todas]
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

URL = "https://portaldatransparencia.gov.br/download-de-dados/transferencias/{ref}"
SAIDA = c.DADOS_PUBLICOS / "transferencias"
CACHE = c.CACHE / "transferencias"
ANO_INICIAL = 2024
ACOES = {"00PI": "pnae", "0969": "pnate", "0515": "pdde", "0369": "se"}
NOMES = {"pnae": "Merenda (PNAE)", "pnate": "Transporte escolar (PNATE)", "pdde": "Dinheiro Direto na Escola (PDDE)",
         "se": "Salário-educação (cota municipal)"}


def meses_ate_hoje() -> list[str]:
    hoje = date.today()
    out = []
    for a in range(ANO_INICIAL, hoje.year + 1):
        for m in range(1, 13):
            if (a, m) > (hoje.year, hoje.month):
                break
            out.append(f"{a}{m:02d}")
    return out


def baixar_mes(ref: str, recente: bool) -> list[list] | None:
    """Linhas da educação de um mês: [ação, UF, nome do município, tipo favorecido, cnpj, nome favorecido, valor]."""
    arq = CACHE / f"{ref}.json"
    if arq.exists() and not recente:
        return c.ler_json(arq)
    try:
        with c.abrir(URL.format(ref=ref), timeout=300) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
    except Exception as e:  # noqa: BLE001
        c.log(f"   {ref}: sem arquivo ainda ({str(e)[:50]})")
        return None
    linhas = []
    with z.open(z.namelist()[0]) as f:
        leitor = csv.reader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
        cab = next(leitor)
        idx = {k: cab.index(k) for k in ("AÇÃO", "UF", "NOME MUNICÍPIO", "TIPO FAVORECIDO", "CÓDIGO FAVORECIDO",
                                         "NOME FAVORECIDO", "VALOR TRANSFERIDO")}
        for lin in leitor:
            a = ACOES.get(lin[idx["AÇÃO"]].strip())
            if not a:
                continue
            v = c.numero(lin[idx["VALOR TRANSFERIDO"]]) or 0.0
            linhas.append([a, lin[idx["UF"]].strip(), lin[idx["NOME MUNICÍPIO"]].strip(), lin[idx["TIPO FAVORECIDO"]].strip(),
                           lin[idx["CÓDIGO FAVORECIDO"]].strip(), lin[idx["NOME FAVORECIDO"]].strip(), round(v, 2)])
    CACHE.mkdir(parents=True, exist_ok=True)
    c.salvar_json(arq, linhas)
    return linhas


def main() -> None:
    ufs = c.ufs_escolhidas()
    siglas = set(ufs)
    c.log(f"Educa Já - repasses do FNDE mês a mês (Portal da Transparência) - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    casa = c.CasadorMunicipios()
    todos = meses_ate_hoje()
    meses, por_mes = [], {}
    for i, ref in enumerate(todos):
        linhas = baixar_mes(ref, recente=i >= len(todos) - 3)
        if linhas is None:
            continue
        meses.append(ref)
        por_mes[ref] = linhas
    if not meses:
        raise RuntimeError("Nenhum arquivo mensal do Portal da Transparência foi baixado")
    c.log(f"   meses: {meses[0]} a {meses[-1]} ({len(meses)})")
    n = len(meses)
    m: dict[str, dict] = {}
    est: dict[str, dict] = {}
    uex: dict[str, dict] = {}
    for k, ref in enumerate(meses):
        for acao, uf, mun, tipo, cnpj, nome, v in por_mes[ref]:
            if uf not in siglas:
                continue
            t = c.sem_acento(tipo).lower()
            if "estadual" in t:
                alvo = est.setdefault(str(c.SIGLAS[uf]), {})
                cod = None
            else:
                cod = casa.codigo(mun, uf) if mun else None
                if not cod:
                    continue
                alvo = m.setdefault(str(cod), {})
            serie = alvo.setdefault(acao, [0.0] * n)
            serie[k] = round(serie[k] + v, 2)
            if acao == "pdde" and cod and "sem fins" in t and cnpj:
                u = uex.setdefault(cnpj, [nome, cod, {}])
                u[2][k] = round(u[2].get(k, 0) + v, 2)
    if casa.faltando:
        c.log(f"   {len(casa.faltando)} nomes sem correspondência: {sorted(casa.faltando)[:20]}")
    meses_fmt = [f"{r[:4]}-{r[4:]}" for r in meses]
    gerados = []
    for uf in ufs:
        cod_uf = c.SIGLAS[uf]
        mm = {k: v for k, v in m.items() if k.startswith(str(cod_uf))}
        if not mm:
            continue
        uu = {k: v for k, v in uex.items() if str(v[1]).startswith(str(cod_uf))}
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"meses": meses_fmt, "m": mm, "estado": est.get(str(cod_uf), {}), "uex": uu})
        c.log(f"   {uf}: {len(mm):,} municípios, {len(uu):,} associações de escola ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "meses": meses_fmt, "ultimo": meses_fmt[-1],
        "ufs": sorted(set(antigo.get("ufs", [])) | set(gerados)), "programas": NOMES,
        "fonte": "Controladoria-Geral da União, Portal da Transparência: recursos transferidos (FNDE)",
        "aviso": "Valores pelo mês do pagamento. O mês mais recente pode estar incompleto, porque o Portal registra "
                 "os pagamentos aos poucos.",
    })
    pl = m.get("5106752", {})
    if pl:
        def soma(prog, ano):
            return sum(v for r, v in zip(meses, pl.get(prog, [0] * n)) if r.startswith(str(ano)))
        txt = (f"merenda 2025 R$ {soma('pnae', 2025):,.2f}; 2026 até {meses_fmt[-1]} R$ {soma('pnae', 2026):,.2f}; "
               f"PNATE 2026 R$ {soma('pnate', 2026):,.2f}; PDDE 2026 R$ {soma('pdde', 2026):,.2f}")
        c.log(f"Conferência Pontes e Lacerda: {txt}")
        c.resumo_github([f"**Repasses do FNDE (Portal da Transparência):** até {meses_fmt[-1]}. Pontes e Lacerda: {txt}"])


if __name__ == "__main__":
    main()
