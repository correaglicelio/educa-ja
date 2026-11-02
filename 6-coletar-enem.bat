@echo off
chcp 65001 >nul
title Educa Ja - ENEM por escola
cd /d "%~dp0"
echo.
echo  Educa Ja - medias do ENEM por escola e por municipio (INEP)
echo.
echo  ATENCAO: esta coleta normalmente roda so no GitHub, toda segunda-feira.
echo  Ela baixa um arquivo de 1 GB para uma pasta temporaria (apagada no fim)
echo  e precisa do 7-Zip instalado. Nao e preciso rodar no computador.
echo.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_enem.py --uf %UFS%
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
