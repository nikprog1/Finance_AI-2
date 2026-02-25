; Inno Setup script for Finance AI 1.0.0
; Откройте этот файл в Inno Setup и нажмите Build

; --- Базовые параметры приложения ---

#define MyAppName "Finance AI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Finance AI"
#define MyAppExeName "Finance_AI_1.0.0.exe"

; PyInstaller собрал one-file exe в папку dist
#define MyAppSourceDir "dist"

[Setup]
AppId={{F4F1E3B2-5B7A-4C1D-9F12-FA1E0D0A1C01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=Finance_AI_{#MyAppVersion}_Setup
Compression=lzma
SolidCompression=yes
DisableDirPage=no
DisableProgramGroupPage=no
; Имя в «Программы и компоненты» для удаления
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"

[Files]
; Основной exe, собранный PyInstaller (one-file)
Source: "{#MyAppSourceDir}\\{#MyAppExeName}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
; Ярлык запуска программы
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{commondesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

; Ярлык деинсталляции
Name: "{group}\\Удалить {#MyAppName}"; Filename: "{uninstallexe}"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные задачи:"; Flags: unchecked

[Run]
; Автоматический запуск программы после установки (опционально)
Filename: "{app}\\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

; --- Uninstall ---
; При удалении программы через «Удалить Finance AI» или «Программы и компоненты»
; удаляются файлы приложения и каталог установки.
[UninstallDelete]
Type: filesandordirs; Name: "{app}"
