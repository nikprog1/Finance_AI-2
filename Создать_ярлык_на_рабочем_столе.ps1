# Создаёт ярлык Finance AI на рабочем столе
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Finance AI.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "Запуск_Finance_AI.bat"

$Shortcut.TargetPath = $BatPath
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "Bank Statement Analyzer MVP"
$Shortcut.WindowStyle = 7  # Минимизировать окно консоли
$Shortcut.Save()

Write-Host "Готово! Ярлык создан на рабочем столе: $ShortcutPath"
