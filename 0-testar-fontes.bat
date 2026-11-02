@echo off
chcp 65001 >nul
title Educa Ja - teste das fontes de dados
cd /d "%~dp0"
echo.
echo  Educa Ja - testando se os sites do INEP e do FNDE estao respondendo
echo  Leva menos de 1 minuto. Nada grande e baixado.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo  Python nao encontrado neste computador.
  echo  Instale em https://www.python.org/downloads/  marcando "Add Python to PATH"
  echo  e rode este arquivo de novo.
  echo.
  pause
  exit /b 1
)
%PY% scripts\testar_fontes.py
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause
