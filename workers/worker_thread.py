"""
Рабочий поток для генерации диалогов с полной обработкой ошибок и мониторингом состояния
"""

import threading
import time
import logging
import random
from typing import Dict, Any, Optional, Callable

from core.theme_generator import ThemeGenerator
from core.prompt_engine import PromptEngine
from core.api_client import APIClient
from core.dialog_validator import DialogValidator
from storage.thread_safe_writer import ThreadSafeWriter


class WorkerThread(threading.Thread):
    """
    Рабочий поток для параллельной генерации групп диалогов
    """
    
    def __init__(self, 
                 worker_id: int,
                 config: Dict[str, Any],
                 writer: ThreadSafeWriter,
                 stats_callback: Optional[Callable[[bool], None]] = None):
        """
        Инициализация рабочего потока
        
        Args:
            worker_id: Уникальный идентификатор потока
            config: Конфигурация приложения
            writer: Потокобезопасный writer для записи результатов
            stats_callback: Callback для обновления статистики
        """
        super().__init__(name=f"Worker-{worker_id}", daemon=True)
        
        self.worker_id = worker_id
        self.config = config
        self.writer = writer
        self.stats_callback = stats_callback
        
        # Состояние потока
        self._stop_requested = False
        self.is_working = False
        self.error_count = 0
        self.generated_count = 0
        self.consecutive_errors = 0
        
        # Максимальное количество последовательных ошибок
        self.max_consecutive_errors = config['generation'].get('max_errors', 10)
        
        # Инициализация компонентов
        self._init_components()
        
        logging.debug(f"🔧 Worker {worker_id} инициализирован")
    
    def _init_components(self) -> None:
        """Инициализация всех компонентов потока"""
        try:
            # Генератор тем
            prompt_templates = self.config['prompt_templates']
            self.theme_generator = ThemeGenerator(
                templates=prompt_templates['templates'],
                word_banks=prompt_templates['words']
            )
            
            # Движок промптов
            self.prompt_engine = PromptEngine(
                base_template=prompt_templates['base'],
                output_schema=self.config['output_schema'],
                line_range=self.config['generation']['dialog_lines']
            )
            
            # API клиент
            self.api_client = APIClient(self.config['api'])
            
            # Валидатор диалогов
            self.validator = DialogValidator(self.config['output_schema'])
            
        except Exception as e:
            logging.error(f"❌ Worker {self.worker_id}: Ошибка инициализации компонентов: {e}")
            raise
    
    def run(self) -> None:
        """
        Главный цикл выполнения потока
        """
        logging.info(f"🚀 Worker {self.worker_id} запущен")
        
        while not self._stop_requested and self.consecutive_errors < self.max_consecutive_errors:
            try:
                self.is_working = True
                
                # Генерация одной группы диалогов
                success = self._generate_single_group()
                
                if success:
                    self.generated_count += 1
                    self.consecutive_errors = 0
                    logging.debug(f"✅ Worker {self.worker_id}: Успешная генерация группы #{self.generated_count}")
                else:
                    self.error_count += 1
                    self.consecutive_errors += 1
                    logging.warning(f"⚠️ Worker {self.worker_id}: Ошибка генерации (последовательных: {self.consecutive_errors})")
                
                # Обновляем статистику в пуле
                if self.stats_callback:
                    self.stats_callback(success)
                
                # Случайная пауза между группами
                if not self._stop_requested:
                    delay = random.uniform(1.0, 3.0)
                    time.sleep(delay)
                    
            except Exception as e:
                self.error_count += 1
                self.consecutive_errors += 1
                logging.error(f"❌ Worker {self.worker_id}: Критическая ошибка в главном цикле: {e}")
                
                # Обновляем статистику об ошибке
                if self.stats_callback:
                    self.stats_callback(False)
                    
                time.sleep(5)  # Пауза при критической ошибке
        
        # Завершение работы
        self.is_working = False
        
        if self._stop_requested:
            logging.info(f"🔚 Worker {self.worker_id}: Остановлен по запросу")
        elif self.consecutive_errors >= self.max_consecutive_errors:
            logging.error(f"💥 Worker {self.worker_id}: Превышено максимальное количество ошибок")
        else:
            logging.info(f"🔚 Worker {self.worker_id}: Завершил работу")
    
    def _generate_single_group(self) -> bool:
        """
        Генерация одной группы диалогов на всех языках
        
        Returns:
            True если все диалоги группы успешно сгенерированы и сохранены
        """
        try:
            # Генерация темы
            theme = self.theme_generator.generate_theme()
            
            languages = self.config['generation']['languages']
            successful_dialogs = 0
            
            # Генерация диалогов для каждого языка
            for lang_config in languages:
                if self._stop_requested:
                    return False
                
                dialog = self._generate_single_dialog(
                    language_code=lang_config['code'],
                    language_name=lang_config['name'],
                    theme=theme
                )
                
                if dialog:
                    # Добавляем только необходимые метаданные
                    dialog['theme'] = theme
                    dialog['worker_id'] = self.worker_id
                    
                    # ФИЛЬТРУЕМ поля согласно output_schema
                    filtered_dialog = self.validator.filter_output_fields(dialog)
                    
                    # Сохраняем отфильтрованный диалог
                    if self.writer.write_dialog(filtered_dialog):
                        successful_dialogs += 1
                    else:
                        logging.error(f"❌ Worker {self.worker_id}: Ошибка записи диалога")
                
                # Короткая пауза между языками
                if not self._stop_requested:
                    time.sleep(0.2)
            
            # Проверяем что все диалоги сгенерированы
            success = successful_dialogs == len(languages)
            
            if success:
                logging.info(f"🎯 Worker {self.worker_id}: Группа тем '{theme}' успешно сгенерирована ({len(languages)} языков)")
            else:
                logging.warning(f"⚠️ Worker {self.worker_id}: Группа тем '{theme}' частично сгенерирована ({successful_dialogs}/{len(languages)})")
            
            return success
            
        except Exception as e:
            logging.error(f"❌ Worker {self.worker_id}: Ошибка генерации группы: {e}")
            return False
    
    def _generate_single_dialog(self, 
                              language_code: str, 
                              language_name: str,
                              theme: str) -> Optional[Dict[str, Any]]:
        """
        Генерация одного диалога для конкретного языка
        """
        try:
            # Случайная температура из диапазона
            temp_config = self.config['generation']['temperature']
            temperature = random.uniform(temp_config['min'], temp_config['max'])
            
            # Создание промпта
            prompt = self.prompt_engine.build_prompt(
                language_code=language_code,
                language_name=language_name,
                theme=theme
            )
            
            # Генерация диалога через API
            dialog_data = self.api_client.generate_dialog(
                prompt=prompt,
                temperature=temperature
            )
            
            if not dialog_data:
                logging.warning(f"⚠️ Worker {self.worker_id}: Пустой ответ API для {language_code}")
                return None
            
            # Валидация диалога
            if not self.validator.validate_dialog(dialog_data):
                logging.warning(f"⚠️ Worker {self.worker_id}: Невалидный диалог для {language_code}")
                return None
            
            # Добавляем метаданные (только те, что нужны согласно output_schema)
            dialog_data['language'] = language_code
            dialog_data['temperature'] = round(temperature, 4)  # Округляем для читаемости
            dialog_data['timestamp'] = time.time()
            
            # Очистка реплик
            if 'dialog' in dialog_data:
                dialog_data['dialog'] = self.validator.sanitize_replicas(dialog_data['dialog'])
            
            logging.debug(f"✅ Worker {self.worker_id}: Успешная генерация диалога на {language_code}")
            return dialog_data
            
        except Exception as e:
            logging.error(f"❌ Worker {self.worker_id}: Ошибка генерации диалога на {language_code}: {e}")
            return None
    
    def request_stop(self) -> None:
        """
        Запрос на остановку потока
        """
        self._stop_requested = True
        self.is_working = False
        logging.debug(f"🛑 Worker {self.worker_id}: Получен запрос на остановку")
    
    def cleanup(self) -> None:
        """
        Очистка ресурсов потока
        """
        try:
            if hasattr(self, 'api_client'):
                self.api_client.cleanup()
            
            self.is_working = False
            logging.debug(f"🧹 Worker {self.worker_id}: Ресурсы очищены")
            
        except Exception as e:
            logging.error(f"❌ Worker {self.worker_id}: Ошибка очистки ресурсов: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики потока
        
        Returns:
            Словарь со статистикой
        """
        return {
            'worker_id': self.worker_id,
            'is_alive': self.is_alive(),
            'is_working': self.is_working,
            'generated_count': self.generated_count,
            'error_count': self.error_count,
            'consecutive_errors': self.consecutive_errors,
            'stop_requested': self._stop_requested
        }
    
    def __repr__(self) -> str:
        return f"WorkerThread(id={self.worker_id}, alive={self.is_alive()}, working={self.is_working})"