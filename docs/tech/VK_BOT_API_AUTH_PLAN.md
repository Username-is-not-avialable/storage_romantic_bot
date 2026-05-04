# План: `get_user_for_vk_bot` и делегированные эндпоинты для VK-бота

Документ самодостаточен для переноса в другой диалог/репозиторий. Архитектурное решение зафиксировано в [TECH_SPEC.md](TECH_SPEC.md) (§4.3, §7.1.1).

## 1. Цель

Позволить процессу VK-бота вызывать операции API **от имени связанного пользователя** (`User`), используя:

- заголовок `X-VK-Bot-Secret` — доказывает, что вызов идёт от доверенного бота (не от произвольного клиента интернета);
- параметр **`vk_user_id`** (обычно query или поле JSON body) — сопоставляется с `user_messenger_links` (`provider=vk`, `external_user_id=str(vk_user_id)`).

После этого роутеры вызывают **те же сервисы**, что и web-роутеры с JWT/cookie-сессией, без копирования бизнес-логики.

### 1.1 Зафиксированное решение по URL и слой HTTP (дублирует [TECH_SPEC.md](TECH_SPEC.md) §7.1.1)

**Зафиксированное решение по URL:** действия, которые в браузере выполняются с cookie-сессией, а из процесса VK-бота — с `X-VK-Bot-Secret` и `vk_user_id`, для бота **выставляются отдельными маршрутами** под префиксом `/api/integrations/vk/`, по смыслу зеркалирующими канонические пути из TECH_SPEC §7.3–§7.4 (конкретный список и контракт — в этом документе ниже, шаг C). Так явно разделены публичный web-контур и доверенный интеграционный контур бота; усложняется случайная конфигурация «двойной» аутентификации на одном URL. **Доменная логика не дублируется:** вызываются те же функции сервисного слоя. Полное копирование длинных тел FastAPI-обработчиков между web и VK **нежелательно** — общие шаги (валидации доступа к сущности, вызов сервиса, сбор ответа) выносятся в переиспользуемые функции; см. правила в `.cursor/rules/project-standards.mdc` (раздел про дублирующиеся роутеры).

## 2. Угрозы и ограничения

| Риск | Митигация |
|------|-----------|
| Подделка `vk_user_id` снаружи | Эндпоинты принимают `vk_user_id` **только** в связке с валидным `X-VK-Bot-Secret`; секрет только у API и процесса бота. |
| Утечка секрета | Хранить в env (`VK_BOT_SECRET`); не логировать; разные значения для dev/prod по возможности. |
| Непривязанный VK | После резолва link отсутствует `User` — возвращать `404` с явным текстом («аккаунт не привязан»). |
| Недостаточная роль | После получения `User` применять те же проверки ролей, что для web (`member` / `manager` / `admin`). |

Открытый публичный API **не** должен использовать только `vk_user_id` без секрета бота.

## 3. Шаги реализации (порядок)

### Шаг A — общая зависимость FastAPI

**Файл:** разумно добавить рядом с существующими зависимостями, например [`api/dependencies.py`](/home/minty/storage_romantic_bot/api/dependencies.py) (или узкий модуль `api/dependencies_vk_bot.py`, если нужно разгрузить файл).

**Поведение `get_user_for_vk_bot`:**

1. Читает заголовок `X-VK-Bot-Secret` (алиас уже используется в [`api/routers/vk_integration.py`](/home/minty/storage_romantic_bot/api/routers/vk_integration.py) — сохранить тот же `alias`/`compare_digest`, что у `_require_vk_bot_secret`).
2. Если секрет не настроен у API (`VK_BOT_SECRET` пустой) — `503` с понятным `detail` (как сейчас при отсутствии секрета).
3. Принимает **`vk_user_id: int`** из запроса (явный контракт на каждом эндпоинте: query `vk_user_id` или поле body — зафиксировать единообразно, например везде query для GET, body для POST).
4. Вызывает существующий резолвер пользователя: `get_user_profile_for_vk(db, vk_user_id)` из [`api/services/vk_integration.py`](/home/minty/storage_romantic_bot/api/services/vk_integration.py).
5. Если `user is None` — `404`.
6. Возвращает `User`.

**Дополнительно (по необходимости):**

- `get_manager_for_vk_bot` = `get_user_for_vk_bot` + проверка `user.role in ("manager", "admin")`, иначе `403` — для эндпоинтов «завснар нажал кнопку в боте».

Реализация через `Annotated`:

```python
VkBotUser = Annotated[User, Depends(get_user_for_vk_bot)]
```

(имя типа — по вкусу команды; в спеке зафиксировано имя зависимости `get_user_for_vk_bot`.)

### Шаг B — не дублировать проверку секрета

