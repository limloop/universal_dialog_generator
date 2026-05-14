# Universal Dialog Generator

🌍 **Universal multi-language dialog generator with support for any OpenAI-compatible APIs**

<details>
<summary><i>🇷🇺 Русская версия / Russian version...</i></summary>

## 🚀 Возможности

- **Два режима работы**:
  - **Генерация диалогов** - создание структурированных диалогов на основе тем и шаблонов
  - **Перевод текстов** - массовый перевод из датасетов (Hugging Face или локальные файлы)
- **Универсальность** - работает с любыми OpenAI-совместимыми API
- **Гибкая кастомизация** - можно генерировать не только диалоги, а **любые плоские JSON-схемы** (массивы поддерживаются, вложенные объекты - нет)
- **Многопоточность** - параллельная обработка для максимальной производительности
- **Отказоустойчивость** - автоматические повторные попытки, чекпоинты и восстановление после сбоев
- **Потокобезопасность** - безопасная запись и обработка ошибок в многопоточной среде
- **Масштабируемость** - ротация файлов при достижении лимита размера
- **Поддержка датасетов** - интеграция с Hugging Face datasets и локальными JSON/JSONL файлами

## 📦 Быстрый старт

### 1. Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/limloop/universal_dialog_generator.git
cd universal-dialog-generator

# Установите зависимости
pip install -r requirements.txt

# Для работы с Hugging Face датасетами (опционально)
pip install datasets
```

### 2. Настройка конфигурации

Выберите режим работы, отредактировав `config.json`:

#### Режим генерации диалогов (по умолчанию):

```json
{
  "task_type": "dialog_generation",
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "model": "gpt-3.5-turbo"
  },
  "generation": {
    "threads": 2,
    "languages": [
      {"code": "ru", "name": "русском"},
      {"code": "en", "name": "английском"}
    ]
  },
  "prompt_templates": {
    "base": "Создай диалог на ${language_name}...",
    "templates": ["Тема {concept} в {domain}"],
    "words": {
      "concept": ["эволюция", "синтез"],
      "domain": ["философии", "науке"]
    }
  }
}
```

#### Режим перевода текстов:

```json
{
  "task_type": "translation",
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "model": "gpt-3.5-turbo"
  },
  "translation": {
    "dataset": {
      "source": "huggingface",
      "path": "username/dataset-name",
      "fields": {
        "id": "id",
        "text": "source_text"
      }
    },
    "target_language": "tokipona",
    "threads": 2,
    "prompt_template": {
      "system": "Ты профессиональный переводчик...",
      "user": "Переведи на {target_language}:\n{original_text}"
    }
  }
}
```

### 3. Запуск

```bash
python main.py
```

## ⚙️ Конфигурация

### Поддерживаемые API провайдеры

- **OpenAI** - `https://api.openai.com/v1`
- **LocalAI** - `http://localhost:8080/v1`
- **Любой OpenAI-совместимый API**

### Общие параметры

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `task_type` | Режим работы: `dialog_generation` или `translation` | `dialog_generation` |
| `api.base_url` | URL API-провайдера | `https://api.openai.com/v1` |
| `api.api_key` | API ключ | обязательный |
| `api.model` | Модель для генерации | `gpt-3.5-turbo` |
| `api.timeout` | Таймаут запроса (сек) | `30` |
| `api.max_tokens` | Максимум токенов в ответе | `2000` |
| `output.filename` | Имя выходного файла | `dialogues.jsonl` |
| `output.max_file_size_mb` | Макс. размер файла перед ротацией | `100` |
| `output.backup_count` | Количество backup-файлов | `5` |

### Режим генерации диалогов (`dialog_generation`)

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `generation.threads` | Количество рабочих потоков | `2` |
| `generation.temperature.min` | Минимальная температура генерации | `0.5` |
| `generation.temperature.max` | Максимальная температура генерации | `0.8` |
| `generation.dialog_lines.min` | Минимум реплик в диалоге | `4` |
| `generation.dialog_lines.max` | Максимум реплик в диалоге | `16` |
| `generation.languages` | Список языков для генерации | обязательный |
| `generation.request_delay` | Задержка между запросами (сек) | `0.5` |
| `generation.max_errors` | Макс. последовательных ошибок | `10` |

#### Шаблоны промптов (`prompt_templates`)

- **`base`** - базовый шаблон промпта. Доступные переменные:
  - `${language_name}` - название языка
  - `${min_lines}` - минимум реплик
  - `${max_lines}` - максимум реплик
  - `${theme}` - сгенерированная тема

