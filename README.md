# Educa Já

Dados abertos da educação de cada município em linguagem simples: escolas, aprendizagem (Ideb, Saeb, ENEM),
fluxo escolar, merenda, dinheiro na escola (PDDE), transporte e quanto a prefeitura aplica no ensino (SIOPE).
Site instalável (PWA) e app Android. Segue o mesmo modelo do [Saúde Já](https://correaglicelio.github.io/saude-ja/).

## Como está organizado

| Pasta / arquivo | O que é |
|---|---|
| `src/index.src.html` | O app inteiro (HTML + CSS + JS, sem framework) |
| `scripts/montar_site.py` | Gera `public/index.html` a partir do `src` |
| `scripts/comum.py` | Funções comuns das coletas: download com novas tentativas, leitura de zip por partes (HTTP Range), CSV em fluxo, planilhas .xlsx, `--uf`, 7º dígito do código IBGE |
| `scripts/testar_fontes.py` | Testa se cada fonte (INEP, FNDE) responde, com tamanho e data |
| `scripts/coletar_municipios.py` | Lista de municípios (Censo Escolar; plano B SIOPE) |
| `scripts/coletar_escolas.py` | Escolas: rede, localização, infraestrutura, matrículas, professores e turmas (Censo Escolar) |
| `scripts/conferir_escolas.py` | Confere escolas e matrículas contra a Sinopse Estatística do INEP |
| `config-github/` | Cópia das rotinas do GitHub (o `9-preparar-github.bat` copia para `.github/workflows`) |
| `public/data/` | Dados prontos para o app (JSON compacto) |
| `.github/workflows/atualizar-dados.yml` | Coleta toda segunda e publica no GitHub Pages |

## Rodar no Windows

- `0-testar-fontes.bat`: confere as fontes (menos de 1 minuto).
- `1-coletar-municipios.bat`: gera a lista de municípios.
- `2-abrir-no-computador.bat`: abre o site em http://localhost:8080.
- `3-coletar-escolas.bat`: escolas do Censo Escolar (linha `set UFS=MT`).

Coletas aceitam `--uf MT`, `--uf MT,GO` ou `--uf todas`. Só biblioteca padrão do Python.

## Fontes

INEP (Censo Escolar, Ideb/Saeb, Indicadores Educacionais, ENEM) e FNDE (SIOPE e Plataforma Antonieta de Barros:
PNAE, PDDE, PNATE, Conselho de Alimentação Escolar, matrículas do FUNDEB).
