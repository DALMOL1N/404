@echo off
setlocal
pushd "%~dp0"
set "PYTHONUTF8=1"
call PREPARAR_WINDOWS.bat
if errorlevel 1 goto falha
:menu
echo.
echo SGDI v5 - escolha o modo de execucao
echo 1 - Demonstracao da Sprint 5 com dados ficticios e login
echo 2 - Sistema local sem login
echo 3 - Sistema autenticado com senha propria
echo 4 - Executar todos os testes
echo 0 - Sair
choice /c 12340 /n /m "Opcao: "
if errorlevel 5 goto fim
if errorlevel 4 goto testes
if errorlevel 3 goto autenticado
if errorlevel 2 goto local
goto demonstracao
:demonstracao
echo Abra http://127.0.0.1:5056
echo Conta ficticia: admin@404.local / DemoSprint5!2026
echo Para encerrar, use Ctrl+C nesta janela.
".venv\Scripts\python.exe" demo_sprint5.py
goto resultado
:local
echo Abra http://127.0.0.1:5050
echo Modo sem login: autoria registrada como operacao local.
echo Para encerrar, use Ctrl+C nesta janela.
".venv\Scripts\python.exe" app.py
goto resultado
:autenticado
echo Abra http://127.0.0.1:5056
echo Na primeira execucao, escolha a senha do administrador.
echo Para encerrar, use Ctrl+C nesta janela.
".venv\Scripts\python.exe" iniciar_autenticado.py
goto resultado
:testes
".venv\Scripts\python.exe" -m unittest discover -s tests -v
:resultado
if errorlevel 1 echo A execucao terminou com erro. Confira as mensagens acima.
pause
goto menu
:falha
pause
:fim
popd
exit /b