- **`templates`** - массив шаблонов для генерации тем. Используйте `{placeholder}` для подстановки из `words`

- **`words`** - словари для подстановки. Ключи соответствуют плейсхолдерам в `templates`

### Режим перевода (`translation`)

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `translation.dataset.source` | Источник: `local` или `huggingface` | обязательный |
| `translation.dataset.path` | Путь к файлу или имя датасета на HF | обязательный |
| `translation.dataset.split` | Раздел датасета (для HF) | `train` |
| `translation.dataset.fields.id` | Поле с идентификатором | опционально |
| `translation.dataset.fields.text` | Поле с текстом для перевода | обязательный |
| `translation.dataset.filter` | Фильтр записей (для HF) | опционально |
| `translation.dataset.limit` | Лимит записей для обработки | опционально |
| `translation.target_language` | Целевой язык перевода | обязательный |
| `translation.threads` | Количество потоков | `2` |
| `translation.temperature` | Температура генерации | `0.3` |
| `translation.max_retries` | Макс. количество повторных попыток | `3` |
| `translation.retry_delay_seconds` | Задержка перед повтором (сек) | `5` |
| `translation.max_errors` | Макс. последовательных ошибок | `10` |
| `translation.checkpoint_file` | Файл для сохранения прогресса | `translation_progress.json` |
| `translation.prompt_template.system` | Системный промпт | опционально |
| `translation.prompt_template.user` | Пользовательский промпт | обязательный |

#### Переменные в пользовательском промпте:
- `{target_language}` - целевой язык
- `{original_text}` - исходный текст

## 🎯 Примеры использования

### 1. Генерация образовательных диалогов

```json
{
  "task_type": "dialog_generation",
  "prompt_templates": {
    "base": "Создай образовательный диалог на ${language_name} языке...",
    "templates": ["Объяснение {concept} через примеры из {domain}"],
    "words": {
      "concept": ["математики", "физики", "истории"],
      "domain": ["повседневной жизни", "технологий", "природы"]
    }
  }
}
```

### 2. Генерация произвольных JSON-объектов

Можно генерировать любые плоские JSON-схемы. Пример для создания описаний фэнтезийных существ:

```json
{
  "task_type": "dialog_generation",
  "prompt_templates": {
    "base": "Создай JSON с описанием существа на тему: ${theme}...",
    "templates": ["{size} {creature_type} из {biome}"],
    "words": {
      "size": ["маленький", "средний", "огромный"],
      "creature_type": ["дракон", "дух", "зверь"],
      "biome": ["леса", "гор", "пустыни"]
    }
  },
  "output_schema": {
    "fields": ["name", "description", "abilities"],
    "example": {
      "name": "Лесной дух",
      "description": "Загадочное существо...",
      "abilities": ["невидимость", "исцеление"]
    }
  }
}
```

### 3. Массовый перевод с Hugging Face

```json
{
  "task_type": "translation",
  "translation": {
    "dataset": {
      "source": "huggingface",
      "path": "limloop/ru_en_story_pairs",
      "split": "train",
      "fields": {
        "text": "text_en"
      },
      "limit": 1000
    },
    "target_language": "russian",
    "threads": 4,
    "prompt_template": {
      "system": "Ты профессиональный переводчик. Сохраняй стиль и смысл.",
      "user": "Переведи на {target_language}:\n{original_text}"
    }
  }
}
```

### 4. Перевод из локального файла

```json
{
  "task_type": "translation",
  "translation": {
    "dataset": {
      "source": "local",
      "path": "data/sentences.json",
      "fields": {
        "id": "sentence_id",
        "text": "content"
      }
    },
    "target_language": "tokipona",
    "checkpoint_file": "tokipona_progress.json"
  }
}
```

## 📊 Выходные данные

### Режим диалогов

```json
{
  "theme": "Решение логической головоломки",
  "dialog": [
    "У нас есть задача: переправить волка, козу и капусту через реку...",
    "Давайте разберемся. Что произойдет, если оставить волка с козой?",
    "Волк съест козу! Значит, их нельзя оставлять без присмотра.",
    "Правильно. А теперь подумаем о последовательности переправ..."
  ],
  "language": "ru",
  "temperature": 0.65,
  "timestamp": 1234567890,
  "worker_id": 1
}
```

### Режим перевода

```json
{
  "id": 42,
  "original_text": "The quick brown fox jumps over the lazy dog",
  "translated_text": "Быстрая коричневая лиса перепрыгивает через ленивую собаку",
  "target_language": "russian",
  "temperature": 0.3,
  "timestamp": 1234567890,
  "worker_id": 2
}
```

