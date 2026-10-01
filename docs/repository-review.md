# Отчёт по ревью ShipState — 2026-10-01

Проверен исходный main `572135ed406c5260b96afaba0c433c4960eaecef`.
Работа выполнена в `chore/repo-review-fixes`. Имя и версия пакета сохранены:
`shipstate`, `0.1.0`. Теги, GitHub Releases и публикации не создавались.

## 1. Выполненные задачи и коммиты

| Коммит | Изменение | Проверка после блока на Python 3.12 |
| --- | --- | --- |
| `8855c30` | Защита согласованности версии, README-примера и реальных CLI-ожиданий | 579 passed |
| `b353727` | release-consistency на push тегов v* и проверка перед публикацией | 579 passed |
| `9e1cd22` | Полный раздел ограничений перенесён в docs/limitations.md | 579 passed |
| `a341064` | Бейджи, CONTRIBUTING, SECURITY, keywords | 579 passed |
| `09ce5de` | Детерминированный порядок имён workflow с одинаковым casefold; тесты ошибок | 584 passed |
| `d27f25e` | Документация и tests/conftest.py включены в sdist | 584 passed; затем 584 passed из sdist |
| Финальный docs-коммит | Этот отчёт и уточнения проверенных ограничений | 584 passed |

Все 550 слов исходного подробного раздела сохранены; добавлены восемь заданных
подзаголовков. Формулировка линейки уточнена до `ShipState 0.1.x`. README сокращён
со 128 до 84 строк, несмотря на добавление бейджей и ссылки для участников.
Дополнительный How it works не добавлен: существующие Usage, What it checks и
пример meshcontract уже объясняют работу без дублирования.

CI tests.yml по-прежнему запускается на push и pull_request, с Python 3.11 и 3.12.
Все checkout в изменённых workflow получают полную историю и теги. Новая job
устанавливает пакет через `python -m pip install .` и выполняет `shipstate check .`.
На обычном push/PR job пропускается: check_tag возвращает FAIL как при отсутствии
релизного тега, так и при теге на предыдущем коммите. Это пояснено в комментарии.
На PR согласованность локальных версий проверяется тестами. В publish.yml проверка
также выполняется до сборки и публикации. Существующие SHA-пины actions сохранены;
права по умолчанию contents: read, id-token: write только в publish job.

### Инвентаризация версии

Статическая версия в pyproject.toml — источник правды. __version__ остаётся
совпадающей статической константой; тест связывает её с metadata и первым
версионным заголовком CHANGELOG. CLI и оба формата вывода импортируют __version__.
Это не переводит проект на неподдерживаемую динамическую версию.

