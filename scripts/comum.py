"""
Educa Já - funções comuns das coletas (só biblioteca padrão do Python).

- abrir()/baixar()/get_json(): downloads com novas tentativas, espera crescente e
  plano B para certificados do governo que o Python não reconhece.
- ZipRemoto: lê um .zip direto no servidor usando HTTP Range, sem baixar o arquivo
  inteiro. Serve para os microdados do INEP (o Censo 2025 tem 537 MB, mas a tabela
  de escolas tem 141 MB e é tudo que precisamos dela).
- linhas_csv(): lê CSV em fluxo (linha a linha), sem gravar no disco.
- ler_xlsx(): lê planilhas .xlsx do INEP (Ideb, indicadores) sem bibliotecas extras.
- ufs_escolhidas(): --uf MT | --uf MT,GO | --uf todas.
- codigo_ibge(): completa o 7º dígito do código do município (o IBGE não responde
  aos servidores do GitHub, então não dá para buscar lá).
"""
from __future__ import annotations

import codecs
import csv
import io
import json
import os
import ssl
import struct
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS_PUBLICOS = RAIZ / "public" / "data"
CACHE = RAIZ / "dados"
USER_AGENT = "EducaJa/1.0 (+https://github.com/correaglicelio/educa-ja)"

SIGLAS = {"RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22, "CE": 23,
          "RN": 24, "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35,
          "PR": 41, "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53}
SIGLA_DE = {v: k for k, v in SIGLAS.items()}
NOMES_UF = {"RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima", "PA": "Pará", "AP": "Amapá",
            "TO": "Tocantins", "MA": "Maranhão", "PI": "Piauí", "CE": "Ceará", "RN": "Rio Grande do Norte",
            "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas", "SE": "Sergipe", "BA": "Bahia",
            "MG": "Minas Gerais", "ES": "Espírito Santo", "RJ": "Rio de Janeiro", "SP": "São Paulo",
            "PR": "Paraná", "SC": "Santa Catarina", "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul",
            "MT": "Mato Grosso", "GO": "Goiás", "DF": "Distrito Federal"}


# ---------------------------------------------------------------- textos e parâmetros

def log(msg: str) -> None:
    print(msg, flush=True)


def agora_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def chave_nome(nome: str, uf: str = "") -> str:
    """'Pontes e Lacerda', 'MT' -> 'PONTES E LACERDA|MT'. Usado para ligar bases sem código IBGE."""
    base = sem_acento(nome).upper().replace("'", " ").replace("-", " ").replace("`", " ")
    base = " ".join(base.split())
    return f"{base}|{uf.upper()}" if uf else base


def ufs_escolhidas(padrao: str = "todas") -> list[str]:
    """Lê --uf MT | --uf MT,GO | --uf todas. Devolve a lista de siglas, em ordem."""
    val = padrao
    if "--uf" in sys.argv:
        i = sys.argv.index("--uf")
        val = sys.argv[i + 1] if i + 1 < len(sys.argv) else "todas"
    if val.strip().lower() in ("todas", "todos", "br", "brasil"):
        return list(SIGLAS)
    escolhidas = [s.strip().upper() for s in val.split(",") if s.strip()]
    ruins = [s for s in escolhidas if s not in SIGLAS]
    if ruins or not escolhidas:
        raise SystemExit(f"UF desconhecida: {val}. Use a sigla (--uf MT ou --uf MT,GO) ou --uf todas.")
    return escolhidas


# ---------------------------------------------------------------- código IBGE

# Municípios cujo 7º dígito não segue a regra do IBGE (lista oficial de exceções).
_EXCECOES_DV = {c // 10: c for c in (2201919, 2201988, 2202251, 2611533, 3117836, 3152131, 4305871, 5203939, 5203962)}


def codigo_ibge(cod6: int | str) -> int:
    """Completa o código de 6 dígitos (SIOPE, SIOPS) para os 7 dígitos do IBGE."""
    c = int(str(cod6)[:6])
    if c in _EXCECOES_DV:
        return _EXCECOES_DV[c]
    soma = 0
    for i, d in enumerate(f"{c:06d}"):
        p = int(d) * (1 if i % 2 == 0 else 2)
        soma += p // 10 + p % 10
    return c * 10 + (10 - soma % 10) % 10


# ---------------------------------------------------------------- downloads

_CTX = ssl.create_default_context()
_CTX_FRACO = False


def _sem_verificacao() -> None:
    """Alguns sites do governo usam cadeia ICP-Brasil que o Python não conhece. Dados públicos: seguimos sem verificar."""
    global _CTX, _CTX_FRACO
    if not _CTX_FRACO:
        log("   (aviso: certificado do site não reconhecido; seguindo sem verificação, os dados são públicos)")
        _CTX = ssl._create_unverified_context()
        _CTX_FRACO = True


def abrir(url: str, inicio: int | None = None, fim: int | None = None, tentativas: int = 5,
          timeout: int = 90, metodo: str = "GET", cabecalhos: dict | None = None):
    """Abre a URL e devolve a resposta (para ler em fluxo). inicio/fim pedem só um pedaço (HTTP Range)."""
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if inicio is not None:
        h["Range"] = f"bytes={inicio}-{'' if fim is None else fim}"
    if cabecalhos:
        h.update(cabecalhos)
    ultimo = None
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=h, method=metodo)
            r = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            if inicio is not None and metodo == "GET" and r.status != 206:
                r.close()
                raise RuntimeError(f"o servidor não aceitou leitura por partes (HTTP {r.status})")
            return r
        except urllib.error.HTTPError as ex:
            if ex.code in (400, 403, 404, 410):
                raise
            ultimo = ex
        except urllib.error.URLError as ex:
            if isinstance(getattr(ex, "reason", None), ssl.SSLCertVerificationError) and not _CTX_FRACO:
                _sem_verificacao()
                continue
            ultimo = ex
        except (TimeoutError, ConnectionError, OSError) as ex:
            ultimo = ex
        espera = min(60, 3 * 2 ** t)
        log(f"   nova tentativa em {espera}s ({type(ultimo).__name__}: {ultimo})")
        time.sleep(espera)
    raise RuntimeError(f"Não consegui acessar {url}: {ultimo}")


def baixar(url: str, inicio: int | None = None, fim: int | None = None, **kw) -> bytes:
    with abrir(url, inicio, fim, **kw) as r:
        return r.read()


def info(url: str) -> dict:
    """Tamanho e data de um arquivo no servidor, sem baixar (HEAD)."""
    with abrir(url, metodo="HEAD", tentativas=3, timeout=40) as r:
        return {"status": r.status, "bytes": int(r.headers.get("Content-Length") or 0),
                "modificado": r.headers.get("Last-Modified")}


def get_json(url: str, **kw):
    with abrir(url, cabecalhos={"Accept": "application/json"}, **kw) as r:
        texto = r.read().decode("utf-8-sig")
    # a API do FNDE (Olinda) às vezes embrulha a resposta em /* ... */
    texto = texto.strip()
    if texto.startswith("/*") and texto.endswith("*/"):
        texto = texto[2:-2]
    return json.loads(texto)


class _LeitorRange(io.RawIOBase):
    """Lê um trecho do arquivo remoto em fluxo; se a conexão cair, retoma de onde parou."""

    def __init__(self, url: str, inicio: int, tamanho: int):
        self.url, self.pos, self.fim = url, inicio, inicio + tamanho
        self.resp = None
        self.quedas = 0

    def readable(self):
        return True

    def readinto(self, b):
        if self.pos >= self.fim:
            return 0
        while True:
            try:
                if self.resp is None:
                    self.resp = abrir(self.url, self.pos, self.fim - 1, timeout=120)
                n = self.resp.readinto(memoryview(b)[: min(len(b), self.fim - self.pos)])
                if n == 0:
                    raise ConnectionError("conexão encerrada antes do fim")
                self.pos += n
                return n
            except (ConnectionError, TimeoutError, OSError) as ex:
                self.quedas += 1
                if self.quedas > 20:
                    raise RuntimeError(f"Conexão caiu demais lendo {self.url}") from ex
                log(f"   conexão caiu em {self.pos:,} bytes; retomando...")
                try:
                    self.resp and self.resp.close()
                except Exception:
                    pass
                self.resp = None
                time.sleep(3)

    def close(self):
        try:
            self.resp and self.resp.close()
        finally:
            super().close()


class _Descompactor(io.RawIOBase):
    def __init__(self, bruto):
        self.bruto, self.z, self.sobra = bruto, zlib.decompressobj(-15), b""

    def readable(self):
        return True

    def readinto(self, b):
        while not self.sobra:
            if self.z.eof:
                return 0
            pedaco = self.bruto.read(1 << 20)
            self.sobra = self.z.decompress(pedaco) if pedaco else self.z.flush()
            if not pedaco and not self.sobra:
                return 0
        n = min(len(b), len(self.sobra))
        b[:n], self.sobra = self.sobra[:n], self.sobra[n:]
        return n


class ZipRemoto:
    """Um .zip num servidor que aceita HTTP Range. Lista os arquivos e abre um deles em fluxo."""

    def __init__(self, url: str):
        self.url = url
        self.tamanho = info(url)["bytes"]
        if not self.tamanho:
            raise RuntimeError(f"O servidor não informou o tamanho de {url}")
        cauda = min(self.tamanho, 1 << 20)
        fim = baixar(url, self.tamanho - cauda, self.tamanho - 1)
        p = fim.rfind(b"PK\x05\x06")
        if p < 0:
            raise RuntimeError("Fim do zip não encontrado")
        _, _, _, _, n, tam_dir, ini_dir, _ = struct.unpack("<IHHHHIIH", fim[p:p + 22])
        q = fim.rfind(b"PK\x06\x06")          # zip64: arquivos ou diretório além de 4 GB
        if q >= 0:
            n, tam_dir, ini_dir = struct.unpack("<QQQ", fim[q + 32:q + 56])
        diretorio = baixar(url, ini_dir, ini_dir + tam_dir - 1)
        self.arquivos: dict[str, dict] = {}
        i = 0
        while i + 46 <= len(diretorio) and diretorio[i:i + 4] == b"PK\x01\x02":
            (_, _, _, flags, metodo, _, _, _, comp, desc, nl, el, cl, _, _, _, ofs) = struct.unpack(
                "<IHHHHHHIIIHHHHHII", diretorio[i:i + 46])
            nome_b = diretorio[i + 46:i + 46 + nl]
            nome = nome_b.decode("utf-8" if flags & 0x800 else "cp437")
            extra = diretorio[i + 46 + nl:i + 46 + nl + el]
            j = 0
            while j + 4 <= len(extra):
                eid, etam = struct.unpack("<HH", extra[j:j + 4])
                if eid == 1:
                    vals, k = extra[j + 4:j + 4 + etam], 0
                    if desc == 0xFFFFFFFF:
                        desc, k = struct.unpack("<Q", vals[k:k + 8])[0], k + 8
                    if comp == 0xFFFFFFFF:
                        comp, k = struct.unpack("<Q", vals[k:k + 8])[0], k + 8
                    if ofs == 0xFFFFFFFF:
                        ofs = struct.unpack("<Q", vals[k:k + 8])[0]
                j += 4 + etam
            if not nome.endswith("/"):
                self.arquivos[nome] = {"metodo": metodo, "comp": comp, "tam": desc, "ofs": ofs}
            i += 46 + nl + el + cl

    def procurar(self, *pedacos: str) -> str:
        """Nome do primeiro arquivo cujo nome contém todos os pedaços (sem diferenciar maiúsculas)."""
        for nome in self.arquivos:
            n = sem_acento(nome).lower()
            if all(sem_acento(p).lower() in n for p in pedacos):
                return nome
        raise KeyError(f"Nenhum arquivo com {pedacos} em {self.url}")

    def abrir(self, nome: str) -> io.BufferedReader:
        a = self.arquivos[nome]
        cab = baixar(self.url, a["ofs"], a["ofs"] + 29)
        nl, el = struct.unpack("<HH", cab[26:30])
        inicio = a["ofs"] + 30 + nl + el
        bruto = io.BufferedReader(_LeitorRange(self.url, inicio, a["comp"]), 1 << 20)
        if a["metodo"] == 0:
            return bruto
        if a["metodo"] == 8:
            return io.BufferedReader(_Descompactor(bruto), 1 << 20)
        if a["metodo"] == 9:
            raise RuntimeError("Este arquivo usa Deflate64; abra com o 7-Zip (ver coletar_enem.py).")
        raise RuntimeError(f"Compressão {a['metodo']} não suportada")

    def ler(self, nome: str) -> bytes:
        with self.abrir(nome) as f:
            return f.read()


def linhas_csv(fluxo_binario, sep: str = ";", encoding: str = "latin-1"):
    """Gera dicionários linha a linha de um CSV em fluxo (o INEP usa ponto e vírgula e latin-1)."""
    texto = io.TextIOWrapper(fluxo_binario, encoding=encoding, errors="replace", newline="")
    yield from csv.DictReader(texto, delimiter=sep)


# ---------------------------------------------------------------- planilhas .xlsx

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NSR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _coluna(ref: str) -> int:
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + ord(ch.upper()) - 64
        else:
            break
    return n - 1


def ler_xlsx(origem, aba: int | str = 0):
    """Gera as linhas (listas de textos) de uma aba de um .xlsx. origem: caminho, bytes ou arquivo aberto."""
    if isinstance(origem, (bytes, bytearray)):
        origem = io.BytesIO(origem)
    with zipfile.ZipFile(origem) as z:
        textos: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as f:
                for _, el in ET.iterparse(f):
                    if el.tag == _NS + "si":
                        textos.append("".join(t.text or "" for t in el.iter(_NS + "t")))
                        el.clear()
        livro = ET.fromstring(z.read("xl/workbook.xml"))
        abas = [(s.get("name"), s.get(_NSR + "id")) for s in livro.iter(_NS + "sheet")]
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        alvo = {r.get("Id"): r.get("Target") for r in rels}
        if isinstance(aba, int):
            rid = abas[aba][1]
        else:
            rid = next(r for n, r in abas if n == aba)
        caminho = alvo[rid].lstrip("/")
        caminho = caminho if caminho.startswith("xl/") else "xl/" + caminho
        with z.open(caminho) as f:
            for _, el in ET.iterparse(f):
                if el.tag != _NS + "row":
                    continue
                linha: list[str] = []
                for c in el.iter(_NS + "c"):
                    col = _coluna(c.get("r", "")) if c.get("r") else len(linha)
                    while len(linha) < col:
                        linha.append("")
                    tipo, v = c.get("t"), c.find(_NS + "v")
                    if tipo == "s" and v is not None:
                        val = textos[int(v.text)]
                    elif tipo == "inlineStr":
                        val = "".join(t.text or "" for t in c.iter(_NS + "t"))
                    else:
                        val = v.text if v is not None and v.text is not None else ""
                    linha.append(val)
                yield linha
                el.clear()


def numero(txt) -> float | None:
    """'6,3' / '6.3' / '-' / '' -> float ou None."""
    if txt is None:
        return None
    t = str(txt).strip().replace(",", ".")
    if t in ("", "-", "--", "ND", "*", "nan"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------- saída

def salvar_json(caminho: Path, obj) -> int:
    """Grava JSON compacto (sem espaços) e devolve o tamanho em bytes."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), "utf-8")
    os.replace(tmp, caminho)
    return caminho.stat().st_size


def ler_json(caminho: Path, padrao=None):
    try:
        return json.loads(caminho.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def resumo_github(linhas: list[str]) -> None:
    """Escreve no resumo da rodada do GitHub Actions (quando roda lá)."""
    arq = os.environ.get("GITHUB_STEP_SUMMARY")
    if arq:
        with open(arq, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
