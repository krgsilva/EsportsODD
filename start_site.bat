@echo off
title LoL Analyzer - Auto Sync

echo Iniciando sincronizador do Oracle's Elixir...
start "Oracle Sync" cmd /k python sync_oracle_elixir.py

timeout /t 2 /nobreak >nul

echo Iniciando site...
start "LoL Analyzer" cmd /k python app.py
