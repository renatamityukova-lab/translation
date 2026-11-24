# Transtalion

Сервис перевода идентификаторов 1С в стиле `CamelCase` на английский язык
в формате `snake_case` для учётных систем.

Пример: `ДоговорыКонтрагентов` → `partner_contract`.

Полная постановка задачи — в [`TASK.md`](TASK.md).

> **Где лежит окружение.** Виртуальное окружение проекта — `.venv` в корне рабочей
> папки (`ПроектVSC/.venv`), рядом с каталогом `translation`, а не внутри него.
> В git оно не попадает и пересоздаётся командами из раздела «Установка».

## Правила результата

- `lower_snake_case`;
- единственное число для всех слов;
- предлоги отбрасываются;
- общепринятая терминология учётных систем / ERP.

## Структура проекта

```
ПроектVSC/
├── .venv/              # виртуальное окружение проекта (не коммитится)
├── .gitignore          # общие исключения для git
└── translation/
    ├── api/            # эндпоинты (FastAPI-роутеры, Pydantic-схемы)
    ├── services/       # бизнес-логика: оркестрация перевода, нормализация ответа
    ├── llm/            # клиент LLM API, промпты, ошибки
    ├── cache/          # кеш переводов (реализован memory; file/redis заявлены)
    ├── config/         # конфигурация (config.yaml, settings.py, logging_config.py)
    ├── tests/          # тесты (pytest)
    ├── screenshot/     # скриншоты проверок (Postman и логи)
    ├── main.py         # точка входа (FastAPI-приложение)
    ├── requirements.txt
    ├── pytest.ini      # настройки pytest (testpaths = tests)
    ├── .env            # локальные настройки и API-ключ (не коммитится)
    ├── .env.example    # шаблон переменных окружения
    ├── TASK.md         # постановка задачи
    ├── test_report.md  # отчёт о тестировании
    ├── test_checklist.md  # чек-лист проверок
    └── README.md
```

## Требования

- Python 3.11+ (проверено на 3.11.3);
- доступ к корпоративному LLM-шлюзу `https://llm.enplus.group/v1` и API-ключ к нему;
- Windows (`cmd`) — команды ниже даны для него. В bash/zsh замените
  `..\.venv\Scripts\...` на `../.venv/bin/...`, а `copy` — на `cp`.

## Установка

Все команды — из **корня проекта** (`ПроектVSC`), где лежит каталог `translation`.

1. Создать виртуальное окружение в корне проекта:

```cmd
python -m venv .venv
```

2. Активировать его:

```cmd
.venv\Scripts\activate
```

3. Установить зависимости:

```cmd
pip install -r translation\requirements.txt
```

4. Создать файл локальных настроек:

```cmd
copy translation\.env.example translation\.env
```

Если `translation\.env` уже существует, шаг 4 пропустите: `copy` спросит
подтверждение перезаписи, и текущий ключ будет потерян.

5. Открыть `translation\.env` в редакторе и заменить `OPENAI_API_KEY=your_api_key_here`
   на реальный ключ. Без ключа сервис запустится, `/health` будет отвечать `200`,
   а `/chat` вернёт `503`.

Проверка установки (из корня проекта):

```cmd
.venv\Scripts\python.exe -c "import fastapi, uvicorn, httpx, pydantic, yaml, dotenv; print('dependencies OK')"
```

> В этом репозитории `.venv` уже создано и настроено, поэтому шаги 1–5 нужны только
> на новой машине или после удаления окружения.

## Запуск

Из корня проекта перейдите в каталог `translation` — это важно: конфигурация и логи
читаются относительно текущего каталога.

Запуск одной командой — `python main.py` (порт `8000` и автоперезагрузка заданы
в [`main.py`](main.py:196)). Окружение нужно активировать один раз на терминал:

```cmd
cd translation
..\.venv\Scripts\activate
python main.py
```

Тот же запуск с явными параметрами:

```cmd
cd translation
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Если `8000` занят (`WinError 10013` или `10048`), укажите другой порт в варианте
с `uvicorn`: `--port 8001`. У `python main.py` порт зашит в коде.

Остановка — `Ctrl+C` в терминале с сервисом. Если терминал потерян:

```cmd
netstat -ano | findstr ":8000"
taskkill /PID <PID> /T /F
```

## Проверка после запуска

В отдельном терминале:

```cmd
curl.exe -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/health
```

Ожидается `{"status":"ok"}` и `HTTP 200`. Интерактивная документация —
`http://127.0.0.1:8000/docs`.

