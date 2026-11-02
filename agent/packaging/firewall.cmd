@echo off
rem Regra de firewall do PcX Control: so rede Privada, so a rede local, so este programa.
rem Uso: firewall.cmd add "C:\caminho\PcXControl.exe"   ou   firewall.cmd remove
set RULE=PcX Control - agente
netsh advfirewall firewall delete rule name="%RULE%" >nul 2>&1
if /i "%~1"=="remove" exit /b 0
if /i not "%~1"=="add" exit /b 2
netsh advfirewall firewall add rule name="%RULE%" dir=in action=allow protocol=TCP profile=private remoteip=localsubnet program="%~2"
exit /b %ERRORLEVEL%
