@echo off
chcp 65001 >nul
title Educa Ja - Ideb e Saeb
cd /d "%~dp0"
echo.
echo  Educa Ja - Ideb e Saeb (planilhas do INEP: municipios, escolas, estados e Brasil)
echo  Baixa cerca de 300 MB de planilhas para uma pasta temporaria e apaga no fim.
echo  Leva de 10 a 30 minutos, conforme a internet. Nao feche esta janela.
echo.
rem  Estados: troque MT por outra sigla (MT,GO) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_ideb.py --uf %UFS%
if errorlevel 1 (
  echo.
  echo  A coleta falhou. Veja a mensagem acima e avise o Claude.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause
