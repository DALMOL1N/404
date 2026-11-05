@echo off
setlocal
pushd "%~dp0"
set "PYTHONUTF8=1"
call PREPARAR_WINDOWS.bat
if errorlevel 1 goto fim
echo Abra http://127.0.0.1:5070/
echo Dados ficticios. Conta: admin@404.local / DemoSprint7!2026
".venv\Scripts\python.exe" demo_sprint7.py
:fim
pause
popd
