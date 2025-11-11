"""
Универсальный валидатор JSON данных с гибкой проверкой структуры и содержания
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple


class UniversalJsonValidator:
    """
    Универсальный валидатор для проверки сгенерированных JSON данных
    """
    
    def __init__(self, output_schema: Dict[str, Any]):
        """
        Инициализация валидатора
        
        Args:
            output_schema: Схема ожидаемых выходных данных
        """
        self.output_schema = output_schema
        self.required_fields = output_schema.get('fields', [])
        self.example_structure = output_schema.get('example', {})
        
        self.prefix_patterns = [
            # Английские паттерны
            r'^(User|Assistant|Human|AI|Bot):\s*',
            r'^(user|assistant|human|ai|bot):\s*',
            r'^(USER|ASSISTANT|HUMAN|AI|BOT):\s*',
            
            # Русские паттерны
            r'^(Пользователь|Ассистент|Человек|ИИ|Бот):\s*',
            r'^(пользователь|ассистент|человек|ии|бот):\s*',
            r'^(ПОЛЬЗОВАТЕЛЬ|АССИСТЕНТ|ЧЕЛОВЕК|ИИ|БОТ):\s*',
            
            # Смешанные и другие варианты
            r'^\[.*?\]:\s*',
            r'^<.*?>:\s*',
            r'^【.*?】:\s*',
            r'^".*?":\s*',
            r"^'.*?':\s*",
        ]
        
        # Минимальные требования к данным
        self.min_fields = 1  # Минимум одно поле должно быть заполнено
        self.max_field_length = 10000
        self.min_field_length = 1  # Минимальная длина строкового поля
        
        logging.debug("✅ UniversalJsonValidator инициализирован")
    
    def filter_output_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фильтрация полей выходных данных согласно output_schema
        
        Args:
            data: Исходные данные
            
        Returns:
            Отфильтрованные данные только с разрешенными полями
        """
        try:
            filtered_data = {}
            
            for field in self.required_fields:
                if field in data:
                    filtered_data[field] = data[field]
                else:
                    # Для необязательных полей просто пропускаем
                    logging.debug(f"⚠️ Отсутствует поле '{field}' в выходных данных")
            
            return filtered_data
            
        except Exception as e:
            logging.error(f"❌ Ошибка фильтрации полей: {e}")
            return data
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Полная валидация данных
        
        Args:
            data: Данные для валидации
            
        Returns:
            True если данные валидны
        """
        try:
            # 1. Проверка базовой структуры
            if not self._validate_structure(data):
                return False
            
            # 2. Проверка что есть хотя бы некоторые поля из required_fields
            if not self._validate_required_fields_presence(data):
                return False
            
            # 3. Проверка типов и значений полей
            if not self._validate_fields_content(data):
                return False
            
            logging.debug("✅ Данные прошли валидацию")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка валидации данных: {e}")
            return False
    
    def _validate_structure(self, data: Dict[str, Any]) -> bool:
        """
        Проверка базовой структуры данных
        
        Args:
            data: Данные для проверки
            
        Returns:
            True если структура валидна
        """
        if not isinstance(data, dict):
            logging.warning("⚠️ Данные не являются словарем")
            return False
        
        if not data:
            logging.warning("⚠️ Пустые данные")
            return False
        
        return True
    
    def _validate_required_fields_presence(self, data: Dict[str, Any]) -> bool:
        """
        Проверка наличия хотя бы некоторых обязательных полей
        
        Args:
            data: Данные для проверки
            
        Returns:
            True если есть хотя бы одно поле из required_fields
        """
        if not self.required_fields:
            # Если required_fields не заданы, считаем что любые поля допустимы
            return True
        
        present_fields = [field for field in self.required_fields if field in data]
        
        if not present_fields:
            logging.warning(f"⚠️ Отсутствуют все поля из required_fields: {self.required_fields}")
            return False
        
        # Логируем какие поля найдены
        logging.debug(f"✅ Найдены поля: {present_fields}")
        return True
    
    def _validate_fields_content(self, data: Dict[str, Any]) -> bool:
        """
        Проверка содержания полей
        
        Args:
            data: Данные для проверки
            
        Returns:
            True если поля валидны
        """
        for field_name, field_value in data.items():
            # Пропускаем поля не из required_fields (если они есть)
            if self.required_fields and field_name not in self.required_fields:
                continue
                
            # Проверка типа поля
            if not self._validate_field_type(field_name, field_value):
                return False
            
            # Проверка длины поля
            if not self._validate_field_length(field_name, field_value):
                return False
        
        return True
    
    def _validate_field_type(self, field_name: str, field_value: Any) -> bool:
        """
        Проверка типа поля
        
        Args:
            field_name: Имя поля
            field_value: Значение поля
            
        Returns:
            True если тип валиден
        """
        # Базовые допустимые типы
        valid_types = (str, int, float, bool, list, dict, type(None))
        
        if not isinstance(field_value, valid_types):
            logging.warning(f"⚠️ Поле '{field_name}' имеет недопустимый тип: {type(field_value)}")
            return False
        
        return True
    
    def _validate_field_length(self, field_name: str, field_value: Any) -> bool:
        """
        Проверка длины поля
        
        Args:
            field_name: Имя поля
            field_value: Значение поля
            
        Returns:
            True если длина валидна
        """
        if isinstance(field_value, str):
            field_length = len(field_value.strip())
            if field_length < self.min_field_length:
                logging.warning(f"⚠️ Поле '{field_name}' слишком короткое: {field_length} символов")
                return False
            
            if field_length > self.max_field_length:
                logging.warning(f"⚠️ Поле '{field_name}' слишком длинное: {field_length} символов")
                return False
        
        elif isinstance(field_value, list):
            # Для списков проверяем каждый элемент
            for i, item in enumerate(field_value):
                if isinstance(item, str):
                    item_length = len(item.strip())
                    if item_length < self.min_field_length:
                        logging.warning(f"⚠️ Элемент {i} в поле '{field_name}' слишком короткий: {item_length} символов")
                        return False
                    
                    if item_length > self.max_field_length:
                        logging.warning(f"⚠️ Элемент {i} в поле '{field_name}' слишком длинный: {item_length} символов")
                        return False
        
        return True
    
    def sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Очистка данных - удаление лишних пробелов и т.д.
        
        Args:
            data: Данные для очистки
            
        Returns:
            Очищенные данные
        """
        try:
            cleaned_data = {}
            
            for field_name, field_value in data.items():
                # Пропускаем поля не из required_fields (если они есть)
                if self.required_fields and field_name not in self.required_fields:
                    continue
                    
                cleaned_data[field_name] = self._clean_field_value(field_value)
            
            return cleaned_data
            
        except Exception as e:
            logging.error(f"❌ Ошибка очистки данных: {e}")
            return data
    
    def _clean_field_value(self, field_value: Any) -> Any:
        """
        Очистка значения поля
        
        Args:
            field_value: Значение для очистки
            
        Returns:
            Очищенное значение
        """
        if isinstance(field_value, str):
            # Убираем лишние пробелы
            cleaned = field_value.strip()
            
            # Убираем кавычки в начале и конце если они есть
            cleaned = re.sub(r'^["\'](.*)["\']$', r'\1', cleaned)
            
            return cleaned
        
        elif isinstance(field_value, list):
            # Рекурсивно очищаем элементы списка
            return [self._clean_field_value(item) for item in field_value]
        
        elif isinstance(field_value, dict):
            # Рекурсивно очищаем значения словаря
            return {key: self._clean_field_value(value) for key, value in field_value.items()}
        
        else:
            return field_value
    
    def sanitize_replicas(self, dialog_replicas: List[str]) -> List[str]:
        """
        Очистка реплик от префиксов и лишних символов
        
        Args:
            dialog_replicas: Список реплик для очистки
            
        Returns:
            Очищенный список реплик
        """
        cleaned_replicas = []
        
        for replica in dialog_replicas:
            cleaned_replica = self._clean_replica(replica)
            if cleaned_replica.strip():  # Не добавляем пустые реплики
                cleaned_replicas.append(cleaned_replica)
        
        return cleaned_replicas
    
    def _clean_replica(self, replica: str) -> str:
        """
        Очистка одной реплики
        
        Args:
            replica: Реплика для очистки
            
        Returns:
            Очищенная реплика
        """
        cleaned_replica = replica
        
        # Удаляем префиксы
        for pattern in self.prefix_patterns:
            cleaned_replica = re.sub(pattern, '', cleaned_replica, flags=re.IGNORECASE)
        
        # Убираем лишние пробелы
        cleaned_replica = cleaned_replica.strip()
        
        # Убираем кавычки в начале и конце если они есть
        cleaned_replica = re.sub(r'^["\'](.*)["\']$', r'\1', cleaned_replica)
        
        return cleaned_replica

    def validate_json_syntax(self, json_string: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Проверка синтаксиса JSON
        
        Args:
            json_string: JSON строка для проверки
            
        Returns:
            Кортеж (успех, распарсенные данные)
        """
        try:
            data = json.loads(json_string)
            return True, data
        except json.JSONDecodeError as e:
            logging.warning(f"⚠️ Ошибка синтаксиса JSON: {e}")
            return False, None
        except Exception as e:
            logging.error(f"❌ Неизвестная ошибка парсинга JSON: {e}")
            return False, None
    
    def get_validation_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Получение детального отчета о валидации
        
        Args:
            data: Данные для проверки
            
        Returns:
            Отчет о валидации
        """
        report = {
            'is_valid': False,
            'errors': [],
            'warnings': [],
            'stats': {},
            'present_fields': []
        }
        
        try:
            # Проверка структуры
            if not self._validate_structure(data):
                report['errors'].append("Невалидная структура данных")
                return report
            
            # Соберем статистику
            present_fields = []
            total_chars = 0
            field_stats = {}
            
            for field_name, field_value in data.items():
                if self.required_fields and field_name in self.required_fields:
                    present_fields.append(field_name)
                
                # Статистика по длине
                if isinstance(field_value, str):
                    field_length = len(field_value)
                    total_chars += field_length
                    field_stats[field_name] = {'type': 'str', 'length': field_length}
                elif isinstance(field_value, list):
                    field_length = len(field_value)
                    field_stats[field_name] = {'type': 'list', 'length': field_length}
                elif isinstance(field_value, (int, float)):
                    field_stats[field_name] = {'type': 'number', 'value': field_value}
                elif isinstance(field_value, bool):
                    field_stats[field_name] = {'type': 'bool', 'value': field_value}
                elif isinstance(field_value, dict):
                    field_stats[field_name] = {'type': 'dict', 'keys': list(field_value.keys())}
            
            report['present_fields'] = present_fields
            report['stats'] = {
                'total_fields': len(data),
                'required_fields_present': len(present_fields),
                'total_characters': total_chars,
                'field_stats': field_stats
            }
            
            # Проверка обязательных полей
            if self.required_fields:
                missing_fields = [f for f in self.required_fields if f not in data]
                if missing_fields:
                    report['warnings'].append(f"Отсутствуют некоторые поля: {missing_fields}")
            
            # Финальная проверка
            report['is_valid'] = self.validate_data(data)
            
        except Exception as e:
            report['errors'].append(f"Ошибка валидации: {e}")
        
        return report
    
    def get_validator_stats(self) -> Dict[str, Any]:
        """
        Получение статистики валидатора
        
        Returns:
            Словарь со статистикой
        """
        return {
            'required_fields': self.required_fields,
            'min_fields': self.min_fields,
            'min_field_length': self.min_field_length,
            'max_field_length': self.max_field_length
        }