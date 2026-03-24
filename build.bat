@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  AnimeTracker Build Script
REM  產生獨立執行的 AnimeTracker.exe 於 dist\AnimeTracker\ 資料夾
REM ─────────────────────────────────────────────────────────────────────────────

echo [1/3] 確認虛擬環境...
if not exist "venv\Scripts\activate.bat" (
    echo 找不到虛擬環境，請先執行：
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo   pip install pyinstaller
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo [2/3] 確認 PyInstaller 已安裝...
python -m pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo 安裝 PyInstaller...
    pip install pyinstaller
)

echo [3/3] 編譯 AnimeTracker...
venv\Scripts\pyinstaller.exe AnimeTracker.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ==============================
    echo  編譯失敗！請檢查上方錯誤訊息
    echo ==============================
    pause
    exit /b 1
)

echo.
echo ======================================
echo  編譯完成！
echo  執行檔位置：dist\AnimeTracker\AnimeTracker.exe
echo ======================================
pause