Сейчас `_require_vk_bot_secret` — локальная функция в `vk_integration.py`. Вынести проверку секрета в одну функцию (например `verify_vk_bot_secret_header`) и вызывать её из:

- существующих `link-complete` / `me` (рефактор без смены контракта);
- новой `get_user_for_vk_bot`.

### Шаг C — новые маршруты под префиксом `/api/integrations/vk/`

Расширить [`api/routers/vk_integration.py`](/home/minty/storage_romantic_bot/api/routers/vk_integration.py) или вынести второй роутер `vk_bot_actions.py` с тем же `prefix`, подключить в [`api/main.py`](/home/minty/storage_romantic_bot/api/main.py).

**Принцип каждого эндпоинта:** тело/параметры как у web-аналога, но вместо `Depends(get_current_user)` / `require_roles` — `VkBotUser` (и при необходимости проверка роли той же логикой, что в web).

**Минимальный первый набор (после внедрения зависимости):**

| Действие | Web-эталон | VK-integration (пример пути) |
|----------|------------|------------------------------|
| Создать заявку на выдачу | `POST /api/rental-requests` | `POST /api/integrations/vk/rental-requests` + `vk_user_id` + secret |
| Обновить заявку (pending) | `PATCH /api/rental-requests/{id}` | `PATCH /api/integrations/vk/rental-requests/{id}` |
| Создать заявку на возврат | `POST /api/rental-return-requests` | `POST /api/integrations/vk/rental-return-requests` + `vk_user_id` + secret |
| Список активных аренд участника | `GET /api/rentals/active` | `GET /api/integrations/vk/rentals/active?vk_user_id=` |
| Решение завснара по заявке на выдачу | `PATCH /api/manager/rental-requests/{id}` | `PATCH /api/integrations/vk/manager/rental-requests/{id}` + `vk_user_id` менеджера + secret |
| Решение завснара по заявке на возврат | `PATCH /api/manager/rental-return-requests/{id}` | `PATCH /api/integrations/vk/manager/rental-return-requests/{id}` + `vk_user_id` менеджера + secret |
| Список завснаров/админов с привязкой VK (для `target_manager_id` и уведомлений) | — | `GET /api/integrations/vk/managers` — только секрет бота, без `vk_user_id` |

Реализация — **вызов тех же функций сервисного слоя**, что уже вызывают web-роутеры (копировать только «склейку» HTTP → сервис, как в тонких роутерах).

**Важно:** для `list active rentals` в web у member нет параметра чужого `user_id`; для VK-integration достаточно всегда фильтровать по `VkBotUser.id` (игнорируя попытку указать другого пользователя).

### Шаг D — тесты

**Файл:** расширить [`api/tests/test_vk_integration.py`](/home/minty/storage_romantic_bot/api/tests/test_vk_integration.py) или добавить соседний модуль.

Минимум:

1. Успех: секрет верный + привязанный VK → `POST .../integrations/vk/rental-requests` создаёт заявку (как в [`test_rental_requests`](/home/minty/storage_romantic_bot/api/tests/test_rental_requests.py) для member).
2. Неверный секрет → `401`.
3. Нет привязки VK → `404`.
4. Member не может дернуть manager-only vk-эндпоинт → `403`.

Использовать те же фикстуры БД пользователей/ссылок, что уже есть для vk link tests.

### Шаг E — клиент бота

В [`bot/bot/main.py`](/home/minty/storage_romantic_bot/bot/bot/main.py) (или вынесенный `api_client.py`):

- на каждый вызов к integration передавать `headers={"X-VK-Bot-Secret": ...}` и `vk_user_id` согласно контракту;
- базовый URL тот же `API_BASE_URL`.

## 4. Что явно выходит за рамки этой фичи

- Сценарий «участник инициирует возврат, завснар подтверждает» реализован отдельно от `get_user_for_vk_bot`: доменные сущности `rental_return_requests` и REST/VK-эндпоинты (см. [TECH_SPEC.md](TECH_SPEC.md) §5.2.5 и §7.3.1). Прямой менеджерский возврат без заявки по-прежнему доступен как `PATCH /api/rentals/{id}/return`.
- Уведомления завснару в VK после создания заявки — канал отправки из API или из бота; зависимость `get_user_for_vk_bot` к этому не привязана.

## 5. Критерии готовности (DoD)

- Единая зависимость `get_user_for_vk_bot`, переиспользуемая на всех vk-integration эндпоинтах «от имени пользователя».
- Проверка секрета не дублируется расходящимся кодом.
- Хотя бы один полный сценарий «участник через бота создаёт `RentalRequest`» покрыт тестом.
- Документация: [TECH_SPEC.md](TECH_SPEC.md) уже ссылается на этот план; при закрытии задачи обновить [TASKS.md](../planning/TASKS.md) (например T-052 / подзадача про VK integration actions).
