"""
Educa Já - Gastos com educação (SIOPE, FNDE).

O SIOPE recebe de cada prefeitura (e do governo do estado), a cada bimestre, quanto foi gasto em
educação. Os valores são ACUMULADOS no ano: o 4º bimestre vai de janeiro a agosto; o 6º é o ano fechado.

API OData: https://www.fnde.gov.br/olinda-ide/servico/DADOS_ABERTOS_SIOPE/versao/v1/odata/
  Indicadores_Siope(Ano_Consulta, Num_Peri, Sig_UF)  -> um registro por ente x indicador
Pedimos só as colunas e os indicadores usados ($select e $filter), por estado e período.

Coleta:
  - anos fechados (6º bimestre) de 2021 até o ano passado;
  - todos os bimestres do ano atual.
Anos fechados antigos ficam em cache (dados/siope/); o ano passado e o atual sempre são baixados de novo
(as prefeituras corrigem declarações).

Gera public/data/gastos/<código UF>.json e meta.json:
  {"m": {ibge7: {"a": [valores por ano fechado], "b": [valores por bimestre do ano atual]}}, "estado": {...}}
  cada "valores" é uma lista na ordem de meta["indicadores"] (ou null quando o ente não enviou).

Uso: python scripts/coletar_gastos.py [--uf MT | --uf MT,GO | --uf todas]
"""
from __future__ import annotations

import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

API = ("https://www.fnde.gov.br/olinda-ide/servico/DADOS_ABERTOS_SIOPE/versao/v1/odata/"
       "Indicadores_Siope(Ano_Consulta=@Ano_Consulta,Num_Peri=@Num_Peri,Sig_UF=@Sig_UF)"
       "?@Ano_Consulta={ano}&@Num_Peri={per}&@Sig_UF='{uf}'&$format=json&$top=500000"
       "&$select=TIPO,COD_MUNI,COD_EXIB,VAL_INDI&$filter={filtro}")
SAIDA = c.DADOS_PUBLICOS / "gastos"
CACHE = c.CACHE / "siope"
ANO_INICIAL = 2021      # FUNDEB permanente (Lei 14.113/2020) começa em 2021

# (código no SIOPE, chave curta, nome na tela, unidade, limite legal)
INDICADORES = [
    ("1.1", "mde", "Receita de impostos aplicada em educação (MDE)", "%", {"min": 25}),
    ("1.2", "fundeb_remun", "FUNDEB na remuneração dos profissionais da educação", "%", {"min": 70}),
    ("1.3", "fundeb_outras", "FUNDEB em outras despesas de educação", "%", {}),
    ("1.4", "fundeb_nao_aplic", "FUNDEB não aplicado no ano", "%", {"max": 10}),
    ("1.5", "vaat_capital", "VAAT aplicado em despesas de capital (obras, equipamentos)", "%", {"min": 15}),
    ("1.6", "vaat_infantil", "VAAT aplicado na educação infantil", "%", {}),
    ("1.7", "vaat_infantil_min", "Mínimo do VAAT exigido para a educação infantil", "%", {}),
    ("2.8", "peso_educacao", "Educação no total de despesas da prefeitura", "%", {}),
    ("2.9", "alimentacao", "Alimentação escolar no total gasto em educação", "%", {}),
    ("4.8", "aluno_basica", "Investimento por aluno da educação básica", "R$", {}),
    ("4.1", "aluno_infantil", "Investimento por aluno da educação infantil", "R$", {}),
    ("4.2", "aluno_fundamental", "Investimento por aluno do ensino fundamental", "R$", {}),
    ("4.10", "professores_aluno", "Gasto com professores por aluno da educação básica", "R$", {}),
    ("8.1", "mde_exigido", "Valor mínimo exigido em MDE (25% dos impostos)", "R$", {}),
    ("8.2", "mde_aplicado", "Valor aplicado em MDE", "R$", {}),
    ("7.2", "fundeb_saldo", "Saldo financeiro do FUNDEB no ano", "R$", {}),
    ("7.3", "fundeb_nao_usado", "Recursos do FUNDEB do ano não utilizados", "R$", {}),
]
COD_IDX = {cod: i for i, (cod, *_r) in enumerate(INDICADORES)}
BIMESTRES = {1: "1º bimestre (janeiro e fevereiro)", 2: "2º bimestre (até abril)", 3: "3º bimestre (até junho)",
             4: "4º bimestre (até agosto)", 5: "5º bimestre (até outubro)", 6: "6º bimestre (ano inteiro)"}
FILTRO = urllib.parse.quote(" or ".join(f"COD_EXIB eq '{cod}'" for cod, *_r in INDICADORES))


