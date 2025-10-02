"""
Генератор случайных тем на основе шаблонов и словарей слов
"""

import logging
import random
import re
from typing import List, Dict, Any
from threading import RLock


class ThemeGenerator:
    """
    Генератор тем диалогов с использованием шаблонов и словарей слов
    """
    
    def __init__(self, templates: List[str], word_banks: Dict[str, List[str]]):
        """
        Инициализация генератора тем
        
        Args:
            templates: Список шаблонов тем с плейсхолдерами
            word_banks: Словари слов для заполнения плейсхолдеров
        """
        self.templates = templates
        self.word_banks = word_banks
        self._lock = RLock()  # Для потокобезопасности
        
        # Валидация при инициализации
        self._validate_components()
        
        logging.debug("🎨 ThemeGenerator инициализирован")
    
    def _validate_components(self) -> None:
        """
        Валидация шаблонов и словарей слов
        """
        if not self.templates:
            raise ValueError("Список шаблонов не может быть пустым")
        
        if not self.word_banks:
            raise ValueError("Словари слов не могут быть пустыми")
        
        # Проверяем что все плейсхолдеры в шаблонах есть в словарях
        for i, template in enumerate(self.templates):
            placeholders = self._extract_placeholders(template)
            for placeholder in placeholders:
                if placeholder not in self.word_banks:
                    raise ValueError(
                        f"Плейсхолдер '{placeholder}' в шаблоне {i} не найден в словарях слов. "
                        f"Доступные словари: {list(self.word_banks.keys())}"
                    )
        
        # Проверяем что словари не пустые
        for key, words in self.word_banks.items():
            if not words:
                raise ValueError(f"Словарь '{key}' не может быть пустым")
    
    def _extract_placeholders(self, template: str) -> List[str]:
        """
        Извлечение плейсхолдеров из шаблона
        
        Args:
            template: Шаблон темы
            
        Returns:
            Список плейсхолдеров
        """
        return re.findall(r'\{(\w+)\}', template)
    
    def generate_theme(self) -> str:
        """
        Генерация случайной темы
        
        Returns:
            Сгенерированная тема
        """
        with self._lock:
            try:
                # Выбираем случайный шаблон
                template = random.choice(self.templates)
                
                # Заполняем плейсхолдеры
                theme = template
                placeholders = self._extract_placeholders(template)
                
                for placeholder in placeholders:
                    if placeholder in self.word_banks:
                        word = random.choice(self.word_banks[placeholder])
                        theme = theme.replace(f"{{{placeholder}}}", word, 1)
                
                # Дополнительная проверка на оставшиеся плейсхолдеры
                remaining_placeholders = self._extract_placeholders(theme)
                if remaining_placeholders:
                    logging.warning(
                        f"⚠️ В теме остались незаполненные плейсхолдеры: {remaining_placeholders}. "
                        f"Тема: '{theme}'"
                    )
                    # Заполняем оставшиеся плейсхолдеры случайными словами
                    for placeholder in remaining_placeholders:
                        fallback_word = "обсуждение"  # Запасной вариант
                        theme = theme.replace(f"{{{placeholder}}}", fallback_word, 1)
                
                logging.debug(f"🎨 Сгенерирована тема: {theme}")
                return theme
                
            except Exception as e:
                logging.error(f"❌ Ошибка генерации темы: {e}")
                # Возвращаем запасную тему при ошибке
                return "Обсуждение важных вопросов"
    
    def get_available_templates_count(self) -> int:
        """
        Получение количества доступных шаблонов
        
        Returns:
            Количество шаблонов
        """
        return len(self.templates)
    
    def get_word_bank_stats(self) -> Dict[str, int]:
        """
        Получение статистики по словарям слов
        
        Returns:
            Словарь с количеством слов в каждом словаре
        """
        return {key: len(words) for key, words in self.word_banks.items()}
    
    def validate_template(self, template: str) -> bool:
        """
        Проверка валидности шаблона
        
        Args:
            template: Шаблон для проверки
            
        Returns:
            True если шаблон валиден
        """
        try:
            placeholders = self._extract_placeholders(template)
            for placeholder in placeholders:
                if placeholder not in self.word_banks:
                    return False
            return True
        except Exception:
            return False
    
    def add_template(self, template: str) -> bool:
        """
        Добавление нового шаблона
        
        Args:
            template: Новый шаблон
            
        Returns:
            True если шаблон успешно добавлен
        """
        with self._lock:
            try:
                if self.validate_template(template):
                    self.templates.append(template)
                    logging.debug(f"✅ Добавлен новый шаблон: {template}")
                    return True
                else:
                    logging.warning(f"⚠️ Не удалось добавить шаблон: {template}")
                    return False
            except Exception as e:
                logging.error(f"❌ Ошибка добавления шаблона: {e}")
                return False
    
    def add_words_to_bank(self, bank_name: str, words: List[str]) -> bool:
        """
        Добавление слов в словарь
        
        Args:
            bank_name: Название словаря
            words: Список слов для добавления
            
        Returns:
            True если слова успешно добавлены
        """
        with self._lock:
            try:
                if bank_name not in self.word_banks:
                    self.word_banks[bank_name] = []
                
                # Добавляем только уникальные слова
                existing_words = set(self.word_banks[bank_name])
                new_words = [word for word in words if word not in existing_words]
                
                self.word_banks[bank_name].extend(new_words)
                
                logging.debug(f"✅ Добавлено {len(new_words)} слов в словарь '{bank_name}'")
                return True
                
            except Exception as e:
                logging.error(f"❌ Ошибка добавления слов в словарь '{bank_name}': {e}")
                return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение общей статистики генератора
        
        Returns:
            Словарь со статистикой
        """
        return {
            'templates_count': self.get_available_templates_count(),
            'word_banks': self.get_word_bank_stats(),
            'total_combinations': self._calculate_total_combinations()
        }
    
    def _calculate_total_combinations(self) -> int:
        """
        Расчет общего количества возможных комбинаций тем
        
        Returns:
            Примерное количество комбинаций
        """
        total = 0
        for template in self.templates:
            placeholders = self._extract_placeholders(template)
            combinations = 1
            for placeholder in placeholders:
                if placeholder in self.word_banks:
                    combinations *= len(self.word_banks[placeholder])
            total += combinations
        return total