@echo off
setlocal

set SRCDIR=..\src
set OUTDIR=..\bin
set OBJDIR=..\src\o

if not exist %OUTDIR% mkdir %OUTDIR%
if not exist %OBJDIR% mkdir %OBJDIR%

set INCLUDES=/I "." /I "%SRCDIR%\h"
set DEFINES=/D "WIN32" /D "NDEBUG" /D "_CONSOLE" /D "_MBCS" /D "_WINDOWS" /D "ZLIB_DLL" /D "HAVE_STDBOOL_H" /D "_CRT_SECURE_NO_WARNINGS" /D "_WINSOCK_DEPRECATED_NO_WARNINGS"
set CFLAGS=/nologo /W3 /O2 %INCLUDES% %DEFINES%
set LIBS=kernel32.lib user32.lib advapi32.lib gdi32.lib winspool.lib comdlg32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib
set LFLAGS=/nologo /subsystem:console /libpath:"." /out:"%OUTDIR%\1stMud.exe" %LIBS%

echo Compiling 1stMud...
cl.exe %CFLAGS% /Fo"%OBJDIR%\\" %SRCDIR%\*.c /link %LFLAGS%

if %errorlevel% neq 0 (
    echo.
    echo *** Build FAILED ***
    exit /b 1
)

echo.
echo Build successful: %OUTDIR%\1stMud.exe

if not exist %OUTDIR%\zlib1.dll (
    copy zlib1.dll %OUTDIR%\ >nul
    echo Copied zlib1.dll to %OUTDIR%
)

echo.
echo To run: cd ..\area  then  ..\bin\1stMud.exe 4000
endlocal
