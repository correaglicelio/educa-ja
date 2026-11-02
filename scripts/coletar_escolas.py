"""
Educa Já - Escolas (Censo Escolar do INEP, microdados).

Lê 4 tabelas do Censo direto no zip do INEP (HTTP Range, em fluxo, sem gravar no disco):
  Escola (141 MB): rede, localização, situação e infraestrutura
  Matrícula (123 MB): alunos por etapa, tempo integral, zona rural, transporte escolar
  Docente (88 MB): professores, formação e vínculo
  Turma (100 MB): número de turmas
e junta tudo pelo código da escola (CO_ENTIDADE). Ficam só escolas em atividade ou
paralisadas (as extintas saem).

Gera public/data/escolas/<código UF>.json (lista compacta; nomes dos campos no meta.json)
e public/data/escolas/meta.json.

Uso: python scripts/coletar_escolas.py [--uf MT | --uf MT,GO | --uf todas]
Obs.: o número de professores somado por escola conta duas vezes quem dá aula em mais de
uma escola. Por isso o total do município fica maior que o da Sinopse do INEP (que conta pessoas).
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

SAIDA = c.DADOS_PUBLICOS / "escolas"

# Infraestrutura: cada item vira um bit (1 = sim). A ordem não pode mudar sem mudar o app.
INFRA = [
    ("IN_AGUA_POTAVEL", "Água potável"),
    ("IN_AGUA_INEXISTENTE", "Sem abastecimento de água"),
    ("IN_ENERGIA_INEXISTENTE", "Sem energia elétrica"),
    ("IN_ESGOTO_INEXISTENTE", "Sem esgoto"),
    ("IN_ESGOTO_REDE_PUBLICA", "Esgoto na rede pública"),
    ("IN_BANHEIRO", "Banheiro"),
    ("IN_BANHEIRO_PNE", "Banheiro acessível"),
    ("IN_BIBLIOTECA_SALA_LEITURA", "Biblioteca ou sala de leitura"),
    ("IN_LABORATORIO_CIENCIAS", "Laboratório de ciências"),
    ("IN_LABORATORIO_INFORMATICA", "Laboratório de informática"),
    ("IN_QUADRA_ESPORTES", "Quadra de esportes"),
    ("IN_QUADRA_ESPORTES_COBERTA", "Quadra coberta"),
    ("IN_REFEITORIO", "Refeitório"),
    ("IN_COZINHA", "Cozinha"),
    ("IN_PARQUE_INFANTIL", "Parque infantil"),
    ("IN_INTERNET", "Internet"),
    ("IN_INTERNET_ALUNOS", "Internet para os alunos"),
    ("IN_BANDA_LARGA", "Banda larga"),
    ("IN_ACESSIBILIDADE_INEXISTENTE", "Sem recursos de acessibilidade"),
    ("IN_SALA_ATENDIMENTO_ESPECIAL", "Sala de atendimento especializado (AEE)"),
    ("IN_ALIMENTACAO", "Oferece alimentação escolar"),
    ("IN_AREA_VERDE", "Área verde"),
    ("IN_PATIO_COBERTO", "Pátio coberto"),
    ("IN_SALA_PROFESSOR", "Sala dos professores"),
    ("IN_LIXO_SERVICO_COLETA", "Coleta de lixo"),
    ("IN_LOCAL_FUNC_PREDIO_ESCOLAR", "Funciona em prédio escolar"),
    ("IN_EDUCACAO_INDIGENA", "Educação indígena"),
]

# Campos de cada escola, na ordem da lista do JSON.
CAMPOS = [
    "codigo", "nome", "municipio", "rede", "localizacao", "loc_diferenciada", "situacao", "cat_privada",
    "conveniada", "infra",
    "salas", "salas_climatizadas", "salas_acessiveis", "computadores_alunos",
    "prof_bibliotecario", "prof_psicologo", "prof_assist_social", "prof_nutricionista",
    "mat_total", "mat_creche", "mat_pre", "mat_fund_ai", "mat_fund_af", "mat_medio", "mat_profissional",
    "mat_eja", "mat_especial", "mat_integral", "mat_moram_zona_rural", "mat_transporte_publico",
    "docentes", "docentes_superior", "docentes_licenciatura", "docentes_concursados", "docentes_contratados",
    "turmas",
]
NUM_ESCOLA = ["QT_SALAS_UTILIZADAS", "QT_SALAS_UTILIZA_CLIMATIZADAS", "QT_SALAS_UTILIZADAS_ACESSIVEIS"]
COMPUTADORES = ["QT_DESKTOP_ALUNO", "QT_COMP_PORTATIL_ALUNO", "QT_TABLET_ALUNO"]
PROFISSIONAIS = ["QT_PROF_BIBLIOTECARIO", "QT_PROF_PSICOLOGO", "QT_PROF_ASSIST_SOCIAL", "QT_PROF_NUTRICIONISTA"]
MATRICULA = ["QT_MAT_BAS", "QT_MAT_INF_CRE", "QT_MAT_INF_PRE", "QT_MAT_FUND_AI", "QT_MAT_FUND_AF", "QT_MAT_MED",
             "QT_MAT_PROF", "QT_MAT_EJA", "QT_MAT_ESP", "QT_MAT_BAS_INT", "QT_MAT_ZR_RUR", "QT_TRANSP_PUBLICO"]
DOCENTE = ["QT_DOC_BAS", "QT_DOC_BAS_ESCO_SUP_GRAD", "QT_DOC_BAS_ESCO_SUP_GRAD_LICEN",
           "QT_DOC_BAS_VINCULO_CONCUR", "QT_DOC_BAS_VINCULO_CONTRA"]
TURMA = ["QT_TUR_BAS"]

I_MAT = CAMPOS.index("mat_total")
I_DOC = CAMPOS.index("docentes")
I_TUR = CAMPOS.index("turmas")
REDES = {1: "Federal", 2: "Estadual", 3: "Municipal", 4: "Privada"}


def ler_tabela(z: c.ZipRemoto, tabela: str, por_linha) -> int:
    nome = c.tabela_censo(z, tabela)
    t0, n = time.time(), 0
    c.log(f"   {tabela}: {nome.rsplit('/', 1)[-1]} ({z.arquivos[nome]['comp'] / 1e6:.0f} MB)")
    with z.abrir(nome) as f:
        for n, linha in enumerate(c.linhas_csv(f), 1):
            por_linha(linha)
            if n % 100000 == 0:
                c.log(f"      {n:,} linhas")
    c.log(f"      {n:,} linhas em {time.time() - t0:.0f}s")
    return n


def main() -> None:
    ufs = set(c.ufs_escolhidas())
    c.log(f"Educa Já - escolas (Censo Escolar) - UFs: {'todas' if len(ufs) == 27 else ', '.join(sorted(ufs))}")
    z, ano = c.censo_escolar()
    escolas: dict[str, list] = {}

    def escola(l):
        uf = l["SG_UF"].strip()
        sit = c.inteiro(l["TP_SITUACAO_FUNCIONAMENTO"])
        if uf not in ufs or sit not in (1, 2):
            return
        bits = 0
        for i, (col, _) in enumerate(INFRA):
            if (l.get(col) or "").strip() == "1":
                bits |= 1 << i
        comps = [c.inteiro(l.get(x)) for x in COMPUTADORES]
        reg = [int(l["CO_ENTIDADE"]), " ".join(l["NO_ENTIDADE"].split()), int(l["CO_MUNICIPIO"]),
               c.inteiro(l["TP_DEPENDENCIA"]), c.inteiro(l["TP_LOCALIZACAO"]),
               c.inteiro(l["TP_LOCALIZACAO_DIFERENCIADA"]), sit, c.inteiro(l["TP_CATEGORIA_ESCOLA_PRIVADA"]),
               c.inteiro(l["IN_PODER_PUBLICO_PARCERIA"]), bits,
               *[c.inteiro(l.get(x)) for x in NUM_ESCOLA],
               sum(x for x in comps if x) if any(x is not None for x in comps) else None,
               *[c.inteiro(l.get(x)) for x in PROFISSIONAIS]]
        reg += [None] * (len(CAMPOS) - len(reg))
        escolas[l["CO_ENTIDADE"]] = reg

    def completar(colunas, inicio):
        def f(l):
            reg = escolas.get(l["CO_ENTIDADE"])
            if reg is not None:
                for k, col in enumerate(colunas):
                    reg[inicio + k] = c.inteiro(l.get(col))
        return f

    ler_tabela(z, "escola", escola)
    c.log(f"   {len(escolas):,} escolas em atividade ou paralisadas")
    ler_tabela(z, "matricula", completar(MATRICULA, I_MAT))
    ler_tabela(z, "docente", completar(DOCENTE, I_DOC))
    ler_tabela(z, "turma", completar(TURMA, I_TUR))

    nomes_mun = {m[0]: m[1] for m in (c.ler_json(c.DADOS_PUBLICOS / "municipios.json", {}) or {}).get("m", [])}
    por_uf: dict[str, list] = defaultdict(list)
    for reg in escolas.values():
        por_uf[str(reg[2])[:2]].append(reg)
    gerados = []
    for cod_uf, lista in sorted(por_uf.items()):
        lista.sort(key=lambda r: (c.sem_acento(nomes_mun.get(r[2], "")), r[3] or 9, c.sem_acento(r[1])))
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"ano": ano, "e": lista})
        ativas = sum(1 for r in lista if r[6] == 1)
        mat = sum(r[I_MAT] or 0 for r in lista)
        c.log(f"   {c.SIGLA_DE[int(cod_uf)]}: {ativas:,} escolas em atividade, {mat:,} matrículas ({tam / 1e6:.2f} MB)")
        gerados.append(int(cod_uf))

    meta_antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    todas_ufs = sorted(set(meta_antigo.get("ufs", [])) | set(gerados)) if meta_antigo.get("ano") == ano else gerados
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ano": ano, "fonte": f"INEP, Censo Escolar da Educação Básica {ano} (microdados)",
        "data_referencia": f"última quarta-feira de maio de {ano}", "ufs": todas_ufs, "campos": CAMPOS,
        "infra": [r for _, r in INFRA], "redes": REDES,
        "localizacao": {1: "Urbana", 2: "Rural"},
        "loc_diferenciada": {0: "Não", 1: "Área de assentamento", 2: "Terra indígena", 3: "Comunidade quilombola",
                             8: "Povos e comunidades tradicionais"},
        "situacao": {1: "Em atividade", 2: "Paralisada"},
        "cat_privada": {1: "Particular", 2: "Comunitária", 3: "Confessional", 4: "Filantrópica"},
        "aviso_docentes": "Professores somados por escola: quem dá aula em mais de uma escola conta mais de uma vez.",
    })

    pl = [r for r in escolas.values() if r[2] == 5106752]
    if pl:
        rede = defaultdict(lambda: [0, 0])
        for r in pl:
            if r[6] == 1:
                rede[REDES.get(r[3])][0] += 1
                rede[REDES.get(r[3])][1] += r[I_MAT] or 0
        texto = ", ".join(f"{k}: {v[0]} escolas / {v[1]:,} matrículas" for k, v in sorted(rede.items()))
        c.log(f"Conferência Pontes e Lacerda (em atividade): {texto}")
        c.resumo_github([f"**Escolas {ano}:** {len(escolas):,} (em atividade ou paralisadas). Pontes e Lacerda: {texto}"])


if __name__ == "__main__":
    main()
