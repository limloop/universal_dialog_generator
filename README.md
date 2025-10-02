# Universal Dialog Generator

🌍 **Универсальный генератор диалогов на multiple языках с поддержкой любых OpenAI-совместимых API**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/limloop/universal_dialog_generator/blob/main/LICENSE)

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