"""
Валидатор диалогов с проверкой структуры, содержания и качества данных
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple


class DialogValidator:
    """
    Валидатор для проверки сгенерированных диалогов
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
        
        # Паттерны для очистки реплик
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
        
        # Минимальные требования к диалогу
        self.min_replicas = 4
        self.max_replicas = 100
        self.min_replica_length = 10
        self.max_replica_length = 10000
        
        logging.debug("✅ DialogValidator инициализирован")
    
    def filter_output_fields(self, dialog_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фильтрация полей выходных данных согласно output_schema
        
        Args:
            dialog_data: Исходные данные диалога
            
        Returns:
            Отфильтрованные данные только с разрешенными полями
        """
        try:
            filtered_data = {}
            
            for field in self.required_fields:
                if field in dialog_data:
                    filtered_data[field] = dialog_data[field]
                else:
                    # Если поле обязательное, но отсутствует - логируем предупреждение
                    logging.warning(f"⚠️ Отсутствует поле '{field}' в выходных данных")
            
            return filtered_data
            
        except Exception as e:
            logging.error(f"❌ Ошибка фильтрации полей: {e}")
            # Возвращаем оригинальные данные при ошибке
            return dialog_data
    
    def validate_dialog(self, dialog_data: Dict[str, Any]) -> bool:
        """
        Полная валидация диалога
        """
        try:
            # 1. Проверка базовой структуры
            if not self._validate_structure(dialog_data):
                return False
            
            # 2. Проверка обязательных полей
            if not self._validate_required_fields(dialog_data):
                return False
            
            # 3. Проверка поля dialog
            if 'dialog' not in dialog_data:
                logging.warning("⚠️ Отсутствует поле 'dialog'")
                return False
            
            dialog_replicas = dialog_data['dialog']
            
            # 4. Проверка типа и длины диалога
            if not self._validate_dialog_type_and_length(dialog_replicas):
                return False
            
            # 5. Проверка содержания реплик
            if not self._validate_replicas_content(dialog_replicas):
                return False
            
            logging.debug("✅ Диалог прошел валидацию")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка валидации диалога: {e}")
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
    
    def _validate_required_fields(self, data: Dict[str, Any]) -> bool:
        """
        Проверка обязательных полей
        
        Args:
            data: Данные для проверки
            
        Returns:
            True если все обязательные поля присутствуют
        """
        missing_fields = []
        
        for field in self.required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            logging.warning(f"⚠️ Отсутствуют обязательные поля: {missing_fields}")
            return False
        
        return True
    
    def _validate_dialog_type_and_length(self, dialog_replicas: List[str]) -> bool:
        """
        Проверка типа и длины диалога
        
        Args:
            dialog_replicas: Список реплик
            
        Returns:
            True если тип и длина валидны
        """
        # Проверка типа
        if not isinstance(dialog_replicas, list):
            logging.warning("⚠️ Поле 'dialog' не является списком")
            return False
        
        # Проверка длины
        replica_count = len(dialog_replicas)
        if replica_count < self.min_replicas:
            logging.warning(f"⚠️ Слишком мало реплик: {replica_count} (минимум {self.min_replicas})")
            return False
        
        if replica_count > self.max_replicas:
            logging.warning(f"⚠️ Слишком много реплик: {replica_count} (максимум {self.max_replicas})")
            return False
        
        return True
    
    def _validate_replicas_content(self, dialog_replicas: List[str]) -> bool:
        """
        Проверка содержания реплик
        
        Args:
            dialog_replicas: Список реплик
            
        Returns:
            True если реплики валидны
        """
        for i, replica in enumerate(dialog_replicas):
            # Проверка типа реплики
            if not isinstance(replica, str):
                logging.warning(f"⚠️ Реплика {i} не является строкой: {type(replica)}")
                return False
            
            # Проверка длины реплики
            replica_length = len(replica.strip())
            if replica_length < self.min_replica_length:
                logging.warning(f"⚠️ Реплика {i} слишком короткая: {replica_length} символов")
                return False
            
            if replica_length > self.max_replica_length:
                logging.warning(f"⚠️ Реплика {i} слишком длинная: {replica_length} символов")
                return False
            
            # Проверка на пустую реплику после очистки
            cleaned_replica = self._clean_replica(replica)
            if not cleaned_replica.strip():
                logging.warning(f"⚠️ Реплика {i} пустая после очистки")
                return False
        
        return True
    
    def _validate_replica_alternation(self, dialog_replicas: List[str]) -> bool:
        """
        Проверка чередования реплик (эвристическая проверка)
        
        Args:
            dialog_replicas: Список реплик
            
        Returns:
            True если чередование выглядит естественным
        """
        if len(dialog_replicas) < 4:
            return True
        
        # Проверяем что реплики не слишком похожи друг на друга
        similarity_threshold = 0.8
        similar_pairs = 0
        
        for i in range(len(dialog_replicas) - 1):
            similarity = self._calculate_similarity(
                dialog_replicas[i], 
                dialog_replicas[i + 1]
            )
            if similarity > similarity_threshold:
                similar_pairs += 1
                logging.debug(f"⚠️ Высокая схожесть реплик {i} и {i+1}: {similarity:.2f}")
        
        # Если больше 30% пар реплик слишком похожи - возможна проблема
        max_similar_pairs = len(dialog_replicas) * 0.3
        if similar_pairs > max_similar_pairs:
            logging.warning(f"⚠️ Слишком много похожих реплик: {similar_pairs} пар")
            return False
        
        return True
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Расчет схожести двух текстов (простая эвристика)
        
        Args:
            text1: Первый текст
            text2: Второй текст
            
        Returns:
            Коэффициент схожести от 0 до 1
        """
        # Приводим к нижнему регистру и разбиваем на слова
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Рассчитываем коэффициент Жаккара
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
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
    
    def get_validation_report(self, dialog_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Получение детального отчета о валидации
        
        Args:
            dialog_data: Данные диалога для проверки
            
        Returns:
            Отчет о валидации
        """
        report = {
            'is_valid': False,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        try:
            # Проверка структуры
            if not self._validate_structure(dialog_data):
                report['errors'].append("Невалидная структура данных")
                return report
            
            # Проверка обязательных полей
            missing_fields = [f for f in self.required_fields if f not in dialog_data]
            if missing_fields:
                report['errors'].append(f"Отсутствуют обязательные поля: {missing_fields}")
            
            # Статистика
            if 'dialog' in dialog_data and isinstance(dialog_data['dialog'], list):
                replicas = dialog_data['dialog']
                report['stats'] = {
                    'replica_count': len(replicas),
                    'total_characters': sum(len(r) for r in replicas),
                    'avg_replica_length': sum(len(r) for r in replicas) / len(replicas) if replicas else 0,
                    'cleaned_replica_count': len(self.sanitize_replicas(replicas))
                }
            
            # Финальная проверка
            report['is_valid'] = self.validate_dialog(dialog_data)
            
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
            'min_replicas': self.min_replicas,
            'max_replicas': self.max_replicas,
            'min_replica_length': self.min_replica_length,
            'max_replica_length': self.max_replica_length,
            'prefix_patterns_count': len(self.prefix_patterns)
        }