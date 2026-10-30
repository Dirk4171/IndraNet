@echo off
REM ===========================================================================
REM  IndraNet - Windows-Version bauen
REM
REM  Dieses Skript INSTALLIERT NICHTS und LOESCHT NICHTS.
REM  Es prueft nur die Voraussetzungen und ruft PyInstaller auf.
REM
REM  Grund: Ein Skript, das Programmcode aus dem Internet nachlaedt,
REM  Verzeichnisse loescht und eine EXE erzeugt, entspricht dem
REM  Verhaltensmuster eines Schadprogramm-Laders. Virenscanner mit
REM  Verhaltenserkennung (Avast IDP.Generic, Defender u.a.) schlagen darauf
REM  an - zu Recht, denn den Kontext koennen sie nicht kennen.
REM
REM  Die Installation der Abhaengigkeiten machen Sie deshalb einmalig
REM  selbst. Siehe unten oder BUILD.md.
REM ===========================================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   IndraNet - Windows-Version bauen
echo ============================================================
echo.

REM --- Python vorhanden? -----------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo   Python wurde nicht gefunden.
    echo.
    echo   Installieren Sie Python 3.11 oder neuer von
    echo       https://www.python.org/downloads/
    echo   und kreuzen Sie bei der Installation
    echo       "Add python.exe to PATH"
    echo   an. Danach dieses Fenster schliessen und neu starten.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   [1/3] Python %PYVER% gefunden.

REM --- Abhaengigkeiten vorhanden? --------------------------------------------
python -c "import cryptography, PyInstaller, anthropic, httpx2, socksio, pypdf" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Es fehlen noch Bibliotheken.
    echo.
    echo   Geben Sie EINMALIG diesen Befehl ein und starten Sie
    echo   dieses Skript danach erneut:
    echo.
    echo       python -m pip install -r requirements.txt pyinstaller
    echo.
    echo   ^(Das Skript installiert bewusst nicht selbst - siehe Kopf
    echo    dieser Datei und BUILD.md.^)
    echo.
    pause
    exit /b 1
)
echo   [2/3] Bibliotheken vorhanden.

REM --- Bauen -----------------------------------------------------------------
echo   [3/3] Anwendung bauen ^(dauert 1-3 Minuten^)...
echo.
python -m PyInstaller IndraNet.spec --noconfirm --clean --log-level WARN
if errorlevel 1 (
    echo.
    echo   Bau fehlgeschlagen. Bitte die Meldungen oberhalb lesen.
    pause
    exit /b 1
)

REM --- Tor neben die EXE legen, damit dist\IndraNet auch ohne Installer laeuft
if exist "tor\tor\tor.exe" (
    xcopy "tor" "dist\IndraNet\tor" /E /I /Y /Q >nul
    echo   Tor Expert Bundle aus dem Ordner "tor" mitgenommen.
)

echo.
echo ============================================================
echo   FERTIG
echo ============================================================
echo.
echo   Anwendung:  dist\IndraNet\IndraNet.exe
echo.
echo   Vor der Weitergabe empfohlen:
echo       python test_indranet.py
echo       python test_v2.py
echo.
echo   Tor: Liegt das Tor Expert Bundle im Ordner "tor" ^(tor\tor\tor.exe^),
echo   nehmen EXE und Installer es mit. Test ueber das echte Tor-Netz:
echo       python test_tor.py
echo.
echo   Installationsprogramm erzeugen:
echo     1. Inno Setup installieren  ^(https://jrsoftware.org/isdl.php^)
echo     2. installer.iss oeffnen, auf "Compile" klicken
echo     Ergebnis: Ausgabe\IndraNet-Setup-2.0.exe
echo.
echo   VIRENSCANNER
echo   Die erzeugte EXE loest bei manchen Scannern einen Fehlalarm aus.
echo   Das ist bei unsignierten PyInstaller-Programmen normal. Fuer eine
echo   Weitergabe an Redaktionen ist ein Code-Signing-Zertifikat noetig -
echo   siehe BUILD.md, Abschnitt "Virenscanner".
echo.
pause