## 🛠️ Разработка

### Структура проекта

```
universal_dialog_generator/
├── config/             # Управление конфигурацией
│   └── config_manager.py
├── core/               # Основные компоненты
│   ├── api_client.py   # Клиент для API
│   ├── dataset_loader.py   # Загрузка датасетов
│   ├── prompt_engine.py    # Генерация промптов
│   ├── task_manager.py     # Управление задачами (translation)
│   ├── theme_generator.py  # Генерация тем
│   └── validator.py        # Валидация данных
├── storage/            # Потокобезопасная запись
│   └── thread_safe_writer.py
├── workers/            # Многопоточная обработка
│   ├── thread_pool.py
│   ├── worker_thread.py        # Для диалогов
│   └── translation_worker.py   # Для перевода
├── scripts/            # Вспомогательные утилиты
│   └── dialog_cleaner.py   # Очистка диалогов
├── main.py             # Точка входа
├── config.json         # Конфигурация
└── requirements.txt    # Зависимости
```

### Добавление новых шаблонов для диалогов

1. Добавьте шаблоны тем в `prompt_templates.templates`
2. Расширьте словари в `prompt_templates.words`
3. Обновите базовый промпт в `prompt_templates.base`

### Создание кастомной схемы вывода

```json
{
  "output_schema": {
    "fields": ["field1", "field2", "field3"],
    "example": {
      "field1": "значение1",
      "field2": "значение2",
      "field3": ["массив", "значений"]
    }
  }
}
```

**Важно:** схема должна быть **плоской** (без вложенных объектов). Массивы поддерживаются.

## 🔄 Чекпоинты и восстановление

### Режим генерации диалогов

- При прерывании (Ctrl+C) система сохраняет статистику
- При перезапуске начинается генерация новых тем

### Режим перевода

- Автоматическое сохранение прогресса в `translation_progress.json`
- При повторном запуске продолжается с прерванного места
- Проваленные задачи повторяются до `max_retries` раз
- Чекпоинт содержит ID обработанных и проваленных задач

## 🐛 Устранение неполадок

### Частые проблемы:

**Пустой вывод:**
- Проверьте API ключ и URL
- Убедитесь, что модель доступна
- Проверьте квоты API

**Ошибки валидации:**
- Проверьте структуру `output_schema`
- Убедитесь, что промпт возвращает правильный JSON
- Для translation: проверьте формат ответа API

**Низкая производительность:**
- Увеличьте `threads` в конфигурации
- Проверьте сетевую задержку до API
- Уменьшите `request_delay` для диалогов

**Ошибки загрузки датасета (translation):**
- Для HF: установите `pip install datasets`
- Для локальных файлов: проверьте путь и формат (JSON/JSONL)

### 📚 Дополнительные инструменты

В папке `scripts/` доступны вспомогательные утилиты:

- **🧹 Dialog Cleaner** - очистка диалогов от артефактов генерации (китайские иероглифы, опечатки и др.)
- Подробная документация: [scripts/dialog_cleaner.md](scripts/dialog_cleaner.md)

</details>

## 🚀 Features

- **Two operation modes**:
  - **Dialog Generation** - create structured dialogues based on themes and templates
  - **Text Translation** - batch translation from datasets (Hugging Face or local files)
- **Universal** - works with any OpenAI-compatible APIs
- **Flexible customization** - generate not only dialogues but **any flat JSON schemas** (arrays supported, nested objects not supported)
- **Multi-threading** - parallel processing for maximum performance
- **Fault tolerance** - automatic retries, checkpoints, and crash recovery
- **Thread-safe** - safe writing and error handling in multi-threaded environment
- **Scalability** - file rotation when size limit reached
- **Dataset support** - integration with Hugging Face datasets and local JSON/JSONL files

## 📦 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/limloop/universal_dialog_generator.git
cd universal-dialog-generator

# Install dependencies
pip install -r requirements.txt

