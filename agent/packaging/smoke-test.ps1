# Teste de fumaca do instalador: instala, confere, roda o autoteste e desinstala.
# Uso: powershell -File packaging\smoke-test.ps1 -Installer Output\PcXControl-Setup-X.Y.Z.exe
param([Parameter(Mandatory = $true)][string]$Installer)

$ErrorActionPreference = "Stop"
$RuleName = "PcX Control - agente"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$Dir = Join-Path $env:RUNNER_TEMP "pcx-smoke"
if (-not $env:RUNNER_TEMP) { $Dir = Join-Path $env:TEMP "pcx-smoke" }

function Fail([string]$Message) { Write-Host "FALHOU: $Message"; exit 1 }

if (-not (Test-Path $Installer)) { Fail "instalador nao encontrado: $Installer" }

Write-Host "Instalando em $Dir"
$p = Start-Process -FilePath $Installer -Wait -PassThru -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/TASKS=autostart", "/DIR=`"$Dir`"")
if ($p.ExitCode -ne 0) { Fail "instalador saiu com $($p.ExitCode)" }

$Exe = Join-Path $Dir "PcXControl.exe"
if (-not (Test-Path $Exe)) { Fail "PcXControl.exe nao foi instalado" }

$rule = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if (-not $rule) { Fail "regra de firewall ausente" }
if ($rule.Profile -ne "Private") { Fail "regra fora do perfil Private: $($rule.Profile)" }

$run = (Get-ItemProperty -Path $RunKey -Name PcXControl -ErrorAction SilentlyContinue).PcXControl
if ($run -ne "`"$Exe`"") { Fail "valor de inicio com o Windows inesperado: $run" }

$Out = Join-Path $env:TEMP "pcx-selftest.json"
Remove-Item $Out -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $Exe -ArgumentList @("--self-test", "`"$Out`"") -PassThru
if (-not $p.WaitForExit(60000)) { $p.Kill(); Fail "autoteste passou de 60 s" }
if (-not (Test-Path $Out)) { Fail "autoteste nao gravou o resultado" }
$result = Get-Content $Out -Raw | ConvertFrom-Json
Write-Host "Autoteste: $(Get-Content $Out -Raw)"
if (-not $result.ok) { Fail "autoteste falhou: $($result.error)" }

Write-Host "Desinstalando"
$p = Start-Process -FilePath (Join-Path $Dir "unins000.exe") -Wait -PassThru -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
if ($p.ExitCode -ne 0) { Fail "desinstalador saiu com $($p.ExitCode)" }
# O desinstalador do Inno se copia para a pasta temporaria e o original sai na hora.
$deadline = (Get-Date).AddSeconds(60)
while ((Test-Path $Exe) -and ((Get-Date) -lt $deadline)) { Start-Sleep -Milliseconds 500 }
Start-Sleep -Seconds 2

if (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue) {
    Fail "regra de firewall continua depois de desinstalar"
}
$run = (Get-ItemProperty -Path $RunKey -Name PcXControl -ErrorAction SilentlyContinue).PcXControl
if ($run) { Fail "valor de inicio com o Windows continua: $run" }
if (Test-Path $Exe) { Fail "PcXControl.exe continua depois de desinstalar" }

Write-Host "OK: instalador, firewall, inicio com o Windows, autoteste e desinstalacao"
