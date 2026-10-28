@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" goto instalar
where py >nul 2>nul
if errorlevel 1 goto usar_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto python_ausente
py -3 -m venv .venv
if errorlevel 1 goto erro
goto instalar
:usar_python
where python >nul 2>nul
if errorlevel 1 goto python_ausente
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto python_ausente
python -m venv .venv
if errorlevel 1 goto erro
:instalar
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto ambiente_antigo
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -c "from zoneinfo import ZoneInfo; print('Fuso pronto:', ZoneInfo('America/Sao_Paulo'))"
if errorlevel 1 goto erro
popd
exit /b 0
:python_ausente
echo Instale Python 3.11 ou superior em https://www.python.org/downloads/windows/
echo Habilite o launcher py ou a opcao Add python.exe to PATH. Depois tente novamente.
goto erro
:ambiente_antigo
echo A pasta .venv usa Python antigo. Renomeie essa pasta e tente novamente.
:erro
echo Nao foi possivel preparar o ambiente. Confira as mensagens acima.
popd
exit /b 1
