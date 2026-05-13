"""
Рабочий поток для перевода текстов из датасета
Поддерживает кастомные системные и пользовательские промпты
"""

import threading
import time
import logging
import random
from typing import Dict, Any, Optional, List, Callable

from core.api_client import APIClient
from core.validator import UniversalJsonValidator
from storage.thread_safe_writer import ThreadSafeWriter


class TranslationWorkerThread(threading.Thread):
    """
    Рабочий поток для перевода текстов на целевой язык
    Поддерживает настраиваемые промпты из конфига
    """
    
    def __init__(self, 
                 worker_id: int,
                 config: Dict[str, Any],
                 task_queue,
                 task_manager,
                 writer: ThreadSafeWriter,
                 stats_callback: Optional[Callable[[bool], None]] = None):
        """
        Инициализация воркера перевода
        
        Args:
            worker_id: Уникальный идентификатор потока
            config: Конфигурация приложения
            task_queue: Очередь задач (id, text)
            task_manager: Менеджер задач для чекпоинтов
            writer: Потокобезопасный writer для записи результатов
        """
        super().__init__(name=f"Translator-{worker_id}", daemon=True)
        
        self.worker_id = worker_id
        self.config = config
        self.task_queue = task_queue
        self.task_manager = task_manager
        self.writer = writer
        self.stats_callback = stats_callback
        
        # Состояние потока
        self._stop_requested = False
        self.is_working = False
        self.generated_count = 0
        self.error_count = 0
        self.consecutive_errors = 0
        self.max_consecutive_errors = config.get('translation', {}).get('max_errors', 10)
        
        # Параметры перевода
        translation_config = config.get('translation', {})
        self.target_language = translation_config.get('target_language', 'tokipona')
        self.temperature = translation_config.get('temperature', 0.3)
        
        # Загружаем шаблоны промптов из конфига
        self.prompt_template = translation_config.get('prompt_template', {})
        self.system_prompt = self.prompt_template.get(
            'system', 
            "Ты профессиональный переводчик. Переводи текст с сохранением смысла и стиля."
        )
        self.user_prompt_template = self.prompt_template.get(
            'user',
            "Переведи следующий текст на {target_language}:\n\n{original_text}\n\nПеревод:"
        )
        
        # Инициализация компонентов
        self._init_components()
        
        logging.debug(f"🔧 Translator {worker_id} инициализирован (цель: {self.target_language})")
        logging.debug(f"📝 System prompt: {self.system_prompt[:50]}...")
        logging.debug(f"📝 User template: {self.user_prompt_template[:50]}...")
    
    def _init_components(self) -> None:
        """Инициализация всех компонентов потока"""
        try:
            # API клиент
            self.api_client = APIClient(self.config['api'])
            
            # Валидатор данных
            self.validator = UniversalJsonValidator(self.config['output_schema'])
            
        except Exception as e:
            logging.error(f"❌ Translator {self.worker_id}: Ошибка инициализации компонентов: {e}")
            raise
    
    def run(self) -> None:
        """
        Главный цикл выполнения потока
        """
        logging.info(f"🚀 Translator {self.worker_id} запущен")
        
        while not self._stop_requested and self.consecutive_errors < self.max_consecutive_errors:
            try:
                self.is_working = True
                
                # Получаем задачу из очереди с таймаутом
                try:
                    task = self.task_queue.get(timeout=2)
                except:
                    # Пустая очередь, продолжаем ожидание
                    time.sleep(0.5)
                    continue
                
                # Проверка на сигнал остановки
                if task is None:
                    logging.debug(f"🛑 Translator {self.worker_id}: получен сигнал остановки")
                    break
                
                task_id, original_text = task
                success = self._process_translation(task_id, original_text)
                
                if success:
                    self.generated_count += 1
                    self.consecutive_errors = 0
                    logging.debug(f"✅ Translator {self.worker_id}: успешный перевод #{self.generated_count} (id: {task_id})")
                else:
                    self.error_count += 1
                    self.consecutive_errors += 1
                    logging.warning(f"⚠️ Translator {self.worker_id}: ошибка перевода (последовательных: {self.consecutive_errors})")
                
                # Отмечаем задачу как обработанную
                self.task_queue.task_done()
                
                # Случайная небольшая пауза между задачами
                if not self._stop_requested:
                    delay = random.uniform(0.3, 1.0)
                    time.sleep(delay)
                    
            except Exception as e:
                self.error_count += 1
                self.consecutive_errors += 1
                logging.error(f"❌ Translator {self.worker_id}: критическая ошибка в цикле: {e}")
                time.sleep(2)  # Пауза при критической ошибке
        
        # Завершение работы
        self.is_working = False
        
        if self._stop_requested:
            logging.info(f"🔚 Translator {self.worker_id}: остановлен по запросу")
        elif self.consecutive_errors >= self.max_consecutive_errors:
            logging.error(f"💥 Translator {self.worker_id}: превышено максимальное количество ошибок ({self.max_consecutive_errors})")
        else:
            logging.info(f"🔚 Translator {self.worker_id}: завершил работу")
        
        logging.info(f"📊 Translator {self.worker_id}: статистика - успешно: {self.generated_count}, ошибок: {self.error_count}")
    
    def _build_messages(self, original_text: str) -> List[Dict[str, str]]:
        """
        Построение списка сообщений для API
        
        Args:
            original_text: Исходный текст для перевода
            
        Returns:
            Список сообщений в формате [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        messages = []
        
        # Добавляем системный промпт, если он не пустой
        if self.system_prompt and self.system_prompt.strip():
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })
        
        # Формируем пользовательский промпт
        user_content = self.user_prompt_template.format(
            target_language=self.target_language,
            original_text=original_text
        )
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def _process_translation(self, task_id: Any, original_text: str) -> bool:
        """
        Обработка одного перевода
        
        Args:
            task_id: ID задачи
            original_text: Исходный текст для перевода
            
        Returns:
            True если перевод успешен
        """
        try:
            # Строим сообщения для API
            messages = self._build_messages(original_text)
            
            # Генерируем перевод
            temperature = self._get_temperature()
            
            # Используем API клиент для отправки сообщений
            response = self._call_api(messages, temperature)
            
            if not response:
                error_msg = "Пустой ответ от API"
                logging.warning(f"⚠️ Translator {self.worker_id}: {error_msg} для task {task_id}")
                self.task_manager.report_failure(task_id, error_msg)
                # Уведомляем менеджер об ошибке
                if self.stats_callback:
                    self.stats_callback(False)
                return False
            
            # Извлекаем перевод
            translated_text = self._extract_translation(response)
            if not translated_text:
                error_msg = f"Не удалось извлечь перевод из ответа: {response}"
                logging.warning(f"⚠️ Translator {self.worker_id}: {error_msg}")
                self.task_manager.report_failure(task_id, error_msg)
                # Уведомляем менеджер об ошибке
                if self.stats_callback:
                    self.stats_callback(False)
                return False
            
            # Формируем результат
            result = self._build_result(task_id, original_text, translated_text, temperature)
            
            # Валидация результата
            if not self._validate_result(result):
                error_msg = "Результат не прошел валидацию"
                logging.warning(f"⚠️ Translator {self.worker_id}: {error_msg}")
                self.task_manager.report_failure(task_id, error_msg)
                # Уведомляем менеджер об ошибке
                if self.stats_callback:
                    self.stats_callback(False)
                return False
            
            # Сохраняем результат
            filtered_data = self.validator.filter_output_fields(result)
            if self.writer.write_dialog(filtered_data):
                self.task_manager.report_success(task_id)
                # Уведомляем менеджер об успехе
                if self.stats_callback:
                    self.stats_callback(True)
                return True
            else:
                error_msg = "Ошибка записи в файл"
                logging.error(f"❌ Translator {self.worker_id}: {error_msg}")
                self.task_manager.report_failure(task_id, error_msg)
                # Уведомляем менеджер об ошибке
                if self.stats_callback:
                    self.stats_callback(False)
                return False
                
        except Exception as e:
            error_msg = str(e)
            logging.error(f"❌ Translator {self.worker_id}: ошибка обработки task {task_id}: {error_msg}")
            self.task_manager.report_failure(task_id, error_msg)
            # Уведомляем менеджер об ошибке
            if self.stats_callback:
                self.stats_callback(False)
            return False
    
    def _call_api(self, messages: List[Dict[str, str]], temperature: float) -> Optional[Dict[str, Any]]:
        """
        Вызов API с сообщениями
        
        Args:
            messages: Список сообщений для API
            temperature: Температура генерации
            
        Returns:
            Ответ от API или None
        """
        try:
            # Пробуем использовать стандартный метод generate_dialog
            # Если он принимает messages, отлично
            # Если нет, конвертируем в промпт
            
            # Способ 1: если APIClient поддерживает messages напрямую
            if hasattr(self.api_client, 'generate_from_messages'):
                return self.api_client.generate_from_messages(messages, temperature=temperature)
            
            # Способ 2: конвертируем messages в один промпт
            # (для обратной совместимости с существующим APIClient)
            prompt = self._messages_to_prompt(messages)
            return self.api_client.generate_dialog(prompt, temperature=temperature)
            
        except Exception as e:
            logging.error(f"❌ Translator {self.worker_id}: ошибка вызова API: {e}")
            return None
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Конвертация списка сообщений в один промпт (для обратной совместимости)
        
        Args:
            messages: Список сообщений
            
        Returns:
            Строка промпта
        """
        prompt_parts = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if role == 'system':
                prompt_parts.append(f"Системная инструкция: {content}")
            elif role == 'user':
                prompt_parts.append(f"Пользователь: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Ассистент: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def _get_temperature(self) -> float:
        """
        Получение температуры для генерации
        """
        translation_config = self.config.get('translation', {})
        return translation_config.get('temperature', 0.3)
    
    def _extract_translation(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Извлечение переведенного текста из ответа API
        
        Args:
            response: Ответ от API
            
        Returns:
            Переведенный текст или None
        """
        # Пробуем разные варианты получения перевода
        if 'translated_text' in response:
            text = response['translated_text']
        elif 'translation' in response:
            text = response['translation']
        elif 'text' in response:
            text = response['text']
        elif 'content' in response:
            text = response['content']
        elif 'choices' in response and len(response['choices']) > 0:
            # Формат ответа OpenAI
            choice = response['choices'][0]
            if 'message' in choice and 'content' in choice['message']:
                text = choice['message']['content']
            elif 'text' in choice:
                text = choice['text']
            else:
                text = None
        else:
            # Если ключи не найдены, пробуем взять первое строковое значение
            for value in response.values():
                if isinstance(value, str) and len(value) > 0:
                    text = value
                    break
            else:
                return None
        
        # Очистка текста
        if isinstance(text, str):
            # Удаляем лишние кавычки и пробелы
            text = text.strip().strip('"\'')
            
            # Удаляем маркеры JSON если есть
            if text.startswith('{') and text.endswith('}'):
                try:
                    import json
                    parsed = json.loads(text)
                    if 'translated_text' in parsed:
                        text = parsed['translated_text']
                    elif 'translation' in parsed:
                        text = parsed['translation']
                    elif 'text' in parsed:
                        text = parsed['text']
                except:
                    pass
            
            return text if len(text) > 0 else None
        
        return None
    
    def _build_result(self, task_id: Any, original_text: str, 
                     translated_text: str, temperature: float) -> Dict[str, Any]:
        """
        Построение результирующего словаря
        
        Returns:
            Словарь с результатом перевода
        """
        result = {
            'id': task_id,
            'original_text': original_text,
            'translated_text': translated_text,
            'target_language': self.target_language,
            'temperature': round(temperature, 4),
            'timestamp': time.time(),
            'worker_id': self.worker_id
        }
        
        # Добавляем дополнительные поля если они есть в схеме
        output_fields = self.config.get('output_schema', {}).get('fields', [])
        
        # Если в схеме есть source_language, можно попробовать определить язык
        if 'source_language' in output_fields and 'source_language' not in result:
            result['source_language'] = 'unknown'
        
        # Если в схеме есть model, добавляем
        if 'model' in output_fields and 'model' not in result:
            result['model'] = self.config.get('api', {}).get('model', 'unknown')
        
        return result
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """
        Валидация результата перевода
        
        Args:
            result: Результат для проверки
            
        Returns:
            True если результат валиден
        """
        # Базовая проверка
        if not isinstance(result, dict):
            return False
        
        # Проверка наличия обязательных полей
        required_fields = ['id', 'original_text', 'translated_text']
        for field in required_fields:
            if field not in result:
                logging.warning(f"⚠️ Отсутствует обязательное поле: {field}")
                return False
            
            if not result[field] or not str(result[field]).strip():
                logging.warning(f"⚠️ Поле {field} пустое")
                return False
        
        # Проверка, что перевод не совпадает с оригиналом (если языки разные)
        if self.target_language.lower() not in ['en', 'ru', '源语言']:
            # Для токипоны и других языков проверяем
            if result['original_text'].strip().lower() == result['translated_text'].strip().lower():
                logging.warning(f"⚠️ Перевод совпадает с оригиналом, возможно ошибка")
                # Не считаем критической ошибкой, просто предупреждаем
        
        return True
    
    def request_stop(self) -> None:
        """
        Запрос на остановку потока
        """
        self._stop_requested = True
        self.is_working = False
        logging.debug(f"🛑 Translator {self.worker_id}: получен запрос на остановку")
    
    def cleanup(self) -> None:
        """
        Очистка ресурсов потока
        """
        try:
            if hasattr(self, 'api_client'):
                self.api_client.cleanup()
            
            self.is_working = False
            logging.debug(f"🧹 Translator {self.worker_id}: ресурсы очищены")
            
        except Exception as e:
            logging.error(f"❌ Translator {self.worker_id}: ошибка очистки ресурсов: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики потока
        
        Returns:
            Словарь со статистикой
        """
        return {
            'worker_id': self.worker_id,
            'type': 'translation',
            'is_alive': self.is_alive(),
            'is_working': self.is_working,
            'generated_count': self.generated_count,
            'error_count': self.error_count,
            'consecutive_errors': self.consecutive_errors,
            'stop_requested': self._stop_requested,
            'target_language': self.target_language
        }
    
    def __repr__(self) -> str:
        return f"TranslationWorkerThread(id={self.worker_id}, target={self.target_language}, alive={self.is_alive()})"