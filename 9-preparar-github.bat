@echo off
chcp 65001 >nul
title Educa Ja - preparar atualizacao automatica no GitHub
cd /d "%~dp0"
echo.
echo  Copiando a rotina de atualizacao para a pasta .github\workflows ...
if not exist ".github\workflows" mkdir ".github\workflows"
copy /Y "config-github\atualizar-dados.yml" ".github\workflows\atualizar-dados.yml" >nul
if exist ".github\workflows\atualizar-dados.yml" (
  echo  Pronto! Arquivo copiado. Volte ao Claude.
) else (
  echo  Nao consegui copiar. Avise o Claude.
)
echo.
pause
