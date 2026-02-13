# Настройка Z.AI для парсинга объявлений

## Важно: GLM Coding Plan и API

**GLM Coding Plan НЕ покрывает API вызовы!**

Согласно [документации Z.AI](https://docs.z.ai/devpack/overview):

> "API calls are billed separately and do not use the Coding Plan quota."

GLM Coding Plan работает только в инструментах кодирования (Claude Code, Cline, OpenCode и т.д.), а не через API.

Для использования через API нужен **отдельный API ключ** и баланс на API аккаунте.

## Поддерживаемые модели

Для GLM Coding Plan поддерживаются только:

- `glm-4.6` (рекомендуется)
- `glm-4.5`
- `glm-4.5-air` (более легкая модель)

**Модель `GLM-4-Plus` не поддерживается планом!**

## Настройка .env

```env
# LLM Settings
LLM_PROVIDER=zai
LLM_API_KEY=your_api_key_here
LLM_MODEL=glm-4.6  # или glm-4.5, glm-4.5-air
LLM_BASE_URL=https://api.z.ai/api/paas/v4  # Общий API endpoint
# Для Coding Plan (если доступен через API): https://api.z.ai/api/coding/paas/v4
LLM_MAX_TOKENS=1000
LLM_TEMPERATURE=0.1
```

## Endpoints

- **Общий API**: `https://api.z.ai/api/paas/v4` (биллируется отдельно от Coding Plan)
- **Coding Plan API** (если доступен): `https://api.z.ai/api/coding/paas/v4`

## Лимиты и Concurrency

Если вы сталкиваетесь с ошибками превышения квоты:

1. **Проверьте баланс API аккаунта** - GLM Coding Plan не покрывает API вызовы
2. **Используйте поддерживаемую модель** - GLM-4.6, GLM-4.5 или GLM-4.5-Air
3. **Уменьшите concurrency** - слишком много одновременных запросов может привести к превышению лимитов
4. **Рассмотрите переход на более высокий план** - если используете API отдельно

## Рекомендации

1. Используйте `glm-4.6` для лучшего качества парсинга
2. Или `glm-4.5-air` для более быстрой и дешевой обработки
3. Убедитесь, что у вас есть баланс на API аккаунте (не только Coding Plan)
4. Мониторьте использование через логи и проверяйте баланс регулярно
