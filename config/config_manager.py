"""
Менеджер конфигурации с полной валидацией и безопасной загрузкой
"""

import json
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
    """
    
    # JSON Schema для валидации конфигурации
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["generation", "api", "prompt_templates", "output_schema"],
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
                                "code": {"type": "string", "pattern": "^[a-z]{2}$"},
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
            "api": {
                "type": "object",
                "required": ["model", "timeout", "max_tokens"],
                "properties": {
                    "base_url": {"type": "string"},
                    "api_key": {"type": "string"},
                    "model": {"type": "string", "minLength": 1},
                    "timeout": {"type": "integer", "minimum": 10, "maximum": 300},
                    "max_tokens": {"type": "integer", "minimum": 100, "maximum": 8000}
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
                
                self._original_config = json.loads(file_content)
            
            # Валидация схемы
            self._validate_schema()
            
            # Нормализация конфигурации
            self._normalize_config()
            
            # Дополнительная семантическая валидация
            self._semantic_validation()
            
            self._is_loaded = True
            logging.info(f"✅ Конфигурация успешно загружена из {self.config_path}")
            
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Ошибка парсинга JSON: {e}")
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки конфигурации: {e}")
            raise
    
    def _validate_schema(self) -> None:
        """Валидация конфигурации по JSON Schema"""
        try:
            validate(instance=self._original_config, schema=self.CONFIG_SCHEMA)
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
        
        # Установка значений по умолчанию для generation
        generation = self.config.setdefault("generation", {})
        generation.setdefault("request_delay", 0.5)
        generation.setdefault("max_errors", 10)
        
        # Установка значений по умолчанию для output
        output = self.config.setdefault("output", {})
        output.setdefault("filename", "dialogues.jsonl")
        output.setdefault("max_file_size_mb", 100)
        output.setdefault("backup_count", 5)
        
        # Нормализация URL API
        api = self.config["api"]
        if "base_url" not in api:
            api["base_url"] = "https://api.openai.com/v1"
    
    def _semantic_validation(self) -> None:
        """Семантическая валидация логических правил"""
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
    
    def get_api_config(self) -> Dict[str, Any]:
        """Получение конфигурации API"""
        return self.config.get("api", {}).copy()
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Получение конфигурации генерации"""
        return self.config.get("generation", {}).copy()
    
    def get_prompt_templates(self) -> Dict[str, Any]:
        """Получение шаблонов промптов"""
        return self.config.get("prompt_templates", {}).copy()
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Получение схемы вывода"""
        return self.config.get("output_schema", {}).copy()
    
    def get_output_config(self) -> Dict[str, Any]:
        """Получение конфигурации вывода"""
        return self.config.get("output", {}).copy()
    
    def get_languages(self) -> List[Dict[str, str]]:
        """Получение списка языков"""
        return self.config.get("generation", {}).get("languages", []).copy()
    
    def get_thread_count(self) -> int:
        """Получение количества потоков"""
        return self.config.get("generation", {}).get("threads", 1)
    
    def get_output_filename(self) -> str:
        """Получение имени выходного файла"""
        return self.config.get("output", {}).get("filename", "dialogues.jsonl")
    
    def get_language_codes(self) -> List[str]:
        """Получение списка кодов языков"""
        return [lang["code"] for lang in self.get_languages()]
    
    def get_language_name(self, code: str) -> Optional[str]:
        """Получение названия языка по коду"""
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