## 🧹 Dialog Cleaner Tool

<details>
<summary><i>🇷🇺 Русская версия / Russian version...</i></summary>

### Очистка диалогов от артефактов генерации

Скрипт `scripts/dialog_cleaner.py` автоматически обнаруживает и исправляет артефакты в сгенерированных диалогах:

#### 🔍 Обнаруживаемые артефакты:
- **Китайские иероглифы** (中文测试)
- **Японские символы** (ひらがな, カタカナ)  
- **Символы замены** (�)
- **Опечатки и грамматические ошибки**

#### 🚀 Использование

```bash
# Анализ файла на наличие артефактов
python scripts/dialog_cleaner.py --input dialogues.jsonl --analyze

# Очистка файла с диалогами
python scripts/dialog_cleaner.py --input dialogues.jsonl --output cleaned_dialogues.jsonl

# Очистка с кастомным размером батча
python scripts/dialog_cleaner.py -i dialogues.jsonl -o cleaned_dialogues.jsonl --batch-size 20

# С указанием конфигурационного файла
python scripts/dialog_cleaner.py -i input.jsonl -o output.jsonl --config config.json
```

#### 📊 Пример анализа:

```bash
python scripts/dialog_cleaner.py -i dialogues.jsonl --analyze
```

Вывод анализа:
```json
{
  "total_dialogs": 1000,
  "dialogs_with_artifacts": 45,
  "total_lines": 12000,
  "lines_with_artifacts": 67,
  "artifact_types": {
    "chinese": 42,
    "japanese_hiragana": 15,
    "replacement_char": 10
  },
  "sample_artifacts": [
    {
      "text": "Это тест 中文测试 с артефактами",
      "artifacts": ["中", "文", "测"]
    }
  ]
}
```

#### ⚙️ Параметры командной строки:

- `--input, -i` - входной файл с диалогами (обязательно)
- `--output, -o` - выходной файл (обязательно для очистки)
- `--config, -c` - файл конфигурации (по умолчанию: config.json)
- `--analyze, -a` - только анализ без очистки
- `--batch-size, -b` - размер батча для обработки (по умолчанию: 10)

#### 🔧 Как это работает:

1. **Обнаружение** - скрипт сканирует текст по регулярным выражениям
2. **Очистка** - использует AI API для исправления артефактов
3. **Сохранение** - сохраняет исходный стиль и смысл высказывания
4. **Логирование** - подробное логирование процесса очистки

#### 📝 Пример очистки:

**До:**
```json
{
  "theme": "Обсуждение технологий",
  "dialog": [
    "Это тест 中文测试 с китайскими символами",
    "А это нормальный текст без проблем",
    "ここに日本語のテキストがあります"
  ],
  "language": "ru"
}
```

**После:**
```json
{
  "theme": "Обсуждение технологий", 
  "dialog": [
    "Это тест с китайскими символами",
    "А это нормальный текст без проблем", 
    "Здесь японский текст",
  ],
  "language": "ru",
  "cleaned": true
}
```

#### 💡 Особенности:

- **Безопасность** - при ошибках сохраняет оригинальный текст
- **Эффективность** - батчевая обработка для оптимизации API запросов
- **Гибкость** - работает с любыми языками через конфигурацию
- **Детектирование** - пропускает чистые строки без артефактов

</details>

### Cleaning Dialogues from Generation Artifacts

The `scripts/dialog_cleaner.py` script automatically detects and fixes artifacts in generated dialogues:

#### 🔍 Detected Artifacts:
- **Chinese characters** (中文测试)
- **Japanese symbols** (ひらがな, カタカナ)
- **Replacement characters** (�)
- **Typos and grammatical errors**

#### 🚀 Usage

```bash
# Analyze file for artifacts
python scripts/dialog_cleaner.py --input dialogues.jsonl --analyze

# Clean dialogue file
python scripts/dialog_cleaner.py --input dialogues.jsonl --output cleaned_dialogues.jsonl

# Clean with custom batch size
python scripts/dialog_cleaner.py -i dialogues.jsonl -o cleaned_dialogues.jsonl --batch-size 20

# With custom config file
python scripts/dialog_cleaner.py -i input.jsonl -o output.jsonl --config config.json
```

#### 📊 Analysis Example:

```bash
python scripts/dialog_cleaner.py -i dialogues.jsonl --analyze
```

Analysis output:
```json
{
  "total_dialogs": 1000,
  "dialogs_with_artifacts": 45,
  "total_lines": 12000,
  "lines_with_artifacts": 67,
  "artifact_types": {
    "chinese": 42,
    "japanese_hiragana": 15,
    "replacement_char": 10
  },
  "sample_artifacts": [
    {
      "text": "This is a test 中文测试 with artifacts",
      "artifacts": ["中", "文", "测"]
    }
  ]
}
```

#### ⚙️ Command Line Parameters:

- `--input, -i` - input dialogue file (required)
- `--output, -o` - output file (required for cleaning)
- `--config, -c` - configuration file (default: config.json)
- `--analyze, -a` - analysis only without cleaning
- `--batch-size, -b` - processing batch size (default: 10)

#### 🔧 How It Works:

1. **Detection** - scans text using regular expressions
2. **Cleaning** - uses AI API to fix artifacts
3. **Preservation** - maintains original style and meaning
4. **Logging** - detailed logging of cleaning process

#### 📝 Cleaning Example:

**Before:**
```json
{
  "theme": "Technology discussion",
  "dialog": [
    "This is a test 中文测试 with Chinese characters",
    "And this is normal text without issues",
    "ここに日本語のテキストがあります"
  ],
  "language": "en"
}
```

**After:**
```json
{
  "theme": "Technology discussion",
  "dialog": [
    "This is a test with Chinese characters",
    "And this is normal text without issues",
    "Here is Japanese text"
  ],
  "language": "en",
  "cleaned": true
}
```

#### 💡 Features:

- **Safety** - preserves original text on errors
- **Efficiency** - batch processing for API optimization
- **Flexibility** - works with any language through configuration
- **Detection** - skips clean lines without artifacts