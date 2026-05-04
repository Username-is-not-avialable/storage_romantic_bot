# TASKS: План работ по проекту

## Легенда
- Priority: `P0` (критично), `P1` (высоко), `P2` (средне).
- Status: `todo`, `in_progress`, `done`, `blocked`.
- DoD: критерии готовности задачи.

## Epic 0 - Техбаза проекта
### T-001 Настроить миграции Alembic
- Priority: P0
- Status: done
- DoD:
  - Добавлен Alembic и baseline-миграция.
  - Применение миграции поднимает текущую схему.
  - В README/API docs есть команда запуска миграций.

### T-002 Ввести централизованную конфигурацию
- Priority: P0
- Status: done
- DoD:
  - Настройки БД, токенов и фич-флагов вынесены в единый config.
  - Есть валидация обязательных env.

### T-003 Базовые middlewares и observability
- Priority: P1
- Status: todo
- DoD:
  - request-id в логах.
  - Глобальный обработчик ошибок с единым форматом ответа.

### T-004 Healthcheck endpoint `/health`
- Priority: P1
- Status: todo
- DoD:
  - Добавлен `GET /health` без доступа к персональным данным.
  - `docker-compose.yml`/инфра могут использовать endpoint для depends_on/проверок.

### T-005 Политика логирования и маскирование PII
- Priority: P1
- Status: todo
- DoD:
  - Персональные данные (phone/document) не попадают в логи в открытом виде.
  - Ошибки наружу не возвращают внутренние traceback/детали исключений.

### T-006 Привести конфигурацию подключения к БД к единому источнику
- Priority: P1
- Status: done
- DoD:
  - API использует единый механизм конфигурации DSN (например `DATABASE_URL`) согласованный с `docker-compose.yml`.
  - Нет “двух истин” (ручной `init_db.py` и отдельная сборка DSN в runtime без учета compose env).

## Epic 1 - Роли и безопасность
### T-010 Реализовать RBAC (`member`, `manager`, `admin`)
- Priority: P0
- Status: done
- DoD:
  - Роли хранятся явно в БД.
  - Доступ к manager/admin endpoints ограничен.
  - Добавлены тесты на запрет/доступ.

### T-011 Добавить auth для web и связку с мессенджерами
- Priority: P0
- Status: done
- DoD:
  - Web-auth endpoint(ы) работают.
  - Пользователь может быть идентифицирован в API и ботах как одна сущность.

### T-012 Администрирование пользователей и ролей
- Priority: P1
- Status: todo
- DoD:
  - Реализованы admin endpoints:
    - `GET /api/admin/users`
    - `PATCH /api/admin/users/{id}/roles`
  - Есть проверки прав (`admin`) и аудит изменений ролей.

### T-013 Исправить обновление пользователя в `PATCH /api/users/{id_telegram}`
- Priority: P1
- Status: todo
- DoD:
  - Эндпоинт обновляет пользователя по `id_telegram` из path-параметра, а не `current_user` без проверки.
  - Добавлены корректные проверки прав доступа к обновлению (self/admin по согласованной политике).
  - Добавлены тесты на успешный и запрещенный сценарии обновления.

## Epic 2 - Каталог и доступность
### T-020 Доработать модель `Gear`
- Priority: P1
- Status: todo
- DoD:
  - Инвариант: `0 <= available_count <= total_quantity`.

### T-021 Поиск и фильтрация каталога
- Priority: P1
- Status: done
- DoD:
  - Поиск по названию и описанию.
  - Пагинация и сортировка.

### T-022 Календарь доступности
- Priority: P2
- Status: todo
- DoD:
  - Endpoint доступности на диапазон дат.
  - Учитываются активные брони и аренды.

## Epic 3 - Заявки и аренды
### T-030 Добавить модель и API `RentalRequest`
- Priority: P0
- Status: done
- DoD:
  - Статусы `pending/approved/rejected/cancelled/expired`.
  - Поля: позиции, залоговый документ, дата сдачи, мероприятие, комментарий.

### T-031 Очередь входящих заявок для завснара
- Priority: P0
- Status: done
- DoD:
  - Отдельный manager endpoint для просмотра и фильтров заявок.
  - Сортировка по дате создания/срочности.

### T-032 Подтверждение/отклонение заявок
- Priority: P0
- Status: done
- DoD:
  - При approve проверяется доступность и резерв.
  - При reject можно передать комментарий/причину.
  - Все действия записываются в audit log.

### T-033 Операция выдачи по одобренной заявке
- Priority: P0
- Status: done
- DoD:
  - Выдача создаёт `Rental`.
  - `available_count` уменьшается атомарно.
  - Повторная выдача по той же заявке запрещена.

### T-034 Операция приема и частичного возврата
- Priority: P0
- Status: done
- DoD:
  - Поддержка частичного возврата без потери истории.
  - При полном возврате аренда закрывается.

