"""
Движок для создания промптов с поддержкой multiple языков и динамических параметров
"""

import logging
import json
from typing import Dict, Any, Optional
from string import Template
import re


class PromptEngine:
    """
    Движок для создания промптов с валидацией и шаблонизацией
    """
    
    def __init__(self, 
                 base_template: str, 
                 output_schema: Dict[str, Any],
                 line_range: Dict[str, int]):
        """
        Инициализация движка промптов
        
        Args:
            base_template: Базовый шаблон промпта
            output_schema: Схема выходных данных
            line_range: Диапазон количества реплик
        """
        self.base_template = base_template
        self.output_schema = output_schema
        self.line_range = line_range
        
        # Валидация при инициализации
        self._validate_components()
        
        # Подготовка примера выходных данных
        self._prepare_output_example()
        
        logging.debug("💬 PromptEngine инициализирован")
    
    def _validate_components(self) -> None:
        """
        Валидация компонентов движка
        """
        if not self.base_template.strip():
            raise ValueError("Базовый шаблон не может быть пустым")
        
        if 'example' not in self.output_schema:
            raise ValueError("В output_schema должен быть пример (example)")
        
        if 'min' not in self.line_range or 'max' not in self.line_range:
            raise ValueError("line_range должен содержать min и max значения")
        
        if self.line_range['min'] > self.line_range['max']:
            raise ValueError("min не может быть больше max в line_range")
        
        if self.line_range['min'] < 2:
            raise ValueError("min lines не может быть меньше 2")
    
    def _prepare_output_example(self) -> None:
        """
        Подготовка примера выходных данных для промпта
        """
        try:
            # Создаем читабельный пример JSON
            self.output_example = json.dumps(
                self.output_schema['example'], 
                ensure_ascii=False, 
                indent=2
            )
        except Exception as e:
            logging.error(f"❌ Ошибка подготовки output example: {e}")
            # Резервный пример
            self.output_example = json.dumps({
                "theme": "Пример темы",
                "dialog": ["Реплика 1", "Реплика 2"],
                "language": "ru"
            }, ensure_ascii=False, indent=2)
    
    def build_prompt(self, 
                    language_code: str, 
                    language_name: str, 
                    theme: str) -> str:
        """
        Создание промпта для генерации диалога
        
        Args:
            language_code: Код языка (ru, en, etc.)
            language_name: Локализованное название языка
            theme: Тема диалога
            
        Returns:
            Готовый промпт
        """
        try:
            # Параметры для подстановки в шаблон
            template_params = {
                'language_name': language_name,
                'theme': theme,
                'min_lines': self.line_range['min'],
                'max_lines': self.line_range['max'],
                'output_example': self.output_example
            }
            
            # Используем безопасную подстановку через Template
            prompt_template = Template(self.base_template)
            prompt = prompt_template.safe_substitute(template_params)
            
            # Добавляем секцию с форматом ответа
            format_section = self._build_format_section()
            full_prompt = f"{prompt}\n\n{format_section}"
            
            logging.debug(f"💬 Создан промпт для {language_code} (тема: {theme})")
            return full_prompt
            
        except Exception as e:
            logging.error(f"❌ Ошибка создания промпта для {language_code}: {e}")
            # Резервный промпт
            return self._build_fallback_prompt(language_name, theme)
    
    def _build_format_section(self) -> str:
        """
        Создание секции с форматом ответа
        
        Returns:
            Строка с требованиями к формату
        """
        required_fields = self.output_schema.get('fields', [])
        
        format_section = [
            "ФОРМАТ ОТВЕТА:",
            "Ты должен вернуть JSON объект со следующей структурой:",
            self.output_example,
        ]
        
        if required_fields:
            format_section.append(f"Обязательные поля: {', '.join(required_fields)}")
        
        format_section.extend([
            "Убедись что:",
            f"- Количество реплик: {self.line_range['min']}-{self.line_range['max']}",
            "- Все реплики в массиве 'dialog'",
            "- Не используешь префиксы (User:, Assistant: и т.д.)",
            "- JSON валиден и правильно экранирован"
        ])
        
        return "\n".join(format_section)
    
    def _build_fallback_prompt(self, language_name: str, theme: str) -> str:
        """
        Создание резервного промпта при ошибках
        
        Args:
            language_name: Название языка
            theme: Тема диалога
            
        Returns:
            Простой промпт
        """
        return f"""
Создай естественный диалог на {language_name} языке на тему: "{theme}"

Требования:
- Диалог между двумя персонажами
- {self.line_range['min']}-{self.line_range['max']} реплик
- Естественный и engaging разговор
- Без префиксов перед репликами
- Конкретные примеры и объяснения

Формат ответа (JSON):
{{
    "language": "{language_name}",
    "theme": "название темы на нужном языке",
    "dialog": ["реплика 1", "реплика 2", ...]
}}

Верни только JSON без дополнительного текста.
"""
    
    def validate_prompt_length(self, prompt: str) -> bool:
        """
        Проверка длины промпта
        
        Args:
            prompt: Промпт для проверки
            
        Returns:
            True если длина приемлема
        """
        # Примерная оценка токенов (1 токен ≈ 4 символа для английского)
        estimated_tokens = len(prompt) // 4
        
        # Максимальная длина промпта для большинства моделей ~4000 токенов
        if estimated_tokens > 3500:
            logging.warning(f"⚠️ Длинный промпт: ~{estimated_tokens} токенов")
            return False
        
        return True
    
    def get_prompt_stats(self, prompt: str) -> Dict[str, Any]:
        """
        Получение статистики промпта
        
        Args:
            prompt: Промпт для анализа
            
        Returns:
            Словарь со статистикой
        """
        lines = prompt.split('\n')
        words = prompt.split()
        
        return {
            'characters': len(prompt),
            'lines': len(lines),
            'words': len(words),
            'estimated_tokens': len(prompt) // 4,
            'has_format_section': 'ФОРМАТ ОТВЕТА:' in prompt,
            'has_json_example': self.output_example[:50] in prompt
        }
    
    def add_custom_instructions(self, prompt: str, instructions: str) -> str:
        """
        Добавление кастомных инструкций к промпту
        
        Args:
            prompt: Исходный промпт
            instructions: Дополнительные инструкции
            
        Returns:
            Обновленный промпт
        """
        if not instructions.strip():
            return prompt
        
        # Вставляем инструкции перед секцией формата
        if "ФОРМАТ ОТВЕТА:" in prompt:
            sections = prompt.split("ФОРМАТ ОТВЕТА:")
            updated_prompt = f"{sections[0]}\n\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ:\n{instructions}\n\nФОРМАТ ОТВЕТА:{sections[1]}"
            return updated_prompt
        else:
            return f"{prompt}\n\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ:\n{instructions}"
    
    def create_system_prompt(self) -> str:
        """
        Создание системного промпта для модели
        
        Returns:
            Системный промпт
        """
        return """Ты - эксперт по созданию естественных и образовательных диалогов. 
Твоя задача - создавать engaging диалоги на заданные темы, следуя строго указанному формату.

Ключевые принципы:
1. Диалоги должны быть логичным, естественными и реалистичными
2. Используй конкретные примеры и объяснения
3. Следуй строго указанному формату вывода
4. Не добавляй дополнительный текст кроме запрошенного JSON
5. Убедись что JSON валиден и правильно сформирован"""
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """
        Получение статистики движка
        
        Returns:
            Словарь со статистикой
        """
        return {
            'base_template_length': len(self.base_template),
            'output_example_length': len(self.output_example),
            'line_range': self.line_range,
            'output_fields': self.output_schema.get('fields', [])
        }