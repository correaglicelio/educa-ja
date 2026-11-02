@echo off
chcp 65001 >nul
title Educa Ja - site no computador
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\montar_site.py
echo.
echo  Abrindo o Educa Ja em http://localhost:8080
echo  Para parar, feche esta janela.
echo.
start "" http://localhost:8080
%PY% -m http.server 8080 --directory public
