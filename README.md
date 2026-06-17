# Telegram Reminder Bot

Телеграм-бот напоминалка на `Python 3.11/3.12` с `aiogram 3`, `SQLAlchemy 2 async`, `Alembic`, `PostgreSQL`, `APScheduler` и Docker.

## Что умеет бот

- создавать напоминания через FSM;
- хранить их в PostgreSQL;
- показывать список активных и повторяющихся напоминаний;
- редактировать, удалять, откладывать и переносить напоминания;
- восстанавливать задачи после перезапуска;
- обрабатывать просроченные напоминания при старте.

## Структура проекта

```text
app/
  main.py
  config.py
  bot.py
  handlers/
    start.py
    reminders.py
    settings.py
  keyboards/
    callbacks.py
    main.py
    reminders.py
    settings.py
  database/
    base.py
    models.py
    session.py
  services/
    reminder_service.py
    scheduler_service.py
    user_service.py
  utils/
    datetime_parser.py
    timezone.py
  middlewares/
    db.py
alembic/
  env.py
  versions/
docker-compose.yml
Dockerfile
.env.example
requirements.txt
README.md
```

## Подготовка PostgreSQL на хосте

PostgreSQL запускается отдельно от Docker. Контейнер поднимает только бота.

Откройте `psql`:

```sql
sudo -u postgres psql
```

Создайте базу и пользователя:

```sql
CREATE DATABASE reminder_bot;
CREATE USER reminder_user WITH PASSWORD 'reminder_password';
GRANT ALL PRIVILEGES ON DATABASE reminder_bot TO reminder_user;
```

Для PostgreSQL 15+ выполните еще:

```sql
\c reminder_bot
GRANT ALL ON SCHEMA public TO reminder_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO reminder_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO reminder_user;
```

## Настройка `.env`

Скопируйте шаблон:

```bash
cp .env.example .env
```

Для Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Пример содержимого:

```env
BOT_TOKEN=1234567890:replace_me
DATABASE_URL=postgresql+asyncpg://reminder_user:reminder_password@host.docker.internal:5432/reminder_bot
DEFAULT_TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
```

Нужно заполнить:

- `BOT_TOKEN` - токен вашего Telegram-бота;
- `DATABASE_URL` - строка подключения к локальной PostgreSQL на хосте;
- `DEFAULT_TIMEZONE` - часовой пояс для новых пользователей;
- `LOG_LEVEL` - уровень логирования.

## Установка и запуск локально

1. Создайте виртуальное окружение.
2. Установите зависимости.
3. Примените миграции.
4. Запустите бота.

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

## Запуск через Docker

Перед запуском:

- PostgreSQL уже должна работать на хосте;
- `.env` должен быть заполнен;
- миграции применяются отдельно, вручную.

Запуск:

```bash
docker compose up --build -d
```

Остановка:

```bash
docker compose down
```

## Мониторинг через Uptime Kuma

Бот поддерживает два режима мониторинга без дополнительных зависимостей.

Для BotHost удобнее использовать `Push` monitor, потому что внешний HTTP-порт у бота может быть недоступен.

1. В Uptime Kuma создайте монитор типа `Push`.
2. Скопируйте выданный Push URL.
3. Вставьте его в `.env`:

```env
UPTIME_ENABLED=true
UPTIME_PUSH_URL=https://your-kuma.example.com/api/push/your-token
UPTIME_PUSH_INTERVAL_SECONDS=60
```

Бот будет сам отправлять heartbeat в Uptime Kuma после полного запуска.

Если бот запущен на VPS или в Docker и Uptime Kuma может обращаться к нему по сети, можно включить HTTP endpoint:

```env
UPTIME_ENABLED=true
UPTIME_HTTP_ENABLED=true
UPTIME_HOST=0.0.0.0
UPTIME_PORT=8080
UPTIME_PATH=/healthz
```

В этом случае создайте монитор типа `HTTP(s)`:

```text
http://<host>:8080/healthz
```

Если Uptime Kuma запущена в той же Docker-сети, можно использовать адрес:

```text
http://bot:8080/healthz
```

HTTP endpoint возвращает `200 OK`, когда бот полностью запустился, и `503 Service Unavailable` во время старта или остановки.

В `docker-compose.yml` уже добавлен:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Это нужно, чтобы контейнер видел локальную PostgreSQL на Linux.

## Миграции Alembic

Применить все миграции:

```bash
alembic upgrade head
```

Откатить последнюю:

```bash
alembic downgrade -1
```

Миграции не запускаются скрыто внутри контейнера.

## Команды

- `/start` - открыть главное меню.

## Как работает создание напоминаний

1. Бот спрашивает текст.
2. Бот спрашивает время.
3. Пользователь выбирает быстрый вариант или вводит время вручную.
4. Бот спрашивает тип повтора.
5. Бот показывает подтверждение.
6. После сохранения запись попадает в PostgreSQL и ставится в APScheduler.

Поддерживаются форматы ручного ввода:

- `25.05.2026 21:00`
- `завтра 18:00`
- `сегодня 19:30`
- `через 2 часа`
- `через 15 минут`

## Как проверить работу

1. Создайте `.env`.
2. Убедитесь, что PostgreSQL доступна по `DATABASE_URL`.
3. Выполните `alembic upgrade head`.
4. Запустите бота.
5. Отправьте `/start`.
6. Создайте напоминание через 10 минут или тестовое напоминание в настройках.
7. Дождитесь сообщения с кнопками `Выполнено`, `Отложить`, `Перенести`, `Удалить`.
8. Перезапустите бота и проверьте, что активные напоминания остались в базе.

## Замечания по реализации

- токен не хранится в коде;
- параметры базы не захардкожены;
- Docker запускает только бота;
- вся бизнес-логика вынесена в `services`;
- handlers принимают ввод и вызывают сервисы;
- доступ к напоминаниям ограничен владельцем по `user_id`;
- часовые пояса проверяются через `zoneinfo`.
