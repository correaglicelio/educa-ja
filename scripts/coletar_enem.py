"""
Educa Já - ENEM por escola e por município (INEP, microdados do ENEM).

O arquivo RESULTADOS_<ano>.csv traz, para cada participante, as notas das 4 provas e da redação e,
para quem estava terminando o ensino médio, o código INEP da escola, o município e a rede da escola.
Calculamos as médias de quem fez as 4 provas e a redação (presentes nos dois dias).

O RESULTADOS de 2025 vem compactado em "Deflate64", que o Python sozinho não abre: usamos o 7-Zip
(o GitHub já tem; no Windows, se não houver 7-Zip, a coleta avisa e para). Os anos com compressão
comum (2024) são lidos direto do servidor, sem baixar o zip inteiro.

O arquivo grande (1 GB) nunca fica guardado: vai para uma pasta temporária e é apagado no fim.
Se o zip do INEP não mudou desde a última coleta, nada é baixado (o ENEM sai uma vez por ano).

Gera public/data/enem/<código UF>.json e brasil.json e meta.json:
  "e": {escola: [por ano: null | [n] (menos de 10) | [n, CN, CH, LC, MT, redação, média]]}
  "m": {município: {rede: [por ano: null | [inscritos, n, CN, CH, LC, MT, redação, média]]}}  (rede "0" = todas)

Uso: python scripts/coletar_enem.py [--uf MT | --uf todas] [--forcar]
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

BASE = "https://download.inep.gov.br/microdados/microdados_enem_{ano}.zip"
SAIDA = c.DADOS_PUBLICOS / "enem"
MINIMO = 10          # médias só de escolas com pelo menos 10 participantes
AREAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]
NOMES_AREAS = ["Ciências da Natureza", "Ciências Humanas", "Linguagens e Códigos", "Matemática", "Redação"]


def ano_mais_recente() -> int:
    atual = datetime.now(timezone.utc).year
    for a in (atual, atual - 1, atual - 2):
        try:
            c.info(BASE.format(ano=a))
            return a
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("Nenhum microdado do ENEM encontrado no INEP")


def achar_7zip() -> str | None:
    for nome in ("7z", "7zz", "7za"):
        if shutil.which(nome):
            return shutil.which(nome)
    for p in (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe", r"D:\7-Zip\7z.exe"):
        if os.path.exists(p):
            return p
    return None


class Resultados:
    """Abre o RESULTADOS_<ano>.csv em fluxo, pelo servidor (Deflate comum) ou pelo 7-Zip (Deflate64)."""

    def __init__(self, ano: int):
        self.url = BASE.format(ano=ano)
        self.z = c.ZipRemoto(self.url)
        self.nome = self.z.procurar("RESULTADOS", ".csv")
        self.tmp = None
        self.proc = None

    def __enter__(self):
        a = self.z.arquivos[self.nome]
        if a["metodo"] in (0, 8):
            self.fluxo = self.z.abrir(self.nome)
            return io.TextIOWrapper(self.fluxo, encoding="latin-1", newline="")
        exe = achar_7zip()
        if not exe:
            raise RuntimeError("O RESULTADOS do ENEM usa Deflate64 e precisa do 7-Zip. Essa coleta roda no GitHub "
                               "(que já tem o 7-Zip); no computador, instale o 7-Zip para rodar aqui.")
        self.tmp = Path(tempfile.mkdtemp(prefix="enem_", dir=c.CACHE if c.CACHE.exists() else None))
        zipf = self.tmp / "enem.zip"
        c.log(f"   baixando o zip do ENEM ({self.z.tamanho / 1e9:.1f} GB) para uma pasta temporária...")
        with c.abrir(self.url, timeout=300) as r, open(zipf, "wb") as out:
            shutil.copyfileobj(r, out, 1 << 22)
        self.proc = subprocess.Popen([exe, "e", "-so", str(zipf), self.nome], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)
        self.fluxo = self.proc.stdout
        return io.TextIOWrapper(self.fluxo, encoding="latin-1", newline="")

    def __exit__(self, *exc):
        try:
            self.fluxo.close()
        except Exception:  # noqa: BLE001
            pass
        if self.proc:
            self.proc.kill()
            self.proc.wait()
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)


def nota(v: str):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def processar(ano: int, cod_ufs: set[int]) -> tuple[dict, dict, dict]:
    """Soma por escola, por município x rede e por UF x rede (e Brasil). Devolve somas cruas."""
    esc: dict[int, list] = {}
    mun: dict[tuple, list] = {}
    uf: dict[tuple, list] = {}
    n_linhas = 0

    def somar(d, k, valores, presente):
        s = d.get(k)
        if s is None:
            s = d[k] = [0, 0] + [0.0] * 5      # inscritos, presentes, somas das 5 notas
        s[0] += 1
        if presente:
            s[1] += 1
            for i, v in enumerate(valores):
                s[2 + i] += v

    with Resultados(ano) as f:
        leitor = csv.reader(f, delimiter=";")
        cab = {k: i for i, k in enumerate(next(leitor))}
        i_esc, i_mun, i_uf, i_rede = cab["CO_ESCOLA"], cab["CO_MUNICIPIO_ESC"], cab["CO_UF_ESC"], cab["TP_DEPENDENCIA_ADM_ESC"]
        i_notas = [cab[a] for a in AREAS]
        i_red = cab.get("TP_STATUS_REDACAO")
        for lin in leitor:
            n_linhas += 1
            if n_linhas % 1_000_000 == 0:
                c.log(f"      {n_linhas:,} linhas...")
            if len(lin) < len(cab):
                continue
            cod_uf = c.inteiro(lin[i_uf])
            if not lin[i_esc] or not cod_uf:
                continue
            valores = [nota(lin[i]) for i in i_notas]
            presente = all(v is not None for v in valores) and (i_red is None or lin[i_red].strip() == "1")
            rede = c.inteiro(lin[i_rede]) or 0
            somar(uf, (cod_uf, 0), valores, presente)
            somar(uf, (cod_uf, rede), valores, presente)
            somar(uf, ("br", 0), valores, presente)
            somar(uf, ("br", rede), valores, presente)
            if cod_uf not in cod_ufs:
                continue
            somar(esc, c.inteiro(lin[i_esc]), valores, presente)
            m = c.inteiro(lin[i_mun])
            somar(mun, (m, 0), valores, presente)
            somar(mun, (m, rede), valores, presente)
    c.log(f"   ENEM {ano}: {n_linhas:,} participantes lidos; {len(esc):,} escolas")
    return esc, mun, uf


def medias(s: list) -> list | None:
    """[inscritos, presentes, CN, CH, LC, MT, redação, média geral] com 1 casa."""
    n = s[1]
    if not n:
        return [s[0], 0]
    m = [round(x / n, 1) for x in s[2:]]
    return [s[0], n, *m, round(sum(m) / 5, 1)]


def main() -> None:
    ufs = c.ufs_escolhidas()
    cod_ufs = {c.SIGLAS[u] for u in ufs}
    c.log(f"Educa Já - ENEM - UFs: {'todas' if len(ufs) == 27 else ', '.join(ufs)}")
    ano = ano_mais_recente()
    anos = [ano - 1, ano]
    modificado = c.info(BASE.format(ano=ano)).get("modificado")
    antigo = c.ler_json(SAIDA / "meta.json", {}) or {}
    if ("--forcar" not in sys.argv and antigo.get("ano") == ano and antigo.get("modificado") == modificado
            and cod_ufs <= set(antigo.get("ufs", []))):
        c.log(f"   ENEM {ano} sem novidade desde a última coleta ({modificado}). Nada a fazer.")
        c.resumo_github([f"**ENEM:** {ano} sem novidade, mantidos os dados."])
        return

    por_ano = {a: processar(a, cod_ufs) for a in anos}

    gerados = []
    for cod_uf in sorted(cod_ufs):
        pref = str(cod_uf)
        e_out: dict[str, list] = {}
        m_out: dict[str, dict] = {}
        for k, a in enumerate(anos):
            esc, mun, _ = por_ano[a]
            for cod, s in esc.items():
                if str(cod).startswith(pref) and len(str(cod)) == 8:
                    md = medias(s)
                    v = [md[1]] if md[1] < MINIMO else [md[1], *md[2:]]
                    e_out.setdefault(str(cod), [None] * len(anos))[k] = v
            for (mcod, rede), s in mun.items():
                if mcod and str(mcod).startswith(pref):
                    m_out.setdefault(str(mcod), {}).setdefault(str(rede), [None] * len(anos))[k] = medias(s)
        if not m_out:
            continue
        tam = c.salvar_json(SAIDA / f"{cod_uf}.json", {"anos": anos, "e": e_out, "m": m_out})
        c.log(f"   {c.SIGLA_DE[cod_uf]}: {len(m_out):,} municípios, {len(e_out):,} escolas ({tam / 1e6:.2f} MB)")
        gerados.append(cod_uf)

    # estados e Brasil (sempre todos, para comparar)
    br: dict[str, dict] = {}
    for k, a in enumerate(anos):
        for (u, rede), s in por_ano[a][2].items():
            br.setdefault(str(u), {}).setdefault(str(rede), [None] * len(anos))[k] = medias(s)
    c.salvar_json(SAIDA / "brasil.json", {"anos": anos, "uf": br})

    todas = sorted(set(antigo.get("ufs", [])) | set(gerados)) if antigo.get("ano") == ano else gerados
    c.salvar_json(SAIDA / "meta.json", {
        "gerado_em": c.agora_iso(), "ano": ano, "anos": anos, "ufs": todas, "modificado": modificado,
        "minimo": MINIMO, "areas": NOMES_AREAS,
        "fonte": f"INEP, Microdados do ENEM {anos[0]} e {anos[1]}",
        "periodo": f"ENEM {ano}, provas aplicadas em novembro de {ano}",
        "aviso": "Só alunos que fizeram o ENEM enquanto cursavam o último ano do ensino médio (com escola informada) "
                 "e que fizeram as 4 provas e a redação. O ENEM é voluntário: a média depende de quem escolheu fazer "
                 f"a prova. Escolas com menos de {MINIMO} participantes não têm média divulgada.",
    })
    pl = (c.ler_json(SAIDA / "51.json", {}) or {}).get("m", {}).get("5106752") if 51 in gerados else None
    if pl:
        t = pl.get("0", [None, None])[-1]
        txt = f"{t[1]} participantes de {t[0]} inscritos, média geral {t[7]}" if t and len(t) > 2 else "sem dado"
        c.log(f"Conferência Pontes e Lacerda (ENEM {ano}): {txt}")
        c.resumo_github([f"**ENEM {ano}:** {len(gerados)} UFs. Pontes e Lacerda: {txt}"])


if __name__ == "__main__":
    main()