| Файл | Строка в итоговых файлах | Значение / смысл |
| --- | --- | --- |
| `pyproject.toml` | 7 | version = "0.1.0" |
| `src/shipstate/__init__.py` | 3 | __version__ = "0.1.0" |
| `src/shipstate/cli.py` | 6 | from shipstate import __version__ |
| `src/shipstate/cli.py` | 17 | parser.add_argument("--version", action="version", version=f"ShipState {__version__}") |
| `src/shipstate/cli.py` | 32 | output = render_json_error(error, __version__) if args.format == "json" else render_text_error(error, __version__) |
| `src/shipstate/cli.py` | 36 | output = render_json_result(result, __version__) if args.format == "json" else render_text_result(result, __version__) |
| `CHANGELOG.md` | 18 | ## 0.1.0 |
| `README.md` | 42 | ShipState 0.1.0 |
| `README.md` | 69 | ShipState 0.1.x supports Python projects with a static version in `pyproject.toml`. |
| `docs/limitations.md` | 5 | ShipState 0.1.x supports Python projects with a static version in pyproject.toml. |
| `.github/workflows/tests.yml` | — | Литерала версии ShipState нет; пакет устанавливается из исходников / dist. Пины v4/v5 — версии actions, 3.11/3.12 — Python. |
| `.github/workflows/publish.yml` | — | Литерала версии ShipState нет; пакет устанавливается из исходников / dist. Пины v4/v5 — версии actions, 3.11/3.12 — Python. |
| `tests/test_polish_release_readme.py` | 63, 75, 82, 87 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_readme_fence_contexts.py` | 8, 20, 31 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_readme_whitespace_quotes.py` | 14, 17, 29, 44, 50 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_readme_workflows.py` | 79, 116 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_repository_version.py` | 7, 19, 26 | Реальная версия импортируется через __version__; проверка metadata / вывода. |
| `tests/test_review_audit.py` | 25 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_warnings_cli.py` | 5, 83, 107, 149 | Реальная версия импортируется через __version__; проверка metadata / вывода. |
| `tests/test_workflow_command_boundaries.py` | 26, 42, 73, 165 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_workflow_shell_comments.py` | 36, 48, 88 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_workflow_shell_words.py` | 34, 40, 47, 53, 61, 71, 83, 102, 110, 118, 126, 142 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |
| `tests/test_workflow_uncertainty.py` | 15, 39, 41, 161, 162, 172, 194, 258 | 0.1.0 — фиксированная версия тестового проекта или примера, а не источник версии пакета. |

## 2. Замечания, которые не подтвердились

- Различия между 0.1.0 в metadata, __version__, CLI, CHANGELOG и README не было.
  `Version 0.1 supports` обозначало линейку; исправлена только неоднозначность.
  Пример meshcontract 0.2.1 и его намеренно устаревший pin 0.2.0 оставлены.
- В runtime нет shell=True, вызовов eval/exec или выполнения анализируемого shell.
  Слова eval/exec встречаются в списке неподдерживаемых shell-команд.
  Workflow YAML читается через yaml.safe_load. Запрещённый Python YAML-конструктор
  подтверждён тестом: JSON status=error, код 2, файл-маркер не создаётся.
- Git subprocess в src/shipstate/git.py использует список аргументов,
  UTF-8 с replacement и timeout=10. Удалённые команды не вызываются.
- Workflow/requirements symlink escapes, traversal и backend-path escapes уже
  блокируются. Тесты cycles, nested includes, PIP_* и unsupported shell уже были.
- dev extra, URLs, classifiers, readme, MIT license и requires-python уже были.
  В metadata добавлены только отсутствующие keywords. Ruff/mypy/black не настроены.
- Не-Git каталог, битый TOML и dynamic version возвращают код 2 и JSON status=error.
  Добавлены прямые CLI-тесты последних двух случаев и Git timeout. Ошибка JSON имеет
  существующую отдельную схему shipstate_version/status/error; менять её на findings
  было бы нарушением контракта. Ошибки build-system — FAIL/1 согласно документации.

## 3. Проблемы быстрого аудита

| Серьёзность | Файл и строка | Описание и воспроизведение | Статус / предложенное решение |
| --- | --- | --- | --- |
| LOW | src/shipstate/checks/workflows.py:522 | A.yml и a.yml получали одинаковый ключ casefold; изменение порядка iterdir меняло порядок findings. Новый тест сначала упал. | Исправлено: ключ (casefold, name); регрессионный тест проходит. Поля findings и коды выхода не изменены. |
| LOW | src/shipstate/project.py:24–28; checks/readme.py:74–85; checks/changelog.py:41–52; checks/license.py:12–16 | Основные файлы следуют внешним symlink. pyproject.toml -> ../external.toml принимается; README -> ../external.md читается и его stale pin даёт FAIL. Это чтение локального файла, не выполнение кода. | Требует решения о политике корня. Предложение: общий resolved-path guard с согласованными InputError/WARN и тестами для четырёх файлов. Сейчас задокументировано; изменение могло бы нарушить допустимые пользовательские layouts. |
| LOW | .github/workflows/publish.yml:44–55 | Два git subprocess в вспомогательном release-скрипте используют argv, но не имеют timeout. В runtime checker таймаут уже есть. | Требует решения: добавить timeout=10 и проверить timeout-путь helper. Это предложение укрепления CI, зависание не воспроизведено. |
| LOW | MANIFEST.in:1–4 | Первый sdist не содержал CHANGELOG и docs; новый version-тест падал с FileNotFoundError. Также отсутствовал conftest, и полная suite из sdist не собиралась. | Исправлено явным включением документации и conftest. Повторная сборка, twine и все 584 теста распакованного sdist проходят. |
| Ограничение | checks/workflows.py:497–516 | Exact self-pin плюс конфликтующая/условная constraint даёт WARN вместо доказанной проверки pin; это не полноценный dependency resolver. | Существующее поведение сохранено, документация уточнена. |

Локаль и текущая дата не используются для проверок. Имена файлов и множества pins
сортируются; обнаруженный конфликт сортировки исправлен. YAML mappings обходятся
в порядке исходного файла, который сохраняется Python/PyYAML. JSON status и порядок
основных checks остаются прежними.

### Что покрыто и что ещё не покрыто

Coverage измерен локально с ветвями: суммарно 90%, workflows.py 91% (округлённо).
Это не утверждение о полном покрытии всех bash/pip вариантов.

Уже покрыты continuations/quoting/comments, command boundaries, defaults shells,
opaque commands, PIP_* на разных уровнях, сохранение inline drift при PIP ambiguity,
requirements/constraints/nested includes/cycles, missing files и escapes через
workflow-файлы, workflow-каталоги, requirements и backend-path symlinks.

Непокрытые пути по coverage: некоторые отсутствующие аргументы pip options и
requirements directives, malformed jobs/steps/env, исключения чтения workflow
каталога/файла, resolve exception локального install, отдельные ошибки чтения
README/CHANGELOG/LICENSE, недоступный HEAD/status/tag-list Git и некоторые ветви
text rendering. Точные строки workflows.py: 255, 257, 263, 280, 313, 328, 330,
332, 335–336, 363, 367, 370, 443–444, 485–488, 523–524, 534, 537, 543, 605–607.

Циклы includes уже имеют тест. Дополнительно проверена цепочка 1050 разных includes:
возвращается WARN о непрочитанном reference при достижении глубины Python, без
необработанного исключения. Отдельного автоматического теста глубокой цепочки,
ресурсных лимитов YAML и гонки замены симлинка между resolve/read нет.
Политика внешних symlink основных файлов пока также не защищена отдельным тестом.

Линтеры не запускались: конфигурации и dev-зависимостей для них нет. Для отдельной
задачи можно начать с Ruff target-version="py311", lint.select=["E9", "F"] и
`ruff check src tests`; mypy/Black потребуют отдельного согласования масштаба.
Новая lint-конфигурация и runtime-зависимости не добавлены.

## 4. Что сделать вручную

- Рассмотреть и слить изменения после review. Main не изменялся.
- Решить, какая версия будет следующей. `v0.1.0` уже существует и указывает на
  `23db6264ee0d94daba72544d5e7478a4e4de1d65`; его не удалять и не передвигать.
  Самопроверка текущей ветки с version=0.1.0 объективно не может стать PASS без
  отдельного изменения release metadata либо изменения существующего тега.
- Проверить включение GitHub private vulnerability reporting. Его настройка
  и наличие кнопки Report a vulnerability не проверены доступным API.
- Проверить PyPI Trusted Publisher и environment pypi / required reviewers.
  Состояние этих настроек не проверено и не изменялось.
- После реальной публикации изменить “PyPI releases are not available yet”.
  Сейчас фраза сохранена. GitHub API на момент проверки возвращает пустой список
  Releases; факт отсутствия пакета на PyPI принят из задания, отдельно не проверялся.

После слияния и выбора **новой неиспользованной** версии, выполнения checklist из
CONTRIBUTING и commit обновлённых pyproject/__version__/README/CHANGELOG:

```sh
git switch main
git pull --ff-only
python -m pip install -e ".[dev]"
python -m pytest
python -m pip install build twine
# Запускайте сборку с чистым dist/, чтобы не проверить старые архивы.
python -m build
python -m twine check dist/*
VERSION=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
# Остановитесь, если v$VERSION уже существует: не используйте -f.
git tag -a "v$VERSION" -m "ShipState v$VERSION"
shipstate check .
shipstate check . --format json
# Продолжайте только если обе проверки дали exit code 0.
git push origin main
git push origin "v$VERSION"
# Дождитесь зелёного Tests, включая release-consistency.
# Отдельное решение о релизе: эта команда запускает publish.yml / попытку PyPI publish.
gh release create "v$VERSION" --verify-tag --title "ShipState v$VERSION" --generate-notes
```

Эти команды не выполнялись. Значение VERSION здесь читается из metadata;
в текущем состоянии оно 0.1.0, и tag-команда правильно откажется заменять старый тег.

## 5. Финальные результаты

| Проверка | Результат |
| --- | --- |
| Базовая suite, Python 3.11.16 и 3.12.14 | 577 passed на каждой версии |
| Итоговая suite, Python 3.11.16 и 3.12.14 | 584 passed на каждой версии |
| GitHub Actions Tests на d27f25e | Python 3.11 SUCCESS, Python 3.12 SUCCESS; release-consistency SKIPPED для branch push |
| sdist + wheel | python -m build PASS |
| twine check dist/* | Оба архива PASSED |
| Чистая установка wheel и sdist | --version 0.1.0; зависимости совместимы |
| Все тесты из распакованного sdist с установленным sdist | 584 passed |
| Git diff --check | PASS |
| Самопроверка, text и JSON | exit code 1 / status=fail; единственный FAIL — tag_commit_mismatch для существующего v0.1.0 |
| Остальные findings самопроверки | PASS или ожидаемые WARN локальных/непроверяемых workflow installs |
| Публичный CLI / JSON контракт | Сохранён; изменён только недетерминированный порядок при конфликте регистра имён workflow |

Критерий полного PASS самопроверки остаётся открытым только из-за существующего
релизного тега на другом коммите. Замалчивать или превращать этот FAIL в WARN нельзя:
это нарушило бы назначение инструмента и заданный контракт.
