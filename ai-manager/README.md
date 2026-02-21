# ChatBot для инвестплатформы (может быть приспособлен для любой задачи, где требуется предварительная консультация по продукту и затем жесткий сбор данных лида)
~~~код доступен в отдельном репо
~~~

Backend-сервис AI-консультанта на FastAPI + PostgreSQL (pgvector).

## Что внутри

- Chat API для сценарного диалога
- Сбор и хранение лидов
- Админ-панель для контента, FAQ, заявок, диалогов, сервисных настроек
- RAG база знаний (документы + чанки + векторный поиск)
- Встраиваемый виджет (/widget/frame, /widget/loader.js)

## Стек

- Python 3.11, FastAPI, Uvicorn
- SQLAlchemy (async) + asyncpg
- PostgreSQL 16 + pgvector
- Docker Compose
- Caddy (reverse proxy)

## Структура проекта

~~~text
root
  backend/
    app/
      main.py              # FastAPI app и чат-эндпоинты
      admin/               # admin API + HTML pages
      widget/              # iframe + embeddable loader.js
      repo/                # доступ к данным
      services/            # диалог, telegram/email, RAG
      core/config.py       # настройки env
    Dockerfile
    requirements.txt
  db/init/                 # SQL инициализация БД
  docker-compose.yml
  .env
  .env.example
  Caddyfile                # конфиг reverse proxy (если используется)
~~~

## Быстрый запуск

1. Скопировать env файл:

~~~bash
cp .env.example .env
~~~

2. Заполнить минимум в .env:

- DATABASE_URL
- ADMIN_API_KEY
- опционально: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- для RAG/LLM: YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER_ID

3. Поднять сервисы:

~~~bash
docker compose up -d --build
~~~

4. Проверить здоровье API:

~~~bash
curl http://localhost:8000/health
~~~

## Основные эндпоинты

- GET / - информация о сервисе.
- GET /health - healthcheck.
- POST /chat/start - старт диалога.
- POST /chat/restart - перезапуск сессии.
- POST /chat/consent - подтверждение согласий.
- POST /chat/message - сообщение пользователя.

Админ:

- GET /admin/ui - веб-админка (Basic Auth).
- GET/PUT/PATCH /admin/content
- GET/PUT /admin/service
- GET/POST/PUT/DELETE /admin/kb
- GET /admin/leads, GET /admin/sessions
- GET /admin/logs
- GET/POST/PATCH/DELETE /admin/rag...

Виджет:

- GET /widget/frame
- GET /widget/loader.js

## CORS

CORS настроен в backend/app/main.py и разрешает материнские домены

Чтобы добавить домен:

- Добавить домен в список allow_origins в backend/app/main.py.
- Перезапустить backend (docker compose restart backend).

## Reverse proxy (Caddy)

Сервис caddy включён в docker-compose.yml и требует файл Caddyfile в корне проекта.

Если нужно терминировать HTTPS или пробросить /admin и /widget как есть, достаточно reverse_proxy.

## Аутентификация админки

Два варианта:

- Header: X-Admin-Key: <ADMIN_API_KEY>
- Basic Auth: admin:<ADMIN_API_KEY>

## Пример встраивания виджета

~~~html
<script
  src=https://YOUR-DOMAIN/widget/loader.js
  data-base=https://YOUR-DOMAIN
  data-source=site_widget
></script>
~~~

## Логи

- в контейнере: app.log
- на хосте: ./logs/app.log
- endpoint: /admin/logs (секреты маскируются)

## RAG

RAG-таблицы создаются SQL-скриптами в db/init/.
Для индексации и поиска нужно настроить ключи Yandex Cloud в сервисных настройках (/admin/ui/service) или через env.

## Полезные команды

~~~bash
# статус контейнеров
docker compose ps

# логи backend
docker compose logs -f backend

# перезапуск backend
docker compose restart backend
~~~

## Инструкция по использованию админки

Админка доступна по адресу /admin/ui и защищена Basic Auth (логин admin, пароль = ADMIN_API_KEY).

Разделы:

- Главная: обзор и быстрые переходы.
- Служебные: настройки интеграций (Telegram, LLM, Email) и сервисные параметры, лог-файлы сервиса.
- Тексты: управляемые тексты и дисклеймеры для диалога.
- FAQ: база вопросов и ответов, используется в диалогах. Вся база faq добавляется к каждому запросу к LLM. Любой вопрос/ответ можно отключить - убрать из запроса.
- RAG (База знаний): загрузка документов, индексация. Сервис RAG можно отдельно включить/отключать, найденные чанки будут добавляться (обогащать) в контекст наряду с базой faq.
- Заявки: список лидов, статусы, детали. Отображаются заявки, оставленные пользователями, полностью прошедшими процесс заполнения (эти данные дублируются в ТГ и email). Срок хранения 96 часов.
- Диалоги: сессии чата и история сообщений. История всех диалогов бота со пользователями (личные данные маскированы), срок хранения 90 дней, настраивается в разделе Служебные.
- Тест виджета: проверка виджета в браузере. Так же есть код для размещения "вызова" на сайте.

Рекомендуемый порядок настройки:

1. Служебные: заполнить ключи и настройки сервисов.
2. Тексты: отредактировать приветствия и дисклеймеры.
3. FAQ: добавить базовые вопросы и ответы. 
4. RAG: загрузить документы и проверить индексацию. 
5. Тест виджета: убедиться, что диалог работает.

API доступ:

- Для API используйте заголовок X-Admin-Key: <ADMIN_API_KEY>.

Примеры:

~~~bash
curl -H X-Admin-Key: <ADMIN_API_KEY> http://localhost:8000/admin/content
curl -H X-Admin-Key: <ADMIN_API_KEY> http://localhost:8000/admin/leads
~~~

Логи:

- Админ-лог endpoint: /admin/logs (секреты маскируются).