# For Hugging Face datasets support (optional)
pip install datasets
```

### 2. Configuration

Choose operation mode by editing `config.json`:

#### Dialog generation mode (default):

```json
{
  "task_type": "dialog_generation",
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "model": "gpt-3.5-turbo"
  },
  "generation": {
    "threads": 2,
    "languages": [
      {"code": "ru", "name": "Russian"},
      {"code": "en", "name": "English"}
    ]
  },
  "prompt_templates": {
    "base": "Create a dialogue in ${language_name}...",
    "templates": ["Theme {concept} in {domain}"],
    "words": {
      "concept": ["evolution", "synthesis"],
      "domain": ["philosophy", "science"]
    }
  }
}
```

#### Translation mode:

```json
{
  "task_type": "translation",
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "model": "gpt-3.5-turbo"
  },
  "translation": {
    "dataset": {
      "source": "huggingface",
      "path": "username/dataset-name",
      "fields": {
        "id": "id",
        "text": "source_text"
      }
    },
    "target_language": "french",
    "threads": 2,
    "prompt_template": {
      "system": "You are a professional translator...",
      "user": "Translate to {target_language}:\n{original_text}"
    }
  }
}
```

### 3. Run

```bash
python main.py
```

## ⚙️ Configuration

### Supported API Providers

- **OpenAI** - `https://api.openai.com/v1`
- **LocalAI** - `http://localhost:8080/v1`
- **Any OpenAI-compatible API**

### Common Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `task_type` | Operation mode: `dialog_generation` or `translation` | `dialog_generation` |
| `api.base_url` | API provider URL | `https://api.openai.com/v1` |
| `api.api_key` | API key | required |
| `api.model` | Model for generation | `gpt-3.5-turbo` |
| `api.timeout` | Request timeout (seconds) | `30` |
| `api.max_tokens` | Max tokens in response | `2000` |
| `output.filename` | Output file name | `dialogues.jsonl` |
| `output.max_file_size_mb` | Max file size before rotation | `100` |
| `output.backup_count` | Number of backup files | `5` |

### Dialog Generation Mode (`dialog_generation`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `generation.threads` | Number of worker threads | `2` |
| `generation.temperature.min` | Minimum generation temperature | `0.5` |
| `generation.temperature.max` | Maximum generation temperature | `0.8` |
| `generation.dialog_lines.min` | Minimum dialog lines | `4` |
| `generation.dialog_lines.max` | Maximum dialog lines | `16` |
| `generation.languages` | List of languages for generation | required |
| `generation.request_delay` | Delay between requests (sec) | `0.5` |
| `generation.max_errors` | Max consecutive errors | `10` |

#### Prompt Templates (`prompt_templates`)

- **`base`** - base prompt template. Available variables:
  - `${language_name}` - language name
  - `${min_lines}` - minimum lines
  - `${max_lines}` - maximum lines
  - `${theme}` - generated theme

- **`templates`** - array of theme templates. Use `{placeholder}` for word bank substitution

- **`words`** - word banks for substitution. Keys match placeholders in `templates`

### Translation Mode (`translation`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `translation.dataset.source` | Source: `local` or `huggingface` | required |
| `translation.dataset.path` | File path or HF dataset name | required |
| `translation.dataset.split` | Dataset split (for HF) | `train` |
| `translation.dataset.fields.id` | ID field name | optional |
| `translation.dataset.fields.text` | Text field name | required |
| `translation.dataset.filter` | Record filter (for HF) | optional |
| `translation.dataset.limit` | Limit records to process | optional |
| `translation.target_language` | Target language for translation | required |
| `translation.threads` | Number of threads | `2` |
| `translation.temperature` | Generation temperature | `0.3` |
| `translation.max_retries` | Maximum retry attempts | `3` |
| `translation.retry_delay_seconds` | Delay before retry (sec) | `5` |
| `translation.max_errors` | Max consecutive errors | `10` |
| `translation.checkpoint_file` | Progress checkpoint file | `translation_progress.json` |
| `translation.prompt_template.system` | System prompt | optional |
| `translation.prompt_template.user` | User prompt | required |

#### User Prompt Variables:
- `{target_language}` - target language
- `{original_text}` - original text

## 🎯 Usage Examples

### 1. Educational Dialog Generation

```json
{
  "task_type": "dialog_generation",
  "prompt_templates": {
    "base": "Create an educational dialogue in ${language_name}...",
    "templates": ["Explanation of {concept} through examples from {domain}"],
    "words": {
      "concept": ["mathematics", "physics", "history"],
      "domain": ["daily life", "technology", "nature"]
    }
  }
}
```

### 2. Custom JSON Object Generation

Generate any flat JSON schemas. Example for fantasy creature descriptions:

```json
{
  "task_type": "dialog_generation",
  "prompt_templates": {
    "base": "Create a JSON creature description for theme: ${theme}...",
    "templates": ["{size} {creature_type} from {biome}"],
    "words": {
      "size": ["small", "medium", "huge"],
      "creature_type": ["dragon", "spirit", "beast"],
      "biome": ["forest", "mountains", "desert"]
    }
  },
  "output_schema": {
    "fields": ["name", "description", "abilities"],
    "example": {
      "name": "Forest Spirit",
      "description": "A mysterious creature...",
      "abilities": ["invisibility", "healing"]
    }
  }
}
```

