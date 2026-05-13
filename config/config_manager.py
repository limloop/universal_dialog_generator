"""
Менеджер конфигурации с полной валидацией и безопасной загрузкой
Поддерживает два режима работы:
1. dialog_generation - генерация диалогов (оригинальный режим)
2. translation - перевод текстов из датасета
"""

import json
import json5
import logging
import os
import re
from typing import Dict, List, Any, Optional
from jsonschema import validate, ValidationError, SchemaError
import copy


class ConfigValidationError(Exception):
    """Кастомное исключение для ошибок валидации конфигурации"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Инициализация исключения валидации
        
        Args:
            message: Человеко-читаемое сообщение об ошибке
            details: Дополнительные детали ошибки (поле, значение и т.д.)
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Строковое представление с деталями"""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} [{details_str}]"
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Представление исключения в виде словаря"""
        return {
            "error": self.message,
            "details": self.details
        }


class ConfigManager:
    """
    Безопасный менеджер конфигурации с валидацией схемы
    Поддерживает режимы: dialog_generation (по умолчанию) и translation
    """
    
    # Базовая схема для общих полей
    BASE_SCHEMA = {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "enum": ["dialog_generation", "translation"],
                "default": "dialog_generation"
            },
            "api": {
                "type": "object",
                "required": ["model", "timeout", "max_tokens"],
                "properties": {
                    "base_url": {"type": "string"},
                    "api_key": {"type": "string"},
                    "model": {"type": "string", "minLength": 1},
                    "timeout": {"type": "integer", "minimum": 10, "maximum": 3000},
                    "max_tokens": {"type": "integer", "minimum": 100, "maximum": 100000}
                }
            },
            "output_schema": {
                "type": "object", 
                "required": ["fields", "example"],
                "properties": {
                    "fields": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1}
                    },
                    "example": {"type": "object"}
                }
            },
            "output": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "minLength": 1},
                    "max_file_size_mb": {"type": "number", "minimum": 1},
                    "backup_count": {"type": "integer", "minimum": 0}
                }
            }
        }
    }
    
    # Схема для режима генерации диалогов
    DIALOG_GENERATION_SCHEMA = {
        "type": "object",
        "required": ["generation", "prompt_templates"],
        "properties": {
            "generation": {
                "type": "object",
                "required": ["threads", "temperature", "dialog_lines", "languages"],
                "properties": {
                    "threads": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20
                    },
                    "temperature": {
                        "type": "object", 
                        "required": ["min", "max"],
                        "properties": {
                            "min": {"type": "number", "minimum": 0.0, "maximum": 2.0},
                            "max": {"type": "number", "minimum": 0.0, "maximum": 2.0}
                        }
                    },
                    "dialog_lines": {
                        "type": "object",
                        "required": ["min", "max"],
                        "properties": {
                            "min": {"type": "integer", "minimum": 2, "maximum": 50},
                            "max": {"type": "integer", "minimum": 2, "maximum": 50}
                        }
                    },
                    "languages": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["code", "name"],
                            "properties": {
                                "code": {"type": "string", "pattern": "^[a-z_]*"},
                                "name": {"type": "string", "minLength": 1}
                            }
                        }
                    },
                    "request_delay": {
                        "type": "number", 
                        "minimum": 0.0,
                        "default": 0.5
                    },
                    "max_errors": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 10
                    }
                }
            },
            "prompt_templates": {
                "type": "object",
                "required": ["base", "templates", "words"],
                "properties": {
                    "base": {"type": "string", "minLength": 10},
                    "templates": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 5}
                    },
                    "words": {
                        "type": "object",
                        "minProperties": 1,
                        "patternProperties": {
                            "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1}
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Схема для режима перевода
    TRANSLATION_SCHEMA = {
        "type": "object",
        "required": ["translation"],
        "properties": {
            "translation": {
                "type": "object",
                "required": ["dataset", "target_language"],
                "properties": {
                    "dataset": {
                        "type": "object",
                        "required": ["source", "path", "fields"],
                        "properties": {
                            "source": {
                                "type": "string",
                                "enum": ["local", "huggingface"]
                            },
                            "path": {"type": "string", "minLength": 1},
                            "split": {"type": "string"},
                            "fields": {
                                "type": "object",
                                "required": ["text"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "text": {"type": "string", "minLength": 1}
                                }
                            },
                            "filter": {"type": "object"},
                            "limit": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1000000
                            }
                        }
                    },
                    "checkpoint_file": {
                        "type": "string",
                        "default": "translation_progress.json"
                    },
                    "max_retries": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3
                    },
                    "retry_delay_seconds": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 60,
                        "default": 5
                    },
                    "target_language": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 10
                    },
                    "threads": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 2
                    },
                    "temperature": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.3
                    },
                    "max_errors": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 10
                    },
                    "prompt_template": {
                        "type": "object",
                        "properties": {
                            "system": {
                                "type": "string",
                                "minLength": 1,
                                "default": "Ты профессиональный переводчик. Переводи текст с сохранением смысла и стиля."
                            },
                            "user": {
                                "type": "string",
                                "minLength": 1,
                                "default": "Переведи следующий текст на {target_language}:\n\n{original_text}\n\nПеревод:"
                            }
                        },
                        "additionalProperties": False
                    }
                }
            }
        }
    }
    
    # Полная схема (объединяет базовую + специфичные)
    FULL_SCHEMA = {
        "type": "object",
        "allOf": [
            {"$ref": "#/definitions/base"},
            {
                "if": {
                    "properties": {"task_type": {"const": "dialog_generation"}}
                },
                "then": {"$ref": "#/definitions/dialog_generation"},
                "else": {"$ref": "#/definitions/translation"}
            }
        ],
        "definitions": {
            "base": BASE_SCHEMA,
            "dialog_generation": DIALOG_GENERATION_SCHEMA,
            "translation": TRANSLATION_SCHEMA
        }
    }
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация менеджера конфигурации
        
        Args:
            config_path: Путь к файлу конфигурации
            
        Raises:
            ConfigValidationError: При ошибках валидации
            FileNotFoundError: Если файл не найден
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._original_config: Dict[str, Any] = {}
        self._is_loaded = False
        
        self.load_config()
    
    def load_config(self) -> None:
        """
        Загрузка и валидация конфигурации
        
        Raises:
            ConfigValidationError: При ошибках валидации
            FileNotFoundError: Если файл не найден
        """
        try:
            # Проверка существования файла
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Файл конфигурации не найден: {self.config_path}")
            
            # Безопасная загрузка JSON
            with open(self.config_path, 'r', encoding='utf-8') as f:
                file_content = f.read().strip()
                if not file_content:
                    raise ConfigValidationError("Файл конфигурации пуст")
                
                self._original_config = json5.loads(file_content)
            
            # Устанавливаем task_type по умолчанию, если его нет
            if 'task_type' not in self._original_config:
                self._original_config['task_type'] = 'dialog_generation'
                logging.info("ℹ️ task_type не указан, установлен по умолчанию: dialog_generation")
            
            # Валидация схемы
            self._validate_schema()
            
            # Нормализация конфигурации
            self._normalize_config()
            
            # Дополнительная семантическая валидация
            self._semantic_validation()
            
            self._is_loaded = True
            logging.info(f"✅ Конфигурация успешно загружена из {self.config_path}")
            logging.info(f"📋 Режим работы: {self.get_task_type()}")
            
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Ошибка парсинга JSON: {e}")
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки конфигурации: {e}")
            raise
    
    def _validate_schema(self) -> None:
        """Валидация конфигурации по JSON Schema"""
        try:
            # Используем более простой подход для совместимости
            # Сначала проверяем базовую структуру
            validate(instance=self._original_config, schema=self.BASE_SCHEMA)
            
            # Затем проверяем специфичные секции в зависимости от task_type
            task_type = self._original_config.get('task_type', 'dialog_generation')
            
            if task_type == 'dialog_generation':
                # Проверяем наличие необходимых секций
                if 'generation' not in self._original_config:
                    raise ValidationError("Отсутствует секция 'generation' для режима dialog_generation")
                if 'prompt_templates' not in self._original_config:
                    raise ValidationError("Отсутствует секция 'prompt_templates' для режима dialog_generation")
                
                # Валидируем секции
                validate(instance=self._original_config, schema=self.DIALOG_GENERATION_SCHEMA)
                
            elif task_type == 'translation':
                # Проверяем наличие секции translation
                if 'translation' not in self._original_config:
                    raise ValidationError("Отсутствует секция 'translation' для режима translation")
                
                # Валидируем секцию translation
                validate(instance=self._original_config, schema=self.TRANSLATION_SCHEMA)
                
            else:
                raise ValidationError(f"Неизвестный task_type: {task_type}")
                
        except ValidationError as e:
            details = {
                "path": " → ".join(str(p) for p in e.path),
                "validator": e.validator,
                "value": e.instance
            }
            raise ConfigValidationError(
                f"Ошибка валидации конфигурации: {e.message}",
                details=details
            )
        except SchemaError as e:
            raise ConfigValidationError(f"Ошибка схемы валидации: {e}")
    
    def _normalize_config(self) -> None:
        """Нормализация и установка значений по умолчанию"""
        self.config = copy.deepcopy(self._original_config)
        
        # Установка значений по умолчанию для output
        output = self.config.setdefault("output", {})
        output.setdefault("filename", "output.jsonl")
        output.setdefault("max_file_size_mb", 100)
        output.setdefault("backup_count", 5)
        
        # Нормализация URL API
        api = self.config.setdefault("api", {})
        if "base_url" not in api:
            api["base_url"] = "https://api.openai.com/v1"
        
        # Нормализация в зависимости от режима
        task_type = self.get_task_type()
        
        if task_type == 'dialog_generation':
            self._normalize_dialog_config()
        elif task_type == 'translation':
            self._normalize_translation_config()
    
    def _normalize_dialog_config(self) -> None:
        """Нормализация конфигурации для режима диалогов"""
        generation = self.config.setdefault("generation", {})
        generation.setdefault("request_delay", 0.5)
        generation.setdefault("max_errors", 10)
        
        prompt_templates = self.config.setdefault("prompt_templates", {})
        prompt_templates.setdefault("templates", [])
        prompt_templates.setdefault("words", {})
    
    def _normalize_translation_config(self) -> None:
        """Нормализация конфигурации для режима перевода"""
        translation = self.config.setdefault("translation", {})
        translation.setdefault("checkpoint_file", "translation_progress.json")
        translation.setdefault("max_retries", 3)
        translation.setdefault("retry_delay_seconds", 5)
        translation.setdefault("threads", 2)
        translation.setdefault("temperature", 0.3)
        translation.setdefault("max_errors", 10)
        
        # Нормализация prompt_template
        prompt_template = translation.setdefault("prompt_template", {})
        prompt_template.setdefault("system", "Ты профессиональный переводчик. Переводи текст с сохранением смысла и стиля.")
        prompt_template.setdefault("user", "Переведи следующий текст на {target_language}:\n\n{original_text}\n\nПеревод:")
        
        # Нормализация dataset
        dataset = translation.setdefault("dataset", {})
        dataset.setdefault("source", "local")
        dataset.setdefault("split", "train")
        dataset.setdefault("fields", {})
        
        # Если указан только text, но не id
        if "id" not in dataset["fields"]:
            dataset["fields"]["id"] = None

    def _semantic_validation(self) -> None:
        """Семантическая валидация логических правил"""
        task_type = self.get_task_type()
        
        if task_type == 'dialog_generation':
            self._validate_dialog_semantics()
        elif task_type == 'translation':
            self._validate_translation_semantics()
    
    def _validate_dialog_semantics(self) -> None:
        """Семантическая валидация для режима диалогов"""
        generation = self.config["generation"]
        
        # Проверка диапазона temperature
        temp_min = generation["temperature"]["min"]
        temp_max = generation["temperature"]["max"]
        if temp_min > temp_max:
            raise ConfigValidationError(
                "min temperature не может быть больше max temperature",
                details={
                    "min_temperature": temp_min,
                    "max_temperature": temp_max,
                    "section": "generation.temperature"
                }
            )
        
        # Проверка диапазона lines
        lines_min = generation["dialog_lines"]["min"]
        lines_max = generation["dialog_lines"]["max"]
        if lines_min > lines_max:
            raise ConfigValidationError(
                "min lines не может быть больше max lines",
                details={
                    "min_lines": lines_min,
                    "max_lines": lines_max, 
                    "section": "generation.dialog_lines"
                }
            )
        
        # Проверка уникальности кодов языков
        language_codes = [lang["code"] for lang in generation["languages"]]
        if len(language_codes) != len(set(language_codes)):
            duplicates = [code for code in language_codes if language_codes.count(code) > 1]
            raise ConfigValidationError(
                "Коды языков должны быть уникальными",
                details={
                    "duplicate_codes": duplicates,
                    "section": "generation.languages"
                }
            )
        
        # Проверка шаблонов и слов
        templates = self.config["prompt_templates"]["templates"]
        word_banks = self.config["prompt_templates"]["words"]
        
        for i, template in enumerate(templates):
            placeholders = re.findall(r'\{(\w+)\}', template)
            for placeholder in placeholders:
                if placeholder not in word_banks:
                    raise ConfigValidationError(
                        f"Плейсхолдер в шаблоне не найден в word banks",
                        details={
                            "placeholder": placeholder,
                            "template_index": i,
                            "template": template,
                            "available_word_banks": list(word_banks.keys()),
                            "section": "prompt_templates"
                        }
                    )
    
    def _validate_translation_semantics(self) -> None:
        """Семантическая валидация для режима перевода"""
        translation = self.config["translation"]
        dataset = translation["dataset"]
        
        # Проверка существования локального файла
        if dataset["source"] == "local":
            if not os.path.exists(dataset["path"]):
                raise ConfigValidationError(
                    f"Локальный файл датасета не найден: {dataset['path']}"
                )
            
            # Проверка расширения файла
            import pathlib
            ext = pathlib.Path(dataset["path"]).suffix.lower()
            if ext not in ['.json', '.jsonl', '.csv']:
                raise ConfigValidationError(
                    f"Неподдерживаемый формат файла: {ext}. Поддерживаются: .json, .jsonl, .csv"
                )
        
        # Проверка параметров повторных попыток
        max_retries = translation.get("max_retries", 3)
        if max_retries < 1 or max_retries > 10:
            raise ConfigValidationError(
                "max_retries должен быть в диапазоне от 1 до 10",
                details={"max_retries": max_retries}
            )
        
        # Проверка температуры
        temperature = translation.get("temperature", 0.3)
        if temperature < 0.0 or temperature > 1.0:
            raise ConfigValidationError(
                "temperature должен быть в диапазоне от 0.0 до 1.0",
                details={"temperature": temperature}
            )
    
    def validate_config(self) -> bool:
        """
        Проверка валидности конфигурации
        
        Returns:
            True если конфигурация валидна
        """
        if not self._is_loaded:
            logging.warning("Конфигурация не загружена")
            return False
        
        try:
            self._semantic_validation()
            return True
        except ConfigValidationError as e:
            logging.error(f"Конфигурация невалидна: {e}")
            return False
    
    def get_task_type(self) -> str:
        """Получение типа задачи"""
        return self.config.get('task_type', 'dialog_generation')
    
    def is_translation_mode(self) -> bool:
        """Проверка, включен ли режим перевода"""
        return self.get_task_type() == 'translation'
    
    def is_dialog_mode(self) -> bool:
        """Проверка, включен ли режим диалогов"""
        return self.get_task_type() == 'dialog_generation'
    
    def get_api_config(self) -> Dict[str, Any]:
        """Получение конфигурации API"""
        return self.config.get("api", {}).copy()
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Получение конфигурации генерации (для режима диалогов)"""
        if self.is_dialog_mode():
            return self.config.get("generation", {}).copy()
        return {}
    
    def get_prompt_templates(self) -> Dict[str, Any]:
        """Получение шаблонов промптов (для режима диалогов)"""
        if self.is_dialog_mode():
            return self.config.get("prompt_templates", {}).copy()
        return {}
    
    def get_translation_config(self) -> Dict[str, Any]:
        """Получение конфигурации перевода"""
        if self.is_translation_mode():
            return self.config.get("translation", {}).copy()
        return {}
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Получение схемы вывода"""
        return self.config.get("output_schema", {}).copy()
    
    def get_output_config(self) -> Dict[str, Any]:
        """Получение конфигурации вывода"""
        return self.config.get("output", {}).copy()
    
    def get_languages(self) -> List[Dict[str, str]]:
        """Получение списка языков (для режима диалогов)"""
        if self.is_dialog_mode():
            return self.config.get("generation", {}).get("languages", []).copy()
        return []
    
    def get_thread_count(self) -> int:
        """Получение количества потоков"""
        if self.is_dialog_mode():
            return self.config.get("generation", {}).get("threads", 1)
        else:
            return self.config.get("translation", {}).get("threads", 2)
    
    def get_max_errors(self) -> int:
        """Получение максимального количества ошибок"""
        if self.is_dialog_mode():
            return self.config.get("generation", {}).get("max_errors", 10)
        else:
            return self.config.get("translation", {}).get("max_errors", 10)
    
    def get_temperature_range(self) -> Dict[str, float]:
        """Получение диапазона температур (для режима диалогов)"""
        if self.is_dialog_mode():
            return self.config.get("generation", {}).get("temperature", {"min": 0.5, "max": 0.8})
        return {"min": 0.3, "max": 0.3}
    
    def get_output_filename(self) -> str:
        """Получение имени выходного файла"""
        return self.config.get("output", {}).get("filename", "output.jsonl")
    
    def get_language_codes(self) -> List[str]:
        """Получение списка кодов языков (для режима диалогов)"""
        return [lang["code"] for lang in self.get_languages()]
    
    def get_language_name(self, code: str) -> Optional[str]:
        """Получение названия языка по коду (для режима диалогов)"""
        for lang in self.get_languages():
            if lang["code"] == code:
                return lang["name"]
        return None
    
    def reload_config(self) -> bool:
        """
        Перезагрузка конфигурации из файла
        
        Returns:
            True если перезагрузка успешна
        """
        try:
            self.load_config()
            return True
        except Exception as e:
            logging.error(f"Ошибка перезагрузки конфигурации: {e}")
            return False
    
    @property
    def is_loaded(self) -> bool:
        """Проверка загружена ли конфигурация"""
        return self._is_loaded
    
    def __getitem__(self, key: str) -> Any:
        """Доступ к конфигурации через квадратные скобки"""
        if not self._is_loaded:
            raise RuntimeError("Конфигурация не загружена")
        return self.config[key]
    
    def get(self, key: str, default: Any = None) -> Any:
        """Безопасный доступ к конфигурации"""
        if not self._is_loaded:
            return default
        return self.config.get(key, default)


# Синглтон экземпляр для глобального доступа
_config_instance: Optional[ConfigManager] = None

def get_config_manager(config_path: str = "config.json") -> ConfigManager:
    """
    Получение глобального экземпляра менеджера конфигурации
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        Экземпляр ConfigManager
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager(config_path)
    return _config_instance