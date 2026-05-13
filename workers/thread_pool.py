"""
Менеджер пула потоков для безопасной и эффективной параллельной генерации
Поддерживает два режима работы:
1. dialog_generation - генерация диалогов (оригинальный режим)
2. translation - перевод текстов из датасета
"""

import threading
import time
import logging
import queue
from typing import Dict, List, Any, Optional

from workers.worker_thread import WorkerThread
from workers.translation_worker import TranslationWorkerThread
from core.task_manager import TranslationTaskManager
from storage.thread_safe_writer import ThreadSafeWriter


class ThreadPoolManager:
    """
    Управление пулом рабочих потоков с мониторингом и graceful shutdown
    Поддерживает разные типы воркеров в зависимости от конфигурации
    """
    
    def __init__(self, config: Dict[str, Any], writer: ThreadSafeWriter):
        """
        Инициализация менеджера пула потоков
        
        Args:
            config: Конфигурация приложения (уже загруженная как dict)
            writer: Потокобезопасный writer для записи результатов
        """
        self.config = config
        self.writer = writer
        self.workers: List[Any] = []  # Может быть WorkerThread или TranslationWorkerThread
        self.task_type = config.get('task_type', 'dialog_generation')
        
        # Специфичные для translation режима компоненты
        self.task_queue: Optional[queue.Queue] = None
        self.task_manager: Optional[TranslationTaskManager] = None
        
        # Примитивы синхронизации
        self._pool_lock = threading.RLock()
        self._stats_lock = threading.Lock()
        
        # Состояние пула
        self._is_running = False
        self._shutdown_requested = False
        
        # Статистика
        self._total_groups_generated = 0
        self._successful_groups = 0
        self._failed_groups = 0
        self._start_time: Optional[float] = None
        
        logging.info(f"🔄 ThreadPoolManager инициализирован (режим: {self.task_type})")
    
    def _update_stats_callback(self, success: bool) -> None:
        """
        Callback для обновления статистики от рабочих потоков
        
        Args:
            success: True если задача успешно выполнена
        """
        self.update_stats(success)
    
    def _init_translation_components(self) -> bool:
        """
        Инициализация компонентов для режима перевода
        
        Returns:
            True если инициализация успешна
        """
        try:
            # Создаем менеджер задач
            self.task_manager = TranslationTaskManager(
                translation_config=self.config['translation'],
                output_schema=self.config['output_schema']
            )
            
            # Получаем очередь задач
            self.task_queue = self.task_manager.get_task_queue()
            
            logging.info(f"✅ Инициализирован TranslationTaskManager")
            logging.info(f"📊 Всего задач: {self.task_manager.get_total_tasks()}")
            logging.info(f"📈 Выполнено: {self.task_manager.get_processed_count()}")
            logging.info(f"❌ Ошибок: {self.task_manager.get_failed_count()}")
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка инициалиции translation компонентов: {e}")
            return False
    
    def start_generation(self) -> bool:
        """
        Запуск пула рабочих потоков
        
        Returns:
            True если пул успешно запущен
        """
        with self._pool_lock:
            if self._is_running:
                logging.warning("⚠️ Пул потоков уже запущен")
                return False
            
            try:
                # Определяем количество потоков
                if self.task_type == 'translation':
                    thread_count = self.config['translation'].get('threads', 2)
                else:
                    thread_count = self.config['generation']['threads']
                
                if thread_count <= 0:
                    logging.error("❌ Некорректное количество потоков")
                    return False
                
                # Инициализируем translation компоненты если нужно
                if self.task_type == 'translation':
                    if not self._init_translation_components():
                        return False
                
                # Создание и запуск рабочих потоков
                for i in range(thread_count):
                    worker = self._create_worker(i + 1)
                    if worker:
                        worker.start()
                        self.workers.append(worker)
                    else:
                        logging.error(f"❌ Не удалось создать воркер {i + 1}")
                        return False
                
                self._is_running = True
                self._shutdown_requested = False
                self._start_time = time.time()
                
                logging.info(f"🚀 Запущено {len(self.workers)} рабочих потоков (режим: {self.task_type})")
                return True
                
            except Exception as e:
                logging.error(f"❌ Ошибка запуска пула потоков: {e}")
                self._cleanup_workers()
                return False
    
    def _create_worker(self, worker_id: int) -> Optional[Any]:
        """
        Создание рабочего потока в зависимости от режима
        
        Args:
            worker_id: Уникальный идентификатор потока
            
        Returns:
            Экземпляр воркера или None при ошибке
        """
        try:
            if self.task_type == 'translation':
                # Воркер для перевода
                return TranslationWorkerThread(
                    worker_id=worker_id,
                    config=self.config,
                    task_queue=self.task_queue,
                    task_manager=self.task_manager,
                    writer=self.writer,
                    stats_callback=self._update_stats_callback
                )
            else:
                # Оригинальный воркер для диалогов
                return WorkerThread(
                    worker_id=worker_id,
                    config=self.config,
                    writer=self.writer,
                    stats_callback=self._update_stats_callback
                )
        except Exception as e:
            logging.error(f"❌ Ошибка создания воркера {worker_id}: {e}")
            return None
    
    def stop_generation(self, timeout: float = 30.0) -> bool:
        """
        Безопасная остановка пула потоков
        
        Args:
            timeout: Таймаут ожидания завершения потоков в секундах
            
        Returns:
            True если все потоки успешно остановлены
        """
        with self._pool_lock:
            if not self._is_running:
                logging.info("ℹ️ Пул потоков уже остановлен")
                return True
            
            logging.info("🛑 Запрос на остановку пула потоков...")
            self._shutdown_requested = True
            self._is_running = False
            
            # Уведомляем все потоки о необходимости остановки
            for worker in self.workers:
                worker.request_stop()
            
            # Для translation режима добавляем сигнал завершения в очередь
            if self.task_type == 'translation' and self.task_queue:
                for _ in range(len(self.workers)):
                    try:
                        self.task_queue.put(None, timeout=1)
                    except queue.Full:
                        pass
            
            # Ожидаем завершения потоков
            all_stopped = self._wait_for_workers_stop(timeout)
            
            if all_stopped:
                logging.info("✅ Все рабочие потоки остановлены")
            else:
                logging.warning("⚠️ Некоторые потоки не остановились вовремя")
            
            # Сохраняем финальный чекпоинт для translation режима
            if self.task_type == 'translation' and self.task_manager:
                self.task_manager.save_checkpoint()
                logging.info(f"💾 Финальный чекпоинт сохранен: {self.task_manager.checkpoint_file}")
            
            self._cleanup_workers()
            return all_stopped
    
    def _wait_for_workers_stop(self, timeout: float) -> bool:
        """
        Ожидание остановки всех рабочих потоков
        
        Args:
            timeout: Максимальное время ожидания
            
        Returns:
            True если все потоки остановились
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Проверяем состояние всех потоков
            alive_workers = [w for w in self.workers if w.is_alive()]
            
            if not alive_workers:
                return True
            
            # Выводим прогресс остановки
            if len(alive_workers) != len(self.workers):
                logging.info(f"⏳ Ожидание остановки {len(alive_workers)}/{len(self.workers)} потоков...")
            
            time.sleep(1)
        
        # Форсируем завершение оставшихся потоков
        alive_workers = [w for w in self.workers if w.is_alive()]
        for worker in alive_workers:
            worker_id = getattr(worker, 'worker_id', 'unknown')
            logging.warning(f"⚠️ Принудительная остановка потока {worker_id}")
        
        return len(alive_workers) == 0
    
    def _cleanup_workers(self) -> None:
        """Очистка ресурсов рабочих потоков"""
        try:
            for worker in self.workers:
                if hasattr(worker, 'cleanup'):
                    worker.cleanup()
            
            self.workers.clear()
            
            # Очистка translation компонентов
            if self.task_manager:
                self.task_manager = None
            if self.task_queue:
                self.task_queue = None
                
        except Exception as e:
            logging.error(f"❌ Ошибка очистки ресурсов пула: {e}")
    
    def update_stats(self, success: bool) -> None:
        """
        Обновление статистики генерации
        
        Args:
            success: True если задача успешно выполнена
        """
        with self._stats_lock:
            self._total_groups_generated += 1
            if success:
                self._successful_groups += 1
            else:
                self._failed_groups += 1
            
            # Логируем каждую 10-ю успешную задачу для отслеживания прогресса
            if success and self._successful_groups % 10 == 0:
                logging.info(f"📈 Успешно выполнено задач: {self._successful_groups}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение текущей статистики пула
        
        Returns:
            Словарь со статистикой
        """
        with self._stats_lock:
            active_workers = len([w for w in self.workers if w.is_alive() and getattr(w, 'is_working', False)])
            
            stats = {
                'task_type': self.task_type,
                'total_pairs': self._total_groups_generated,
                'successful_pairs': self._successful_groups,
                'failed_pairs': self._failed_groups,
                'active_workers': active_workers,
                'total_workers': len(self.workers),
                'success_rate': 0,
                'is_running': self._is_running,
                'shutdown_requested': self._shutdown_requested
            }
            
            # Расчет процента успеха
            if self._total_groups_generated > 0:
                stats['success_rate'] = (self._successful_groups / self._total_groups_generated) * 100
            
            # Время работы
            if self._start_time:
                stats['uptime_seconds'] = time.time() - self._start_time
            
            # Добавляем статистику из task_manager для translation режима
            if self.task_type == 'translation' and self.task_manager:
                stats['translation_stats'] = {
                    'total_tasks': self.task_manager.get_total_tasks(),
                    'processed': self.task_manager.get_processed_count(),
                    'failed': self.task_manager.get_failed_count(),
                    'remaining': self.task_manager.get_remaining_count(),
                    'checkpoint_file': self.task_manager.checkpoint_file
                }
            
            return stats
    
    def is_running(self) -> bool:
        """
        Проверка работает ли пул
        
        Returns:
            True если пул активен
        """
        return self._is_running and not self._shutdown_requested
    
    def get_active_worker_count(self) -> int:
        """
        Получение количества активных рабочих потоков
        
        Returns:
            Количество активных потоков
        """
        return len([w for w in self.workers if w.is_alive() and getattr(w, 'is_working', False)])
    
    def restart_failed_workers(self) -> None:
        """
        Перезапуск упавших рабочих потоков
        """
        with self._pool_lock:
            if not self._is_running or self._shutdown_requested:
                return
            
            for i, worker in enumerate(self.workers):
                if not worker.is_alive():
                    worker_id = getattr(worker, 'worker_id', i + 1)
                    logging.warning(f"🔄 Перезапуск упавшего потока {worker_id}")
                    
                    try:
                        new_worker = self._create_worker(worker_id)
                        if new_worker:
                            new_worker.start()
                            self.workers[i] = new_worker
                        else:
                            logging.error(f"❌ Не удалось перезапустить поток {worker_id}")
                    except Exception as e:
                        logging.error(f"❌ Ошибка перезапуска потока {worker_id}: {e}")
    
    def monitor_workers_health(self) -> Dict[str, Any]:
        """
        Мониторинг здоровья рабочих потоков
        
        Returns:
            Статистика здоровья потоков
        """
        health_stats = {
            'task_type': self.task_type,
            'total_workers': len(self.workers),
            'alive_workers': 0,
            'working_workers': 0,
            'failed_workers': 0,
            'worker_details': []
        }
        
        for worker in self.workers:
            worker_info = {
                'worker_id': getattr(worker, 'worker_id', 'unknown'),
                'type': worker.__class__.__name__,
                'is_alive': worker.is_alive(),
                'is_working': getattr(worker, 'is_working', False),
                'error_count': getattr(worker, 'error_count', 0),
                'generated_count': getattr(worker, 'generated_count', 0)
            }
            health_stats['worker_details'].append(worker_info)
            
            if worker.is_alive():
                health_stats['alive_workers'] += 1
                if getattr(worker, 'is_working', False):
                    health_stats['working_workers'] += 1
            else:
                health_stats['failed_workers'] += 1
        
        # Добавляем информацию о прогрессе для translation режима
        if self.task_type == 'translation' and self.task_manager:
            health_stats['progress'] = {
                'completed': self.task_manager.get_processed_count(),
                'failed': self.task_manager.get_failed_count(),
                'total': self.task_manager.get_total_tasks(),
                'percentage': self.task_manager.get_progress_percentage()
            }
        
        return health_stats
    
    def get_checkpoint_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации о чекпоинте (для translation режима)
        
        Returns:
            Словарь с информацией о чекпоинте или None
        """
        if self.task_type == 'translation' and self.task_manager:
            return self.task_manager.get_checkpoint_info()
        return None
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированная остановка пула"""
        self.stop_generation()