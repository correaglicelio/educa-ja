@echo off
chcp 65001 >nul
title Educa Ja - endereco e localizacao das escolas (Catalogo do INEP)
cd /d "%~dp0"
echo.
echo  Educa Ja - latitude, longitude, endereco e telefone
echo  Leva cerca de 1 minuto.
echo.
rem  Estados: troque MT por outra sigla (MT,GO) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_locais.py --uf %UFS%
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
