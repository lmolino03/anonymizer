@echo off
echo ================================================
echo   Compilando Procesador de Informes Medicos
echo ================================================
echo.

echo [1/3] Instalando PyInstaller...
pip install pyinstaller

echo.
echo [2/3] Compilando aplicacion...
pyinstaller build_exe.spec --clean

echo.
echo [3/3] Limpiando archivos temporales...
rmdir /s /q build

echo.
echo ================================================
echo   COMPILACION COMPLETADA!
echo ================================================
echo.
echo El archivo ejecutable esta en: dist\ProcesadorInformesMedicos.exe
echo.
pause