Проверка перевода (кириллица передаётся `\u`-последовательностями, чтобы не зависеть
от кодировки консоли Windows):

```cmd
curl.exe -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"\u0414\u043e\u0433\u043e\u0432\u043e\u0440\u044b\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442\u043e\u0432\"}"
```

Ожидается `{"message":"ДоговорыКонтрагентов","translated":"partner_contract"}` и
`HTTP 200`. Повторный запрос того же идентификатора обслуживается из кеша и выполняется
заметно быстрее.

В Postman: `POST http://127.0.0.1:8000/chat`, вкладка **Body** → `raw` → **JSON**:

```json
{ "message": "ДоговорыКонтрагентов" }
```

Быстрая проверка импорта без запуска сервера (из каталога `translation`):

```cmd
..\.venv\Scripts\python.exe -c "from main import app; print(app.title)"
```

## Тесты

```cmd
cd translation
..\.venv\Scripts\python.exe -m pytest -q
```

Ожидаемый результат — `75 passed`. Запускать нужно из каталога `translation`:
в [`pytest.ini`](pytest.ini) задан `testpaths = tests`, а конфигурация и логи
читаются относительно текущего каталога.

Полезные варианты: `-v` (подробно по каждому тесту), `-k normalizer` (по имени),
`tests/test_api_errors.py` (один файл), `--lf` (только упавшие в прошлый раз).

Реальный API-ключ для тестов не требуется: вызовы LLM подменяются моками
([`tests/test_llm_client.py`](tests/test_llm_client.py) — `httpx.Client`,
[`tests/test_api_errors.py`](tests/test_api_errors.py) — `services.translator.complete`).

## API

### `POST /chat`

Перевод идентификатора 1С в `lower_snake_case`.

Запрос:

```json
{ "message": "ДоговорыКонтрагентов" }
```

Ответ `200`:

```json
{ "message": "ДоговорыКонтрагентов", "translated": "partner_contract" }
```

Валидация (ответ `400`): `message` обязательно, должно быть строкой, непустым после обрезки
пробелов, длиной не более 1000 символов; лишние поля запрещены. В теле ответа — `detail`
и `errors[{field, message}]`.

Коды ошибок:

| Код | Когда |
|---|---|
| `400` | некорректный запрос (валидация, битый JSON) |
| `502` | провайдер LLM отклонил запрос или вернул невалидный ответ |
| `503` | LLM не настроена (нет ключа) или временно недоступна |
| `500` | непредвиденная ошибка (без внутренних деталей) |

Ретраи выполняются только для временных ошибок: таймаут, сетевая ошибка, HTTP 429 и 5xx.
Интерактивная документация — `http://127.0.0.1:8000/docs`.

Как обрабатывается запрос:

```
POST /chat
  → services.translator.translate_identifier()
  → llm.prompts.build_user_prompt()              # идентификатор + правила snake_case
  → llm.client.complete(SYSTEM_PROMPT, prompt)   # вызов chat/completions
  → services.normalizer.normalize_snake_case()   # чистка ответа → partner_contract
```

Системный промпт: «Ты — полезный ассистент, профессиональный переводчик терминов учетных
систем. Отвечай кратко и по существу.» Пользовательский запрос формируется в
[`llm/prompts.py`](llm/prompts.py); настройки — в [`config/settings.py`](config/settings.py).

## Конфигурация

Параметры приложения, LLM, кеша и правил перевода — в [`config/config.yaml`](config/config.yaml).
API-ключ LLM передаётся через переменную окружения, имя которой задано в `llm.api_key_env`
(по умолчанию `OPENAI_API_KEY`); в файл конфигурации ключ не записывается.

Используется корпоративный OpenAI-совместимый шлюз:

| Параметр | Значение |
|---|---|
| `LLM_BASE_URL` | `https://llm.enplus.group/v1` |
| `LLM_MODEL` | `gpt-oss-120b` (основная) |
| `LLM_FALLBACK_MODEL` | `MiniMax-M2.7` (резервная) |
| `LLM_TRUST_ENV` | `true` (`false` — не использовать прокси из окружения) |

Клиент — [`llm/client.py`](llm/client.py) на `httpx` (OpenAI SDK не требуется).
Проверка доступности без ключа: `curl.exe https://llm.enplus.group/v1/models` → `401`.

