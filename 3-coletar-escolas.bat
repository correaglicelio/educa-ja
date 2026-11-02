@echo off
chcp 65001 >nul
title Educa Ja - escolas (Censo Escolar)
cd /d "%~dp0"
echo.
echo  Educa Ja - escolas, matriculas, professores e infraestrutura (Censo Escolar do INEP)
echo  Le 4 tabelas direto no site do INEP (cerca de 450 MB, sem gravar no disco).
echo  Leva de 5 a 20 minutos, conforme a internet. Nao feche esta janela.
echo.
rem  Estados: troque MT por outra sigla (MT,GO) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_escolas.py --uf %UFS%
if errorlevel 1 (
  echo.
  echo  A coleta falhou. Veja a mensagem acima e avise o Claude.
  pause
  exit /b 1
)
%PY% scripts\montar_site.py
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause
