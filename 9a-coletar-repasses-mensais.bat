@echo off
chcp 65001 >nul
title Educa Ja - repasses do FNDE mes a mes (Portal da Transparencia)
cd /d "%~dp0"
echo.
echo  Educa Ja - merenda, transporte, PDDE e salario-educacao por mes
echo  Baixa um arquivo por mes (5 MB cada). Leva de 5 a 10 minutos.
echo.
rem  Estados: troque MT por outra sigla (MT,GO) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_transferencias.py --uf %UFS%
if errorlevel 1 (
  echo.
  echo  A coleta parou. Rode de novo ou avise o Claude.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause
