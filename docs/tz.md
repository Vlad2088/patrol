# Патруль — ТЗ и архитектура (v1)

Система контроля обходов охраны по QR-точкам.
Версия: 1.0 (MVP). Дата: 2026-09-11.

---

## 1. Цели и границы

### Цели
- Диспетчер планирует обходы объектов и следит за их выполнением в веб-кабинете.
- Охранник проходит маршрут, сканируя QR-коды точек, в Android-приложении.
- Приложение работает офлайн; отметки синхронизируются при появлении сети.
- Сервер валидирует обходы и автоматически фиксирует нарушения.

### Границы (в MVP)
Входят: объекты/маршруты/точки, QR-генерация (PDF-наклейки), расписания обходов,
смены, офлайн-режим Android, валидация, автофиксация нарушений, мониторинг
статусов, уведомления в кабинете, отчёты CSV/Excel, аудит диспетчера.

Вне MVP (отложено): онлайн-карта, GPS, геозоны, чат, эскалация,
SMS/email/Telegram/push, интеграции (1С, СКУД, видео), iOS, отмена/переназначение
обходов диспетчером.

### Расчётная нагрузка
от 10 объектов, от 24 обходов/сутки, до 200 охранников, до 1000 обходов/сутки
с запасом.

---

## 2. Роли и права

| Роль | Интерфейс | Права |
|---|---|---|
| Диспетчер | Веб-кабинет | Полные: объекты, маршруты, точки, QR, расписания, смены, охранники, мониторинг, отчёты, уведомления, аудит (только чтение журнала) |
| Охранник | Android | Логин, список своих смен и обходов, прохождение обхода, история своих отметок. Без управления чем-либо |

RBAC на сервере: role в JWT, зависимости FastAPI require_role("dispatcher").
Охранник не имеет доступа к API кабинета; диспетчер не имеет мобильных эндпоинтов.

---

## 3. Сущности и схема БД (ER)

```
User 1 ── * Shift (guard)          Shift * ── 1 Object (через object_id)
Object 1 ── * Route                Route 1 ── * Checkpoint (order_num 1..30)
Route 1 ── * PatrolSchedule        PatrolSchedule ──> Route (+object через маршрут)
Patrol 1 ── * ScanEvent            Patrol * ── 1 Object (обход на объект)
Patrol 1 ── * Violation            AuditLog * ── 1 User (dispatcher)
```

### Таблицы (PostgreSQL 16)

- **users**: id, login, password_hash (argon2), full_name, role
  ('dispatcher' | 'guard'), is_active, created_at
- **objects**: id, name, address, is_active
- **routes**: id, object_id FK, name, is_active
- **checkpoints**: id, route_id FK, order_num (int, уникально в маршруте),
  code (уникально глобально, формат `R{route_id}-{order:03d}`), name
- **patrol_schedules**: id, route_id FK, kind ('once' | 'daily' | 'weekly' |
  'shift'), weekdays (int[] для weekly), window_start (time), window_end (time),
  shift_kind ('day'|'night', для kind=shift), is_active
- **shifts**: id, object_id FK, guard_id FK users, starts_at, ends_at (ts)
- **patrols**: id, object_id FK, route_id FK, schedule_id FK nullable,
  patrol_date (date), window_start, window_end (ts — конкретные границы),
  status ('planned' | 'in_progress' | 'completed' | 'missed' | 'partial'),
  started_by (FK users nullable), started_at, finished_at, checkpoints_total,
  checkpoints_scanned
- **scan_events**: id, patrol_id FK, checkpoint_id FK, guard_id FK,
  scanned_at (ts — время устройства), synced_at (ts — время сервера),
  client_uuid (уникальный id скана на устройстве, идемпотентность)
- **violations**: id, patrol_id FK, kind ('missed_patrol' | 'missed_points'),
  details (jsonb: список непройденных точек и пр.), detected_at
- **audit_logs**: id, user_id FK, action, entity, entity_id, payload jsonb,
  created_at

Индексы: patrols(object_id, patrol_date), scan_events(patrol_id),
checkpoints(route_id, order_num) unique, checkpoints(code) unique,
shifts(object_id, starts_at).

### Правила порождения обходов
Материализация: обходы создаёт фоновая задача (раз в минуту) из расписаний на
горизонт +24 ч: kind=once → на дату; daily → каждый день; weekly → по дням
недели; shift → на каждую смену дня/ночи объекта. Окно обхода = окно расписания
на конкретную дату (ts).

---

## 4. API (контракт)

База: `/api/v1`. Auth: JWT Bearer (access 30 мин + refresh 30 дней).
Ошибки: 401 не авторизован, 403 роль не та, 404 нет сущности, 409 конфликт
бизнес-правила, 422 валидация pydantic, 500 сервер. Тело ошибки:
`{"detail": "строка", "code": "machine_code"}`.

### Auth
- POST /auth/login {login, password} → {access, refresh, role, full_name}
- POST /auth/refresh {refresh} → {access}

### Кабинет (dispatcher)
- GET /objects, POST /objects, PATCH /objects/{id}, DELETE (soft)
- GET /routes?object_id=, POST /routes, PATCH, DELETE
- GET /routes/{id}/checkpoints, POST /routes/{id}/checkpoints (массово),
  PATCH /checkpoints/{id}, DELETE
- GET /routes/{id}/qr.pdf → PDF со всеми QR наклейками маршрута
- GET /schedules?route_id=, POST, PATCH, DELETE
- GET /shifts?object_id=&date=, POST, PATCH, DELETE
- GET /guards, POST /guards (создание охранника), PATCH, DELETE
- GET /patrols?date=&object_id=&status= (мониторинг), GET /patrols/{id}
- GET /dashboard?date= → сводка: по объектам статусы, счётчики нарушений
- GET /notifications?unread=true → список нарушений за период, POST /notifications/read
- GET /reports/patrols.csv|xlsx?from=&to=&object_id=&guard_id=
- GET /reports/violations.csv|xlsx?from=&to=
- GET /audit?user_id=&from=&to=

### Мобильное (guard)
- GET /mobile/sync → {routes, checkpoints, patrols(плановые на сегодня+активные),
  shifts(мои)} — полный пакет для офлайн
- POST /mobile/patrols/{id}/start → Patrol(in_progress, started_by)
- POST /mobile/scans (batch) [{client_uuid, checkpoint_code, scanned_at}] →
  по каждому: accepted | duplicate | wrong_checkpoint | out_of_order |
  patrol_closed (серверная валидация, см. раздел 6)
- POST /mobile/patrols/{id}/finish → completed/partial
- GET /mobile/history?from=&to= → мои обходы со статусами

---

## 5. Сценарии

### Диспетчер
1. Создаёт объект → маршрут → точки (10–30) → скачивает qr.pdf, клеит наклейки.
2. Настраивает расписание (например: daily, окно 22:00–23:00).
3. Назначает смены: объект + охранник + интервал.
4. Мониторинг: дашборд на дату — по объектам статус обходов (запланирован,
   идёт, завершён, просрочен, частично), счётчик нарушений.
5. Уведомления: колокольчик — список нарушений (пропуск/непройденные точки),
   прочитанные скрываются.
6. Отчёты: выгрузка CSV/Excel по обходам (смена/объект/охранник/статус/точки)
   и по нарушениям.
7. Аудит: журнал — кто из диспетчеров что создал/изменил/удалил и когда.

### Охранник
1. Логин в приложении (логин/пароль) → синк данных (маршруты, точки, смены,
   плановые обходы).
2. Смена началась → на экране объект(ы) смены и обходы с окнами.
3. В окне: «Начать обход» → приложение валидирует офлайн: следующая ожидаемая
   точка = первая непройденная по order_num.
4. Сканирует QR: код точки → офлайн-проверка (та точка? по порядку?) → отметка
   сохраняется в Room с client_uuid; на сервер — в очереди на отправку.
5. Вне сети очередь копится; при появлении сети — батч POST /mobile/scans.
6. Последняя точка → «Завершить обход» (или автоматически) → статус на сервере.
7. История: список своих обходов с датами, статусами, % точек.

---

## 6. Логика валидации обхода и нарушений

### Валидация отметки
Офлайн (устройство): точка принадлежит маршруту текущего обхода; сканируемая
точка = следующая по порядку (первая непройденная). Подсказки мгновенно.

Сервер (при синхронизации, по каждому скану):
1. patrol существует и status in (planned, in_progress) — иначе patrol_closed.
2. client_uuid уже был → duplicate (идемпотентность, не ошибка для приложения).
3. Точка принадлежит маршруту обхода — иначе wrong_checkpoint.
4. Все предыдущие точки (order_num меньше) уже отмечены — иначе out_of_order.
   Исключение: если это повторная доставка пачки после сбоя — сверка по
   client_uuid восстанавливает порядок.
5. scanned_at в [window_start − 5 мин, window_end + 15 мин] — иначе отметка
   принимается, но помечается out_of_window (не блокирует, факт фиксируется).

Любой accepted-скан: checkpoints_scanned++, patrol.status → in_progress
(при первом), при scanned == total → completed + finished_at.

### Автофиксация нарушений (фоновая задача, раз в минуту)
- Окно истекло (now > window_end + 15 мин), сканов 0 → violation
  missed_patrol, patrol.status = missed.
- Окно истекло, 0 < scanned < total → violation missed_points (details:
  список непройденных), patrol.status = partial.
- Один patrol → максимум один violation каждого вида; повторная фиксация
  идемпотентна.
- Фиксация нарушения → запись в notifications (кабинет диспетчера).

---

## 7. Офлайн-режим и синхронизация

- Полный пакет данных при логине/пульсе: GET /mobile/sync (маршруты объекта,
  точки с кодами, мои смены, плановые обходы на 48 ч). Room хранит всё.
- Каждая отметка: client_uuid (UUIDv4 на устройстве) — ключ идемпотентности.
- Очередь отправки в Room (WorkManager): батчи по 50 сканов, exponential
  backoff. Ответ сервера по каждому скану обновляет локальный статус
  (accepted/duplicate — синее; wrong/out_of_order — предупреждение на экране).
- Конфликты: сервер — источник истины по статусам patrol; устройство не
  пытается менять статусы, только шлёт сканы. Дубль client_uuid — skip.
  Время: scanned_at всегда с устройства; рассинхрон часов фиксируется как
  out_of_window (факт), не отклоняется.
- «Завершить обход»: если сеть есть — сразу; нет — локально завершён,
  финальный статус подтвердит сервер (паттерн тот же, что у сканов).

---

## 8. Безопасность и аудит

- Пароли: argon2id. JWT: access 30 мин, refresh 30 дней, refresh ротация.
- HTTPS (nginx, Let's Encrypt на проде; self-signed на dev).
- ПДн (152-ФЗ, базовый уровень): ФИО + логин; шифрование трафика; хеширование
  паролей; хранение на сервере РФ (прод-VPS).
- Аудит: все мутации диспетчера (create/update/delete объектов, маршрутов,
  точек, расписаний, смен, охранников, чтение отчётов) → audit_logs
  (user, action, entity, entity_id, payload-diff, ts). Журнал только читается.
- Rate-limit на /auth/login (5/мин/IP) — простая защита брутфорса.

---

## 9. Отчётность

- Обходы за период: фильтры объект/охранник/статус; колонки: дата, объект,
  маршрут, охранник (начавший), окно, статус, точек пройдено/всего.
- Нарушения за период: тип, объект, дата окна, кто должен был, детали.
- Форматы: CSV (utf-8-sig для Excel) и xlsx (openpyxl). streaming-выдача.

---

## 10. Нефункциональные требования

- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (sync), Alembic, Pydantic v2.
- БД: PostgreSQL 16.
- Кабинет: React 18 + TypeScript + Vite + TanStack Query.
- Android: Kotlin, Jetpack Compose, Room, CameraX + ML Kit (сканер),
  Retrofit + OkHttp, WorkManager (sync).
- Инфра: Docker + docker-compose, nginx reverse-proxy, HTTPS.
- Тесты: pytest (валидация, нарушения, auth, RBAC); JUnit — парсер QR и sync.
- Код: слои router → service → repository; схемы Pydantic на вход/выход;
  никаких TODO в критичном.

---

## 11. Архитектура (компоненты)

```
[Android (Kotlin)] --HTTPS--> [nginx] --/api--> [FastAPI uvicorn]
                                                   ├─ auth (JWT, RBAC)
                                                   ├─ routers (v1)
                                                   ├─ services (валидация,
                                                   │   нарушения, отчёты)
                                                   ├─ repositories (SA2)
                                                   ├─ scheduler (APScheduler:
                                                   │   порождение обходов,
                                                   │   фиксация нарушений)
                                                   └─ PostgreSQL 16
[React-кабинет] --HTTPS----> [nginx] --/ (static)] 
```

- Один compose: api, db, nginx (+ сборка кабинета в образ nginx).
- Dev: тот же compose на 155.212.140.81, порт 8080 (там уже живут Rails на
  3000 и пр.).

---

## 12. Структура репозитория

```
patrol/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, db.py
│   │   ├── models/ (sqlalchemy)
│   │   ├── schemas/ (pydantic)
│   │   ├── routers/ (auth, objects, routes, checkpoints, schedules,
│   │   │           shifts, guards, patrols, dashboard, notifications,
│   │   │           reports, audit, mobile)
│   │   ├── services/ (patrol_engine, violations, qr_pdf, audit, reports)
│   │   ├── core/ (security, deps, scheduler)
│   │   └── tests/
│   ├── alembic/
│   ├── Dockerfile, requirements.txt, .env.example
├── web/ (React: src/pages, src/components, src/api)
├── android/ (проект Kotlin)
├── docs/tz.md (этот документ)
├── docker-compose.yml
└── README.md
```
