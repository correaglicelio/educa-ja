"""
Monta public/index.html a partir de src/index.src.html (mesmo esquema do Saúde Já).

- Se existir src/leaflet.css (mapa, numa fase futura), embute no marcador /*LEAFLET_CSS*/.
- Gera a página completa (com <!doctype>, <head> e <body>) para o GitHub Pages.
- Com --artefato, gera também build/artefato.html (sem o esqueleto), para prévia no Claude.

Uso:  python scripts/montar_site.py [--artefato]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
corpo = (RAIZ / "src" / "index.src.html").read_text("utf-8")
leaflet = RAIZ / "src" / "leaflet.css"
corpo = corpo.replace("/*LEAFLET_CSS*/", leaflet.read_text("utf-8") if leaflet.exists() else "")

pagina = ("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
          "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
          "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
          "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
          "</head>\n<body>\n" + corpo + "\n</body>\n</html>\n")
(RAIZ / "public").mkdir(exist_ok=True)
(RAIZ / "public" / "index.html").write_text(pagina, "utf-8")
print("public/index.html gerado")

if "--artefato" in sys.argv:
    (RAIZ / "build").mkdir(exist_ok=True)
    (RAIZ / "build" / "artefato.html").write_text(corpo, "utf-8")
    print("build/artefato.html gerado")