def baixar(uf: str, ano: int, per: int) -> dict:
    """{chave do ente: [valores]} de um estado num período. Chave: ibge7 do município ou 'estado'."""
    dados = c.get_json(API.format(ano=ano, per=per, uf=uf, filtro=FILTRO), timeout=120)
    out: dict[str, list] = {}
    for r in dados.get("value", []):
        i = COD_IDX.get(str(r.get("COD_EXIB")).strip())
        if i is None:
            continue
        if r.get("TIPO") == "Estadual" or not r.get("COD_MUNI"):
            chave = "estado"
        else:
            chave = str(c.codigo_ibge(r["COD_MUNI"]))
        v = c.numero(r.get("VAL_INDI"))
        out.setdefault(chave, [None] * len(INDICADORES))[i] = None if v is None else round(v, 2)
    return out


def main() -> None:
    ufs = c.ufs_escolhidas()
    hoje = datetime.now(timezone.utc)
    atual = hoje.year
    fechados = list(range(ANO_INICIAL, atual))
    c.log(f"Educa Já - gastos com educação (SIOPE) - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    c.log(f"   anos fechados {fechados[0]}-{fechados[-1]} e bimestres de {atual}")
    CACHE.mkdir(parents=True, exist_ok=True)
    gerados, envios_uf = [], {}
    for uf in ufs:
        arq_cache = CACHE / f"{uf}.json"
        cache = c.ler_json(arq_cache, {}) or {}
        tarefas = [(a, 6) for a in fechados if a >= atual - 1 or f"{a}-6" not in cache] + [(atual, p) for p in range(1, 7)]
        with ThreadPoolExecutor(6) as ex:
            for (a, p), res in zip(tarefas, ex.map(lambda t: baixar(uf, *t), tarefas)):
                cache[f"{a}-{p}"] = res
        c.salvar_json(arq_cache, cache)

        cod_uf = c.SIGLAS[uf]
        entes = sorted({k for per in cache.values() for k in per})
        m = {}
        for ente in entes:
            a = [cache.get(f"{ano}-6", {}).get(ente) for ano in fechados]
            b = [cache.get(f"{atual}-{p}", {}).get(ente) for p in range(1, 7)]
            m[ente] = {"a": a, "b": b}
        estado = m.pop("estado", None)
        # quantos municípios enviaram cada bimestre do ano atual (para saber qual é o "período corrente")
        envios = [sum(1 for v in m.values() if v["b"][p - 1]) for p in range(1, 7)]
        envios_ano_passado = sum(1 for v in m.values() if v["a"] and v["a"][-1])
        envios_uf[str(cod_uf)] = {"bimestres": envios, "ano_passado": envios_ano_passado}
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"anos": fechados, "atual": atual, "m": m, "estado": estado})
        c.log(f"   {uf}: {len(m):,} municípios; enviaram em {atual} por bimestre: {envios}; "
              f"ano {atual - 1} fechado: {envios_ano_passado} ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)

    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    mesmos = antigo.get("atual") == atual
    todas = sorted(set(antigo.get("ufs", [])) | set(gerados)) if mesmos else gerados
    envios_todos = {**(antigo.get("envios", {}) if mesmos else {}), **envios_uf}
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "anos": fechados, "atual": atual, "ufs": todas,
        "indicadores": [{"cod": cod, "chave": k, "nome": n, "unidade": u, **lim} for cod, k, n, u, lim in INDICADORES],
        "bimestres": BIMESTRES, "envios": envios_todos,
        "fonte": "FNDE, Sistema de Informações sobre Orçamentos Públicos em Educação (SIOPE)",
        "aviso": "Valores declarados pelo próprio município e acumulados no ano. No ano em curso, o percentual "
                 "costuma ficar abaixo do mínimo até o fim do ano: compare com o estado no mesmo bimestre.",
    })
    pl = c.ler_json(SAIDA / "51.json", {}).get("m", {}).get("5106752") if 51 in gerados else None
    if pl:
        a = pl["a"][-1]
        txt = f"{fechados[-1]}: MDE {a[0]}%, FUNDEB remuneração {a[1]}%" if a else f"{fechados[-1]}: não enviado"
        ult = max((p for p in range(1, 7) if pl["b"][p - 1]), default=None)
        txt += f"; {atual} até o {ult}º bimestre: MDE {pl['b'][ult - 1][0]}%" if ult else f"; {atual}: nada enviado"
        c.log(f"Conferência Pontes e Lacerda: {txt}")
        c.resumo_github([f"**Gastos (SIOPE):** {len(gerados)} UFs. Pontes e Lacerda: {txt}"])


if __name__ == "__main__":
    main()