### T-038 Заявки на возврат снаряжения (участник → завснар → решение)
- Priority: P0
- Status: done
- DoD:
  - Таблицы `rental_return_requests` / `rental_return_request_items`, миграция Alembic.
  - Участник создаёт заявку в `pending`; валидация владельца аренды, активной аренды, остатков по позициям, не более одной `pending` на аренду; опционально `target_manager_id`.
  - Завснар/админ approve/reject; при approve — делегирование в `return_rental` в той же транзакции.
  - REST и зеркальные маршруты `/api/integrations/vk/` без дублирования бизнес-логики.
  - Автотесты (web + VK RBAC), спецификация в [TECH_SPEC.md](../tech/TECH_SPEC.md).

### T-037 Перейти на целевую модель аренд (events + items, append-only)
- Priority: P0
- Status: done
- DoD:
  - Реализованы таблицы/модели: `rentals`, `rental_items`, `rental_events`, `rental_event_items`.
  - Возвраты фиксируются только через события (`RETURN_PARTIAL`/`RETURN_FINAL`) без перезаписи истории.
  - В `rental_events` хранится `fee_status_snapshot` (nullable) как аудит.
  - Закрытие аренды происходит только при полном возврате всех позиций; есть `status` и `closed_at` (или эквивалентное решение, не теряющее семантику спеки).

### T-035 Продление аренды через `ExtensionRequest`
- Priority: P1
- Status: todo
- DoD:
  - Участник может создать запрос продления активной аренды.
  - Завснар может approve/reject.

### T-036 Списки активных аренд, должников, история участника
- Priority: P1
- Status: done
- DoD:
  - Эндпоинты для трех отчетов.
  - Должники корректно определяются по due_date и return_date.

## Epic 4 - Взносы и внешняя интеграция
### T-040 Реализовать импорт статуса взносов из Excel
- Priority: P0
- Status: todo
- DoD:
  - Парсинг файла по утвержденной схеме.
  - Upsert статуса и даты окончания по участнику.
  - Протоколирование ошибок импорта.

### T-041 Политика взносов: без блокировки approve/issue + audit-снапшот
- Priority: P1
- Status: done
- DoD:
  - Одобрение заявок и выдача не блокируются из-за статуса взноса (`active/inactive/unknown/missing`).
  - В `rental_events.fee_status_snapshot` фиксируется статус взноса, видимый на момент действия (issue/returns).

## Epic 5 - Уведомления и боты
### T-050 Notification service + шаблоны сообщений
- Priority: P1
- Status: todo
- DoD:
  - Событийные уведомления по заявкам.
  - Напоминания о возврате и просрочках.

### T-053 Хранение логов уведомлений (`NotificationLog`)
- Priority: P2
- Status: todo
- DoD:
  - Добавлена сущность/таблица `NotificationLog` (канал, тип, payload, статус отправки, timestamps).
  - Неуспешные отправки не теряются, доступны для ретраев/диагностики.

### T-052 VK-адаптер (MVP)
- Priority: P1
- Status: todo
- DoD:
  - Поддержан основной поток участника.
  - Поддержаны ключевые уведомления для завснара.
  - Делегированная аутентификация пользователя ботом через `Depends(get_user_for_vk_bot)` и `X-VK-Bot-Secret`: см. [docs/tech/TECH_SPEC.md](../tech/TECH_SPEC.md) §4.3 и план в [docs/tech/VK_BOT_API_AUTH_PLAN.md](../tech/VK_BOT_API_AUTH_PLAN.md).

### T-054 Добавить каркас/проект бота в репозиторий
- Priority: P2
- Status: done
- DoD:
  - В репозитории присутствует `bot/` (или согласованная директория) для сборки сервиса `bot` из `docker-compose.yml`.
  - Определены базовые команды запуска и переменные окружения в README.

## Epic 6 - Качество и эксплуатация
### T-060 Покрыть API автотестами
- Priority: P0
- Status: todo
- DoD:
  - Критичный контур (issue/return/approve/reject/RBAC) покрыт тестами.
  - Тесты включены в CI.

### T-061 Контрактные тесты API
- Priority: P1
- Status: todo
- DoD:
  - Проверяется формат ключевых ответов и коды ошибок.

### T-062 Резервное копирование БД и восстановление
- Priority: P1
- Status: todo
- DoD:
  - Описан и проверен backup/restore сценарий.

### T-063 Audit log для критичных действий (`AuditLog`)
- Priority: P1
- Status: todo
- DoD:
  - Добавлена сущность/таблица `AuditLog`.
  - Логируются минимум: approve/reject booking, изменения ролей, ручные корректировки аренды.
  - Логи не содержат PII в открытом виде.

---

## Рекомендуемая последовательность (сверху вниз)
1. T-001 -> T-002 -> T-010 -> T-030 -> T-032 -> T-033 -> T-034
2. T-040
3. T-050 -> T-052
4. T-060 -> T-061 -> T-062