### 3. Batch Translation with Hugging Face

```json
{
  "task_type": "translation",
  "translation": {
    "dataset": {
      "source": "huggingface",
      "path": "limloop/ru_en_story_pairs",
      "split": "train",
      "fields": {
        "text": "text_ru"
      },
      "limit": 1000
    },
    "target_language": "english",
    "threads": 4,
    "prompt_template": {
      "system": "You are a professional translator. Preserve style and meaning.",
      "user": "Translate to {target_language}:\n{original_text}"
    }
  }
}
```

### 4. Translation from Local File

```json
{
  "task_type": "translation",
  "translation": {
    "dataset": {
      "source": "local",
      "path": "data/sentences.json",
      "fields": {
        "id": "sentence_id",
        "text": "content"
      }
    },
    "target_language": "spanish",
    "checkpoint_file": "spanish_progress.json"
  }
}
```

## 📊 Output Data

### Dialog Mode

```json
{
  "theme": "Solving a logic puzzle",
  "dialog": [
    "We need to cross the river with a wolf, goat, and cabbage...",
    "Let's think this through. What happens if we leave the wolf with the goat?",
    "The wolf will eat the goat! So we can't leave them unattended.",
    "Exactly. Now let's plan the sequence of crossings..."
  ],
  "language": "en",
  "temperature": 0.65,
  "timestamp": 1234567890,
  "worker_id": 1
}
```

### Translation Mode

```json
{
  "id": 42,
  "original_text": "The quick brown fox jumps over the lazy dog",
  "translated_text": "Le renard brun rapide saute par-dessus le chien paresseux",
  "target_language": "french",
  "temperature": 0.3,
  "timestamp": 1234567890,
  "worker_id": 2
}
```

## 🛠️ Development

### Project Structure

```
universal_dialog_generator/
├── config/             # Configuration management
│   └── config_manager.py
├── core/               # Core components
│   ├── api_client.py   # API client
│   ├── dataset_loader.py   # Dataset loading
│   ├── prompt_engine.py    # Prompt generation
│   ├── task_manager.py     # Task management (translation)
│   ├── theme_generator.py  # Theme generation
│   └── validator.py        # Data validation
├── storage/            # Thread-safe writing
│   └── thread_safe_writer.py
├── workers/            # Multi-threaded processing
│   ├── thread_pool.py
│   ├── worker_thread.py        # For dialogues
│   └── translation_worker.py   # For translation
├── scripts/            # Helper utilities
│   └── dialog_cleaner.py   # Dialogue cleaning
├── main.py             # Entry point
├── config.json         # Configuration
└── requirements.txt    # Dependencies
```

### Adding New Dialog Templates

1. Add theme templates to `prompt_templates.templates`
2. Extend word banks in `prompt_templates.words`
3. Update base prompt in `prompt_templates.base`

### Creating Custom Output Schema

```json
{
  "output_schema": {
    "fields": ["field1", "field2", "field3"],
    "example": {
      "field1": "value1",
      "field2": "value2",
      "field3": ["array", "of", "values"]
    }
  }
}
```

**Important:** Schema must be **flat** (no nested objects). Arrays are supported.

## 🔄 Checkpoints and Recovery

### Dialog Generation Mode

- On interrupt (Ctrl+C), system saves statistics
- On restart, new themes are generated

### Translation Mode

- Automatic progress saving to `translation_progress.json`
- Resumes from where it left off on restart
- Failed tasks are retried up to `max_retries` times
- Checkpoint contains processed and failed task IDs

## 🐛 Troubleshooting

### Common Issues:

**Empty output:**
- Check API key and URL
- Ensure model is accessible
- Check API quotas

**Validation errors:**
- Verify `output_schema` structure
- Ensure prompt returns valid JSON
- For translation: check API response format

**Low performance:**
- Increase `threads` in configuration
- Check network latency to API
- Reduce `request_delay` for dialogues

**Dataset loading errors (translation):**
- For HF: install `pip install datasets`
- For local files: check path and format (JSON/JSONL)

### 📚 Additional Tools

The `scripts/` folder contains helper utilities:

- **🧹 Dialog Cleaner** - cleans dialogues from generation artifacts (Chinese characters, typos, etc.)
- Detailed documentation: [scripts/dialog_cleaner.md](scripts/dialog_cleaner.md)