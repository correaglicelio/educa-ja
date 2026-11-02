"""
Educa Já - confere a coleta de escolas contra a Sinopse Estatística oficial do INEP.

A Sinopse traz os totais já somados pelo INEP por município:
  tabela 1.1 = matrículas da educação básica; tabela 3.1 = estabelecimentos (escolas).
Comparamos com a soma dos nossos dados (public/data/escolas/<UF>.json), por rede.

Baixa a Sinopse (cerca de 140 MB) para uma pasta temporária e apaga no fim.
Uso: python scripts/conferir_escolas.py [--uf MT]
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c  # noqa: E402

URL = "https://download.inep.gov.br/dados_abertos/sinopses_estatisticas/sinopse_estatistica_censo_escolar_{ano}.zip"


def totais_sinopse(xlsx: Path, aba_prefixo: str, ufs: set[str]) -> tuple[dict, list]:
    """{cod_municipio: [total, ...]} da aba; devolve também as linhas de cabeçalho."""
    with __import__("zipfile").ZipFile(xlsx) as z:
        import xml.etree.ElementTree as ET
        livro = ET.fromstring(z.read("xl/workbook.xml"))
    nomes = [s.get("name") for s in livro.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet")]
    aba = next(n for n in nomes if n.startswith(aba_prefixo))
    res, cab = {}, []
    for linha in c.ler_xlsx(xlsx, aba):
        cods = [i for i, v in enumerate(linha) if re.fullmatch(r"\d{7}(\.0)?", v.strip())]
        if not cods:
            if len(cab) < 12 and any(linha):
                cab.append([v for v in linha if v][:12])
            continue
        i = cods[0]
        nums = [c.numero(v) for v in linha[i + 1:]]
        nums = [int(n) if n is not None else 0 for n in nums]
        res[int(float(linha[i]))] = nums[:5]
    return res, cab


def main() -> None:
    ufs = set(c.ufs_escolhidas("MT"))
    meta = c.ler_json(c.DADOS_PUBLICOS / "escolas" / "meta.json")
    if not meta:
        raise SystemExit("Rode antes: python scripts/coletar_escolas.py")
    ano, campos = meta["ano"], meta["campos"]
    im, isit = campos.index("mat_total"), campos.index("situacao")
    nossos_mat, nossos_esc = defaultdict(int), defaultdict(int)
    for uf in ufs:
        dados = c.ler_json(c.DADOS_PUBLICOS / "escolas" / f"{c.SIGLAS[uf]}.json")
        if not dados:
            c.log(f"   sem dados de {uf}")
            continue
        for r in dados["e"]:
            # a Sinopse conta escolas em atividade COM matrícula na educação básica
            if r[isit] != 1 or not r[im]:
                continue
            nossos_mat[r[2]] += r[im]
            nossos_esc[r[2]] += 1

    tmp = Path(tempfile.mkdtemp(prefix="sinopse_"))
    try:
        z = c.ZipRemoto(URL.format(ano=ano))
        nome = z.procurar(".xlsx")
        c.log(f"   baixando {nome.rsplit('/', 1)[-1]} ({z.arquivos[nome]['comp'] / 1e6:.0f} MB)...")
        xlsx = tmp / "sinopse.xlsx"
        with z.abrir(nome) as f, open(xlsx, "wb") as out:
            shutil.copyfileobj(f, out, 1 << 20)
        sin_mat, cab_mat = totais_sinopse(xlsx, "Educação Básica 1.1", ufs)
        sin_esc, cab_esc = totais_sinopse(xlsx, "Educação Básica 3.1", ufs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    linhas = [f"### Conferência com a Sinopse {ano} ({', '.join(sorted(ufs))})", "",
              "| Município | Matrículas (nós × Sinopse) | Escolas com matrícula (nós × Sinopse) |", "|---|---|---|"]
    difs = 0
    muns = {m[0]: m[1] for m in c.ler_json(c.DADOS_PUBLICOS / "municipios.json", {})["m"]}
    for cod in sorted(nossos_mat, key=lambda k: c.sem_acento(muns.get(k, ""))):
        # na Sinopse, a 1ª coluna depois do código é o total (as outras são por etapa)
        a, b = nossos_mat[cod], (sin_mat.get(cod) or [None])[0]
        e1, e2 = nossos_esc[cod], (sin_esc.get(cod) or [None])[0]
        igual = b is not None and e2 is not None and a == b and e1 == e2
        difs += not igual
        if not igual or cod == 5106752:
            linhas.append(f"| {muns.get(cod, cod)} | {a} × {b} | {e1} × {e2} |")
    tot = len(nossos_mat)
    soma = (sum(nossos_mat.values()), sum((sin_mat.get(k) or [0])[0] for k in nossos_mat),
            sum(nossos_esc.values()), sum((sin_esc.get(k) or [0])[0] for k in nossos_mat))
    c.log(f"Total: matrículas {soma[0]:,} × {soma[1]:,}; escolas {soma[2]:,} × {soma[3]:,}")
    linhas.insert(1, f"Total: matrículas {soma[0]:,} × {soma[1]:,}; escolas {soma[2]:,} × {soma[3]:,}")
    c.log(f"\n{tot - difs} de {tot} municípios batem exatamente com a Sinopse (matrículas e escolas).")
    for l in linhas[4:40]:
        c.log("   " + l)
    c.resumo_github(linhas[:4 + 60] + ["", f"**{tot - difs} de {tot} municípios batem exatamente.**"])


if __name__ == "__main__":
    main()
