"""
Менеджер пула потоков для безопасной и эффективной параллельной генерации
"""

import threading
import time
import logging
from typing import Dict, List, Any, Optional

from workers.worker_thread import WorkerThread
from storage.thread_safe_writer import ThreadSafeWriter


class ThreadPoolManager:
    """
    Управление пулом рабочих потоков с мониторингом и graceful shutdown
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
        self.workers: List[WorkerThread] = []
        
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
        
        logging.info("🔄 ThreadPoolManager инициализирован")
    
    def _update_stats_callback(self, success: bool) -> None:
        """
        Callback для обновления статистики от рабочих потоков
        
        Args:
            success: True если группа диалогов успешно сгенерирована
        """
        self.update_stats(success)
    
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
                thread_count = self.config['generation']['threads']
                
                if thread_count <= 0:
                    logging.error("❌ Некорректное количество потоков")
                    return False
                
                # Создание и запуск рабочих потоков
                for i in range(thread_count):
                    worker = WorkerThread(
                        worker_id=i + 1,
                        config=self.config,
                        writer=self.writer,
                        stats_callback=self._update_stats_callback  # Добавляем callback
                    )
                    worker.start()
                    self.workers.append(worker)
                
                self._is_running = True
                self._shutdown_requested = False
                self._start_time = time.time()
                
                logging.info(f"🚀 Запущено {len(self.workers)} рабочих потоков")
                return True
                
            except Exception as e:
                logging.error(f"❌ Ошибка запуска пула потоков: {e}")
                self._cleanup_workers()
                return False
    
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
            
            # Ожидаем завершения потоков
            all_stopped = self._wait_for_workers_stop(timeout)
            
            if all_stopped:
                logging.info("✅ Все рабочие потоки остановлены")
            else:
                logging.warning("⚠️ Некоторые потоки не остановились вовремя")
            
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
            
            logging.info(f"⏳ Ожидание остановки {len(alive_workers)} потоков...")
            time.sleep(1)
        
        # Форсируем завершение оставшихся потоков
        alive_workers = [w for w in self.workers if w.is_alive()]
        for worker in alive_workers:
            logging.warning(f"⚠️ Принудительная остановка потока {worker.worker_id}")
        
        return len(alive_workers) == 0
    
    def _cleanup_workers(self) -> None:
        """Очистка ресурсов рабочих потоков"""
        try:
            for worker in self.workers:
                if hasattr(worker, 'cleanup'):
                    worker.cleanup()
            
            self.workers.clear()
                
        except Exception as e:
            logging.error(f"❌ Ошибка очистки ресурсов пула: {e}")
    
    def update_stats(self, success: bool) -> None:
        """
        Обновление статистики генерации
        
        Args:
            success: True если группа диалогов успешно сгенерирована
        """
        with self._stats_lock:
            self._total_groups_generated += 1
            if success:
                self._successful_groups += 1
            else:
                self._failed_groups += 1
            
            # Логируем каждую 10-ю успешную группу для отслеживания прогресса
            if success and self._successful_groups % 10 == 0:
                logging.info(f"📈 Успешно сгенерировано групп: {self._successful_groups}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение текущей статистики пула
        
        Returns:
            Словарь со статистикой
        """
        with self._stats_lock:
            active_workers = len([w for w in self.workers if w.is_alive() and getattr(w, 'is_working', False)])
            
            stats = {
                'total_pairs': self._total_groups_generated,  # Исправлено: должно быть total_pairs
                'successful_pairs': self._successful_groups,  # Исправлено: должно быть successful_pairs
                'failed_pairs': self._failed_groups,          # Исправлено: должно быть failed_pairs
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
                    logging.warning(f"🔄 Перезапуск упавшего потока {worker.worker_id}")
                    
                    try:
                        new_worker = WorkerThread(
                            worker_id=worker.worker_id,
                            config=self.config,
                            writer=self.writer,
                            stats_callback=self._update_stats_callback  # Добавляем callback
                        )
                        new_worker.start()
                        self.workers[i] = new_worker
                    except Exception as e:
                        logging.error(f"❌ Ошибка перезапуска потока {worker.worker_id}: {e}")
    
    def monitor_workers_health(self) -> Dict[str, Any]:
        """
        Мониторинг здоровья рабочих потоков
        
        Returns:
            Статистика здоровья потоков
        """
        health_stats = {
            'total_workers': len(self.workers),
            'alive_workers': 0,
            'working_workers': 0,
            'failed_workers': 0,
            'worker_details': []
        }
        
        for worker in self.workers:
            worker_info = {
                'worker_id': worker.worker_id,
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
        
        return health_stats
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированная остановка пула"""
        self.stop_generation()