Кеш переводов — in-memory словарь с TTL ([`cache/ttl_cache.py`](cache/ttl_cache.py)):
`CACHE_ENABLED`, `CACHE_BACKEND` (`memory`; `file`/`redis` пока не реализованы),
`CACHE_TTL_SECONDS` (86400), `CACHE_MAX_SIZE` (10000).

## Логирование

Настройка — [`config/logging_config.py`](config/logging_config.py), вызывается один раз
при импорте [`main.py`](main.py). Логи пишутся **в консоль и в файл** с ротацией
(`RotatingFileHandler`, UTF-8): `logs/transtalion.log`, 5 МБ × 5 архивных файлов.
Консольный поток при настройке переключается на UTF-8, поэтому символы `→`/`←`
и кириллица не вызывают `UnicodeEncodeError` в консоли Windows.

Параметры (`config/config.yaml`, секция `logging`, переопределяются из `.env`):

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `LOG_ENABLED` | `true` | включить логирование |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `LOG_CONSOLE` | `true` | вывод в консоль |
| `LOG_FILE` | `true` | вывод в файл |
| `LOG_FILE_PATH` | `logs/transtalion.log` | путь к файлу (от каталога `translation/`) |
| `LOG_MAX_BYTES` | `5000000` | порог ротации файла |
| `LOG_BACKUP_COUNT` | `5` | число архивных файлов |
| `LOG_FORMAT` | `%(asctime)s \| %(levelname)-8s \| %(request_id)s \| %(name)s \| %(message)s` | формат записи |

Формат записи:

```
2026-11-24 11:14:23 | INFO     | ef83ea92 | services.translator | Промпт для LLM (685 символов):
2026-11-24 11:14:23 | INFO     | ef83ea92 | services.translator | Ответ LLM (16 символов): 'partner_contract'
```

Каждому HTTP-запросу присваивается `request_id` (8 символов): он попадает в контекст
(`contextvars`) и во все записи по цепочке API → services → LLM, а также в заголовок
ответа `X-Request-ID` — удобно сопоставлять записи одного запроса.

Что логируется на каждом этапе:

- **HTTP** (`main.py`, middleware): начало запроса (`→ METHOD /path`, клиент), завершение
  (`← METHOD /path — статус за N с`), необработанные ошибки со стеком;
- **API** ([`api/routes.py`](api/routes.py)): входное сообщение и длина, результат перевода
  и время, ошибка перевода с типом исключения;
- **Бизнес-логика** ([`services/translator.py`](services/translator.py)): старт перевода,
  попадание/промах кеша, полный текст промпта, полный ответ модели, результат нормализации,
  сохранение в кеш, ошибки пустого/невалидного ответа;
- **LLM-клиент** ([`llm/client.py`](llm/client.py)): параметры запроса (модель, URL,
  temperature, размер промпта), номер попытки, HTTP-статус и время ответа, содержимое ответа
  на уровне `DEBUG`, причины повторов, переключение на резервную модель, итоговые ошибки.

API-ключ в логи не попадает. Подробные логи сторонних библиотек (`httpx`, `httpcore`,
`urllib3`) приглушены до `WARNING`.

## Статус

- [x] Постановка задачи и структура проекта
- [x] Окружение: `.venv`, зависимости, `.env`
- [x] Конфигурация: `config/settings.py` (YAML + `.env`)
- [x] Клиент LLM: `llm/prompts.py`, `llm/client.py` (timeout, retry, fallback-модель)
- [x] Бизнес-логика: `services/translator.py` + постобработка `services/normalizer.py`
- [x] API-слой: `POST /chat` и валидация
- [x] Подключение к корпоративному LLM проверено (`gpt-oss-120b`, `200 /v1/models`, `partner_contract`)
- [x] Fallback-модель проверена вживую (`MiniMax-M2.7`), очистка reasoning-блоков в ответе
- [x] Кеш переводов: in-memory `TTLCache` (TTL, `max_size`), подключён к `services`
- [x] Обработка ошибок: `400/502/503/500`, ретраи только для временных сбоев
- [x] Логирование: консоль + файл с ротацией, `request_id`, все этапы обработки
- [x] Тесты: нормализация (32), кеш (11), API-ошибки (15), клиент LLM (11),
      логирование (6) — 75 passed
