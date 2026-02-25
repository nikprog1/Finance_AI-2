# Публикация Finance AI на GitHub Release и GitHub Pages

Замените `REPO_OWNER/Finance_AI-2` на свой репозиторий (например `nikprog1/Finance_AI-2`).

---

## 1. Подготовка к релизу

1. **Обновите версию** в корне проекта в файле `version.py`:
   ```python
   __version__ = "1.0.0"   # замените на новую версию
   ```

2. **Соберите приложение локально** (PowerShell из корня проекта):
   ```powershell
   cd C:\Work\Finance_AI-2
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pyinstaller --clean Finance_AI.spec
   ```
   Убедитесь, что в папке `dist` появился файл `Finance_AI_<версия>.exe` (например `Finance_AI_1.0.0.exe`).

3. **Соберите установщик** в Inno Setup:
   - Откройте `Finance_AI_Setup.iss` в Inno Setup Compiler.
   - Выполните Build → Compile.
   - Установщик появится в папке `Output` (по умолчанию рядом со скриптом) с именем вида `Finance_AI_1.0.0_Setup.exe`.

4. **Проверьте артефакты**: должны быть доступны:
   - `dist\Finance_AI_<версия>.exe`
   - `Finance_AI_<версия>_Setup.exe` (результат Inno Setup).

---

## 2. GitHub Release

1. **Создайте и запушьте тег** (PowerShell):
   ```powershell
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Используйте версию, соответствующую `version.py` (например `v1.0.0`).

2. **Создайте релиз на GitHub**:
   - Откройте репозиторий: `https://github.com/REPO_OWNER/Finance_AI-2`
   - Перейдите в **Releases** → **Create a new release**.
   - **Choose a tag**: выберите созданный тег (например `v1.0.0`).
   - **Release title**: например `Finance AI 1.0.0`.
   - **Describe this release**: скопируйте блок версии из `CHANGELOG.md` или напишите краткое описание.

3. **Прикрепите файлы**:
   - Нажмите **Attach binaries by dropping them here or selecting them**.
   - Добавьте `Finance_AI_<версия>_Setup.exe` (установщик).
   - По желанию добавьте `Finance_AI_<версия>.exe` из папки `dist`.

4. Нажмите **Publish release**.

Ссылка на последнюю версию для скачивания: `https://github.com/REPO_OWNER/Finance_AI-2/releases/latest`.

---

## 3. GitHub Pages (лендинг)

1. **Включите GitHub Pages** в настройках репозитория:
   - **Settings** → **Pages**.
   - **Source**: Deploy from a branch.
   - **Branch**: `main` (или `master`), **Folder**: `/docs`.
   - Нажмите **Save**.

2. **Лендинг** уже находится в `docs/index.html`. После пуша в ветку `main` страница будет доступна по адресу:
   ```
   https://REPO_OWNER.github.io/Finance_AI-2/
   ```

3. **Обновите ссылки в `docs/index.html`**: откройте файл и замените плейсхолдер репозитория (например `REPO_OWNER/Finance_AI-2`) на свой `владелец/репозиторий`, чтобы кнопка «Скачать» и ссылка на репозиторий вели на ваш проект.

---

## 4. Краткий чеклист перед каждым релизом

- [ ] Версия обновлена в `version.py`
- [ ] В `Finance_AI_Setup.iss` совпадают `MyAppVersion` и `MyAppExeName` с версией (при необходимости отредактируйте вручную)
- [ ] Выполнены `pyinstaller --clean Finance_AI.spec` и сборка в Inno Setup
- [ ] Создан и запушен тег `v<версия>`
- [ ] В GitHub создан Release с прикреплённым установщиком
- [ ] При необходимости обновлён `CHANGELOG.md` и описание релиза
