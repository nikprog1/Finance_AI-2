# Creates Finance AI desktop shortcut
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Finance AI.lnk"
$ProjectDir = "c:\Work\Finance_AI-2"
$BatPath = Join-Path $ProjectDir "Запуск_Finance_AI.bat"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $BatPath
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description = "Bank Statement Analyzer MVP"
$Shortcut.WindowStyle = 7
$Shortcut.Save()

Write-Host "Done! Shortcut: $ShortcutPath"
