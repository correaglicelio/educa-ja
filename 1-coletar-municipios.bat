@echo off
chcp 65001 >nul
title Educa Ja - tabela de municipios
cd /d "%~dp0"
echo.
echo  Educa Ja - lista de municipios do Brasil (Censo Escolar do INEP)
echo  Le so a tabela de escolas direto no site do INEP (cerca de 140 MB, sem gravar no disco).
echo  Leva de 2 a 10 minutos, conforme a internet. Nao feche esta janela.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_municipios.py
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
