"""
Менеджер задач для режима перевода
Управляет очередью задач, чекпоинтами и повторными попытками
"""

import json
import logging
import queue
import os
import time
from typing import Dict, Any, Iterator, Optional, Set, Tuple
from pathlib import Path

from core.dataset_loader import DatasetLoader


class TranslationTaskManager:
    """
    Управление задачами перевода:
    - Загрузка датасета
    - Поддержка чекпоинтов (сохранение прогресса)
    - Очередь задач с повторными попытками
    - Отслеживание успешных и упавших задач
    """
    
    def __init__(self, translation_config: Dict[str, Any], output_schema: Dict[str, Any]):
        """
        Инициализация менеджера задач
        
        Args:
            translation_config: Конфигурация перевода
            output_schema: Схема выходных данных
        """
        self.config = translation_config
        self.output_schema = output_schema
        
        # Параметры
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay_seconds', 5)
        self.checkpoint_file = self.config.get('checkpoint_file', 'translation_progress.json')
        
        # Состояние
        self.task_queue = queue.Queue()
        self.processed_ids: Set[Any] = set()
        self.failed_ids: Dict[Any, int] = {}  # id -> количество попыток
        self.task_list: list = []  # список всех задач (id, text)
        
        # Статистика
        self._total_tasks = 0
        self._last_checkpoint_save = time.time()
        self._checkpoint_interval = 30  # сохранять чекпоинт каждые 30 секунд
        
        # Загружаем датасет и чекпоинт
        self._load_dataset()
        self._load_checkpoint()
        self._build_task_queue()
        
        logging.info(f"✅ TranslationTaskManager инициализирован")
        logging.info(f"📊 Всего задач: {self._total_tasks}")
        logging.info(f"✅ Обработано: {len(self.processed_ids)}")
        logging.info(f"❌ В ошибке: {len(self.failed_ids)}")
        logging.info(f"📝 Чекпоинт: {self.checkpoint_file}")
    
    def _load_dataset(self) -> None:
        """Загрузка датасета"""
        try:
            dataset_config = self.config['dataset']
            loader = DatasetLoader(dataset_config)
            
            # Загружаем все элементы
            self.task_list = []
            for item in loader.load_items():
                self.task_list.append((item['id'], item['text']))
            
            self._total_tasks = len(self.task_list)
            logging.info(f"📚 Загружено {self._total_tasks} задач из датасета")
            
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки датасета: {e}")
            raise
    
    def _load_checkpoint(self) -> None:
        """Загрузка чекпоинта из файла"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                    
                    self.processed_ids = set(checkpoint.get('processed_ids', []))
                    self.failed_ids = checkpoint.get('failed_ids', {})
                    
                    logging.info(f"💾 Загружен чекпоинт: {len(self.processed_ids)} обработано, {len(self.failed_ids)} в ошибке")
                    
                    # Конвертируем ключи failed_ids в правильные типы (из JSON они приходят как строки)
                    # Определяем тип ID по первому элементу в task_list
                    if self.task_list and self.failed_ids:
                        sample_id = self.task_list[0][0]
                        id_type = type(sample_id)
                        if id_type != str:
                            self.failed_ids = {id_type(k): v for k, v in self.failed_ids.items()}
                    
            except Exception as e:
                logging.warning(f"⚠️ Ошибка загрузки чекпоинта: {e}")
                self.processed_ids = set()
                self.failed_ids = {}
        else:
            logging.info("ℹ️ Файл чекпоинта не найден, начинаем с нуля")
    
    def _build_task_queue(self) -> None:
        """Построение очереди задач (только необработанные и с попытками < max_retries)"""
        for task_id, text in self.task_list:
            # Пропускаем уже обработанные
            if task_id in self.processed_ids:
                continue
            
            # Проверяем количество попыток
            retry_count = self.failed_ids.get(task_id, 0)
            if retry_count >= self.max_retries:
                logging.debug(f"⏭️ Пропускаем задачу {task_id}: превышено число попыток ({retry_count})")
                continue
            
            # Добавляем в очередь
            self.task_queue.put((task_id, text))
        
        logging.info(f"📋 Построена очередь: {self.task_queue.qsize()} задач ожидают обработки")
    
    def save_checkpoint(self) -> None:
        """Сохранение чекпоинта в файл"""
        try:
            # Конвертируем set в list для JSON
            checkpoint = {
                'processed_ids': list(self.processed_ids),
                'failed_ids': self.failed_ids,
                'last_update': time.time(),
                'total_tasks': self._total_tasks,
                'max_retries': self.max_retries
            }
            
            # Создаем резервную копию перед записью
            if os.path.exists(self.checkpoint_file):
                backup_file = f"{self.checkpoint_file}.backup"
                try:
                    os.rename(self.checkpoint_file, backup_file)
                except:
                    pass
            
            # Записываем новый чекпоинт
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            
            self._last_checkpoint_save = time.time()
            logging.debug(f"💾 Чекпоинт сохранен: {len(self.processed_ids)} обработано")
            
        except Exception as e:
            logging.error(f"❌ Ошибка сохранения чекпоинта: {e}")
    
    def report_success(self, task_id: Any) -> None:
        """
        Сообщить об успешном выполнении задачи
        
        Args:
            task_id: ID выполненной задачи
        """
        self.processed_ids.add(task_id)
        
        # Удаляем из failed_ids если была там
        if task_id in self.failed_ids:
            del self.failed_ids[task_id]
        
        # Периодически сохраняем чекпоинт
        if time.time() - self._last_checkpoint_save > self._checkpoint_interval:
            self.save_checkpoint()
    
    def report_failure(self, task_id: Any, error_msg: str = "") -> bool:
        """
        Сообщить об ошибке выполнения задачи
        
        Args:
            task_id: ID задачи, вызвавшей ошибку
            error_msg: Сообщение об ошибке
            
        Returns:
            True если задача будет повторена, False если превышен лимит попыток
        """
        retry_count = self.failed_ids.get(task_id, 0) + 1
        self.failed_ids[task_id] = retry_count
        
        logging.warning(f"⚠️ Ошибка для задачи {task_id} (попытка {retry_count}/{self.max_retries}): {error_msg}")
        
        # Решаем, повторять или нет
        if retry_count < self.max_retries:
            # Задержка перед повторной отправкой
            time.sleep(self.retry_delay)
            
            # Находим текст задачи
            task_text = None
            for tid, text in self.task_list:
                if tid == task_id:
                    task_text = text
                    break
            
            if task_text:
                self.task_queue.put((task_id, task_text))
                logging.info(f"🔄 Задача {task_id} отправлена на повтор (попытка {retry_count + 1})")
                return True
        else:
            logging.error(f"💥 Задача {task_id} окончательно провалена после {retry_count} попыток")
            self.save_checkpoint()  # Сохраняем чекпоинт при окончательной ошибке
        
        return False
    
    def get_task_queue(self) -> queue.Queue:
        """
        Получение очереди задач
        
        Returns:
            Queue с задачами (id, text)
        """
        return self.task_queue
    
    def get_total_tasks(self) -> int:
        """Общее количество задач"""
        return self._total_tasks
    
    def get_processed_count(self) -> int:
        """Количество успешно обработанных задач"""
        return len(self.processed_ids)
    
    def get_failed_count(self) -> int:
        """Количество задач с ошибками"""
        return len([c for c in self.failed_ids.values() if c >= self.max_retries])
    
    def get_remaining_count(self) -> int:
        """Количество оставшихся задач"""
        return self.task_queue.qsize()
    
    def get_progress_percentage(self) -> float:
        """Процент выполнения"""
        if self._total_tasks == 0:
            return 0.0
        return (self.get_processed_count() / self._total_tasks) * 100
    
    def get_checkpoint_info(self) -> Dict[str, Any]:
        """Получение информации о чекпоинте"""
        return {
            'checkpoint_file': self.checkpoint_file,
            'processed_ids_count': len(self.processed_ids),
            'failed_ids_count': len(self.failed_ids),
            'total_tasks': self._total_tasks,
            'progress_percentage': self.get_progress_percentage(),
            'max_retries': self.max_retries,
            'last_checkpoint_save': self._last_checkpoint_save
        }
    
    def get_failed_tasks(self) -> Dict[Any, int]:
        """Получение списка проваленных задач"""
        return {tid: count for tid, count in self.failed_ids.items() if count >= self.max_retries}
    
    def is_complete(self) -> bool:
        """Проверка, выполнены ли все задачи"""
        return self.get_processed_count() + self.get_failed_count() >= self._total_tasks
    
    def cleanup(self) -> None:
        """Очистка ресурсов"""
        self.save_checkpoint()  # Финальное сохранение
        logging.info("🧹 TranslationTaskManager очищен")


def load_translation_checkpoint(checkpoint_file: str) -> Optional[Dict[str, Any]]:
    """
    Утилита для загрузки существующего чекпоинта
    
    Args:
        checkpoint_file: Путь к файлу чекпоинта
        
    Returns:
        Содержимое чекпоинта или None
    """
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка загрузки чекпоинта {checkpoint_file}: {e}")
    return None