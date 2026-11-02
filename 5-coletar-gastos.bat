@echo off
chcp 65001 >nul
title Educa Ja - gastos com educacao (SIOPE)
cd /d "%~dp0"
echo.
echo  Educa Ja - quanto cada prefeitura aplica em educacao (SIOPE, FNDE)
echo  So MT: cerca de 1 minuto. Brasil inteiro (UFS=todas): 10 a 15 minutos.
echo.
rem  Estados: troque MT por outra sigla (MT,GO) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_gastos.py --uf %UFS%
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
