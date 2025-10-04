# Universal Dialog Generator

🌍 **Universal multi-language dialog generator with support for any OpenAI-compatible APIs**

<details>
<summary><i>🇷🇺 Русская версия / Russian version...</i></summary>

## 🚀 Возможности

- **Мультиязычность** - генерация диалогов на любых языках
- **Универсальность** - работает с любыми OpenAI-совместимыми API
- **Многопоточность** - параллельная генерация для максимальной производительности  
- **Кастомизация** - гибкая настройка тем, структур и стилей диалогов
- **Безопасность** - потокобезопасная запись и обработка ошибок
- **Масштабируемость** - ротация файлов и автоматическое восстановление

## 📦 Быстрый старт

### 1. Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/limloop/universal_dialog_generator.git
cd universal-dialog-generator

# Установите зависимости
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Отредактируйте `config.json`:

```json
{
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
- **Any OpenAI-compatible** - любой совместимый API

### Основные параметры config.json

```json
{
  "generation": {
    "threads": 2,                      // Количество рабочих потоков
    "temperature": {"min": 0.5, "max": 0.8},
    "dialog_lines": {"min": 4, "max": 16},
    "languages": [                     // Список языков для генерации
      {"code": "ru", "name": "русском"},
      {"code": "en", "name": "английском"}
    ]
  },
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key",        // Ваш API ключ
    "model": "gpt-3.5-turbo",         // Модель для генерации
    "timeout": 30,
    "max_tokens": 2000
  },
  "prompt_templates": {               // Шаблоны для генерации тем
    "base": "Создай диалог на ${language_name}...",
    "templates": ["Тема {concept} в {domain}"],
    "words": {
      "concept": ["эволюция", "синтез"],
      "domain": ["философии", "науке"]
    }
  },
  "output": {
    "filename": "dialogues.jsonl",    // Выходной файл
    "max_file_size_mb": 100,          // Макс. размер перед ротацией
    "backup_count": 5                 // Количество backup файлов
  }
}
```

## 🎯 Примеры использования

### Образовательные диалоги
```json
"prompt_templates": {
  "base": "Создай образовательный диалог на ${language_name}...",
  "templates": ["Объяснение {concept} через примеры из {domain}"],
  "words": {
    "concept": ["математики", "физики", "истории"],
    "domain": ["повседневной жизни", "технологий", "природы"]
  }
}
```

### Бизнес-диалоги  
```json
"templates": [
  "Обсуждение {business_topic} в контексте {industry}",
  "Диалог о {strategy} и ее реализации в {company_size}"
],
"words": {
  "business_topic": ["стратегии", "маркетинга", "управления"],
  "industry": ["IT", "ритейла", "финансов"],
  "strategy": ["роста", "оптимизации", "инноваций"],
  "company_size": ["стартапа", "среднего бизнеса", "корпорации"]
}
```

### Художественные диалоги
```json
"templates": [
  "Диалог между {character_a} и {character_b} о {topic}",
  "Разговор в {setting} о {theme}"
],
"words": {
  "character_a": ["детективом", "ученым", "художником"],
  "character_b": ["свидетелем", "студентом", "коллекционером"],
  "setting": ["старом замке", "космической станции", "кафе"],
  "theme": ["тайне", "открытии", "любви"]
}
```

## 📊 Выходные данные

Диалоги сохраняются в формате JSONL:

```json
{
  "theme": "Обсуждение искусственного интеллекта",
  "dialog": [
    "Как ты думаешь, ИИ изменит наше общество?",
    "Безусловно! Но важно понимать как именно...",
    "Можешь привести конкретные примеры?",
    "Конечно! Возьмем медицину..."
  ],
  "language": "ru"
}
```

## 🛠️ Разработка

### Структура проекта

```
universal_dialog_generator/
├── config/             # Управление конфигурацией
├── core/               # Основные компоненты генерации
├── storage/            # Потокобезопасная запись данных  
├── workers/            # Многопоточная обработка
├── main.py             # Точка входа
├── config.json         # Конфигурация
└── requirements.txt    # Зависимости
```

### Добавление новых шаблонов

1. Добавьте новые шаблоны в `prompt_templates.templates`
2. Расширьте словари в `prompt_templates.words` 
3. Обновите базовый промпт в `prompt_templates.base`

## 🐛 Устранение неполадок

### common issues:

**Пустой вывод:**
- Проверьте API ключ и URL
- Убедитесь что модель доступна
- Проверьте квоты API

**Ошибки валидации:**
- Проверьте структуру `output_schema`
- Убедитесь что промпт возвращает правильный JSON

**Низкая производительность:**
- Увеличьте `threads` в конфигурации
- Проверьте сетевую задержку до API

### 📚 Дополнительные инструменты

В папке `scripts/` доступны вспомогательные утилиты:

- **🧹 Dialog Cleaner** - очистка диалогов от артефактов генерации (китайские иероглифы, опечатки и др.)
- Подробная документация: [scripts/dialog_cleaner.md](https://github.com/limloop/universal_dialog_generator/blob/main/scripts/dialog_cleaner.md)

</details>

## 🚀 Features

- **Multi-language** - Generate dialogues in any language
- **Universal** - Works with any OpenAI-compatible APIs
- **Multi-threading** - Parallel generation for maximum performance
- **Customization** - Flexible configuration of themes, structures and styles
- **Safety** - Thread-safe writing and error handling
- **Scalability** - File rotation and automatic recovery

## 📦 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/limloop/universal_dialog_generator.git
cd universal-dialog-generator

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `config.json`:

```json
{
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
- **Any OpenAI-compatible** - any compatible API

### Main config.json Parameters

```json
{
  "generation": {
    "threads": 2,                      // Number of worker threads
    "temperature": {"min": 0.5, "max": 0.8},
    "dialog_lines": {"min": 4, "max": 16},
    "languages": [                     // List of languages for generation
      {"code": "ru", "name": "Russian"},
      {"code": "en", "name": "English"}
    ]
  },
  "api": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key",        // Your API key
    "model": "gpt-3.5-turbo",         // Model for generation
    "timeout": 30,
    "max_tokens": 2000
  },
  "prompt_templates": {               // Templates for theme generation
    "base": "Create a dialogue in ${language_name}...",
    "templates": ["Theme {concept} in {domain}"],
    "words": {
      "concept": ["evolution", "synthesis"],
      "domain": ["philosophy", "science"]
    }
  },
  "output": {
    "filename": "dialogues.jsonl",    // Output file
    "max_file_size_mb": 100,          // Max size before rotation
    "backup_count": 5                 // Number of backup files
  }
}
```

## 🎯 Usage Examples

### Educational Dialogues
```json
"prompt_templates": {
  "base": "Create an educational dialogue in ${language_name}...",
  "templates": ["Explanation of {concept} through examples from {domain}"],
  "words": {
    "concept": ["mathematics", "physics", "history"],
    "domain": ["daily life", "technology", "nature"]
  }
}
```

### Business Dialogues
```json
"templates": [
  "Discussion of {business_topic} in the context of {industry}",
  "Dialogue about {strategy} and its implementation in {company_size}"
],
"words": {
  "business_topic": ["strategy", "marketing", "management"],
  "industry": ["IT", "retail", "finance"],
  "strategy": ["growth", "optimization", "innovation"],
  "company_size": ["startup", "medium business", "corporation"]
}
```

### Artistic Dialogues
```json
"templates": [
  "Dialogue between {character_a} and {character_b} about {topic}",
  "Conversation in {setting} about {theme}"
],
"words": {
  "character_a": ["detective", "scientist", "artist"],
  "character_b": ["witness", "student", "collector"],
  "setting": ["old castle", "space station", "cafe"],
  "theme": ["mystery", "discovery", "love"]
}
```

## 📊 Output Data

Dialogues are saved in JSONL format:

```json
{
  "theme": "Discussion about artificial intelligence",
  "dialog": [
    "Do you think AI will change our society?",
    "Absolutely! But it's important to understand how exactly...",
    "Can you give specific examples?",
    "Of course! Let's take medicine..."
  ],
  "language": "en"
}
```

## 🛠️ Development

### Project Structure

```
universal_dialog_generator/
├── config/             # Configuration management
├── core/               # Core generation components
├── storage/            # Thread-safe data writing
├── workers/            # Multi-threaded processing
├── main.py             # Entry point
├── config.json         # Configuration
└── requirements.txt    # Dependencies
```

### Adding New Templates

1. Add new templates to `prompt_templates.templates`
2. Extend dictionaries in `prompt_templates.words`
3. Update base prompt in `prompt_templates.base`

## 🐛 Troubleshooting

### Common Issues:

**Empty output:**
- Check API key and URL
- Ensure model is available
- Check API quotas

**Validation errors:**
- Check `output_schema` structure
- Ensure prompt returns valid JSON

**Low performance:**
- Increase `threads` in configuration
- Check network latency to API

### 📚 Additional Tools

The `scripts/` folder contains helper utilities:

- **🧹 Dialog Cleaner** - cleans dialogues from generation artifacts (Chinese characters, typos, etc.)
- Detailed documentation: [scripts/dialog_cleaner.md](https://github.com/limloop/universal_dialog_generator/tree/main/scripts/dialog_cleaner.md)