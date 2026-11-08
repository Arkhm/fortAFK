@echo off
chcp 65001 >nul
setlocal
REM Trabalha na pasta deste arquivo.
cd /d "%~dp0"
if errorlevel 1 goto erro

REM Instala as dependências e a ferramenta que gera o executável.
python -m pip install --upgrade pip
if errorlevel 1 goto erro
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto erro

REM Algumas instalações do Python (Laragon, venv) não acham o Tcl/Tk sozinhas e o
REM PyInstaller deixa o tkinter de fora ("No module named 'tkinter'"). Aponta as pastas.
for /f "delims=" %%i in ('python -c "import sys,os,glob;d=sorted(glob.glob(os.path.join(sys.base_prefix,'tcl','tcl8.*')));print(d[-1] if d else '')"') do set "TCL_LIBRARY=%%i"
for /f "delims=" %%i in ('python -c "import sys,os,glob;d=sorted(glob.glob(os.path.join(sys.base_prefix,'tcl','tk8.*')));print(d[-1] if d else '')"') do set "TK_LIBRARY=%%i"
python -c "import tkinter; tkinter.Tk().destroy()"
if errorlevel 1 (
    echo.
    echo O tkinter deste Python nao funciona. Reinstale o Python pelo python.org
    echo marcando "tcl/tk and IDLE" e rode o build.bat de novo.
    goto erro
)

REM Desenha o ícone e empacota o aplicativo.
python gerar_icone.py
if errorlevel 1 goto erro
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name FortniteAFK --icon icone.ico --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 main.py
if errorlevel 1 goto erro

echo.
echo Pronto! O executável ficou em: dist\FortniteAFK.exe
echo Mova o executável para uma pasta própria.
echo As pastas imagens\ e gravacoes\ e o config.json ficam ao lado do .exe.
echo Eles são criados sozinhos na primeira execução.
pause
exit /b 0

:erro
echo.
echo Falha ao gerar o executável. Veja o erro acima e tente novamente.
pause
exit /b 1
