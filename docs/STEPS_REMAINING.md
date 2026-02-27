# Оставшиеся шаги после подготовки

Инструкция по выполнению оставшихся действий для публикации Finance AI.

---

## 1. Сборка приложения

В PowerShell из корня проекта:

```powershell
cd C:\Work\Finance_AI-2
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pyinstaller --clean Finance_AI.spec
```

Проверьте: в папке `dist` должен появиться файл `Finance_AI_1.0.0.exe` (или с вашей версией из `version.py`).

---

## 2. Сборка установщика (Inno Setup)

1. Убедитесь, что `Finance_AI_<версия>.exe` находится в папке `dist`.
2. Откройте `Finance_AI_Setup.iss` в Inno Setup Compiler.
3. В секции `#define` проверьте совпадение `MyAppVersion` и `MyAppExeName` с версией в `version.py`.
4. Build → Compile.
5. Установщик появится в папке Output (рядом со скриптом): `Finance_AI_1.0.0_Setup.exe`.

---

## 3. Публикация на GitHub

```powershell
git add .
git commit -m "Подготовка к релизу 1.0.0"
git push origin main
```

---

## 4. Создание релиза

```powershell
git tag v1.0.0
git push origin v1.0.0
```

Затем на GitHub:

- Releases → Create a new release
- Choose tag: v1.0.0
- Release title: Finance AI 1.0.0
- Attach: `Finance_AI_1.0.0_Setup.exe`
- Publish release

---

## 5. Включение GitHub Pages

- Repository → Settings → Pages
- Source: Deploy from a branch
- Branch: main, Folder: /docs
- Save

Лендинг будет доступен по адресу: `https://<USER>.github.io/Finance_AI-2/`
