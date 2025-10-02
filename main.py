#!/usr/bin/env python3
"""
Universal Dialog Generator
Генератор универсальных диалогов на multiple языках
"""

import logging
import sys
import time
import signal
import traceback
from typing import Optional

# Импорты наших модулей
from config.config_manager import ConfigManager
from storage.thread_safe_writer import ThreadSafeWriter
from workers.thread_pool import ThreadPoolManager


class UniversalDialogGenerator:
    """
    Главный класс приложения с безопасным управлением жизненным циклом
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация генератора
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = config_path
        self.config_manager: Optional[ConfigManager] = None
        self.writer: Optional[ThreadSafeWriter] = None
        self.pool_manager: Optional[ThreadPoolManager] = None
        self.running = False
        
        # Настройка обработчиков сигналов ПЕРВЫМ делом
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self) -> None:
        """Настройка обработчиков сигналов для graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame) -> None:
        """Обработчик сигналов завершения"""
        logging.info(f"📭 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.running = False
        self.stop()
        
    def initialize(self) -> bool:
        """
        Инициализация всех компонентов
        
        Returns:
            True если инициализация успешна, False при ошибке
        """
        try:
            # 1. Инициализация конфигурации
            logging.info("⚙️ Загрузка конфигурации...")
            self.config_manager = ConfigManager(self.config_path)
            
            if not self.config_manager.validate_config():
                logging.error("❌ Невалидная конфигурация")
                return False
                
            # 2. Инициализация writer'а
            output_file = self.config_manager.get_output_filename()
            logging.info(f"📁 Выходной файл: {output_file}")
            self.writer = ThreadSafeWriter(output_file)
            
            # 3. Инициализация пула потоков
            self.pool_manager = ThreadPoolManager(
                config=self.config_manager.config,
                writer=self.writer
            )
            
            logging.info("✅ Все компоненты инициализированы")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации: {e}")
            logging.debug(traceback.format_exc())
            return False
    
    def run(self) -> int:
        """
        Запуск главного цикла приложения
        
        Returns:
            Код завершения (0 - успех, 1 - ошибка)
        """
        # Инициализация
        if not self.initialize():
            return 1
            
        # Старт генерации
        logging.info("🚀 Запуск генерации диалогов...")
        self.running = True
        
        try:
            # Запуск потоков
            self.pool_manager.start_generation()
            
            # Главный цикл мониторинга
            return self._main_loop()
            
        except Exception as e:
            logging.error(f"💥 Критическая ошибка в главном цикле: {e}")
            logging.debug(traceback.format_exc())
            return 1
        finally:
            # Гарантируем очистку ресурсов
            self.stop()
    
    def _main_loop(self) -> int:
        """
        Главный цикл мониторинга
        
        Returns:
            Код завершения
        """
        last_stats_time = 0
        stats_interval = 10  # секунд между обновлением статистики
        
        while self.running:
            try:
                current_time = time.time()
                
                # Периодический вывод статистики
                if current_time - last_stats_time >= stats_interval:
                    if self.pool_manager:
                        stats = self.pool_manager.get_stats()
                        self._print_progress(stats)
                    last_stats_time = current_time
                
                # Проверка состояния потоков
                if self.pool_manager and not self.pool_manager.is_running():
                    logging.warning("⚠️ Потоки завершили работу")
                    break
                    
                # Короткая пауза для снижения нагрузки на CPU
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logging.info("🛑 Прерывание с клавиатуры...")
                break
            except Exception as e:
                logging.error(f"⚠️ Ошибка в главном цикле: {e}")
                time.sleep(5)  # Пауза при ошибке
        
        return 0
    
    def _print_progress(self, stats: dict) -> None:
        """
        Вывод прогресса генерации
        
        Args:
            stats: Статистика генерации
        """
        try:
            total_pairs = stats.get('total_pairs', 0)
            successful_pairs = stats.get('successful_pairs', 0)
            failed_pairs = stats.get('failed_pairs', 0)
            active_workers = stats.get('active_workers', 0)
            
            success_rate = (successful_pairs / total_pairs * 100) if total_pairs > 0 else 0
            
            logging.info(
                f"📊 Прогресс: {successful_pairs} успешных, "
                f"{failed_pairs} ошибок, "
                f"{active_workers} активных воркеров, "
                f"{success_rate:.1f}% успеха"
            )
            
        except Exception as e:
            logging.warning(f"⚠️ Ошибка вывода прогресса: {e}")
    
    def stop(self) -> None:
        """Безопасная остановка всех компонентов"""
        logging.info("🛑 Остановка генератора...")
        
        try:
            # Останавливаем пул потоков
            if self.pool_manager:
                self.pool_manager.stop_generation()
                
            # Закрываем writer
            if self.writer:
                self.writer.close()
                
            logging.info("✅ Генератор остановлен")
            
        except Exception as e:
            logging.error(f"⚠️ Ошибка при остановке: {e}")
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированная очистка ресурсов"""
        self.stop()


def setup_logging() -> None:
    """
    Настройка системы логирования
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(threadName)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler('generator.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Уменьшаем логирование для некоторых шумных библиотек
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)


def main() -> int:
    """
    Точка входа в приложение
    
    Returns:
        Код завершения (0 - успех, 1 - ошибка)
    """
    setup_logging()
    
    logging.info("🎬 Запуск Universal Dialog Generator")
    
    try:
        # Используем context manager для гарантии очистки ресурсов
        with UniversalDialogGenerator("config.json") as generator:
            return generator.run()
            
    except Exception as e:
        logging.error(f"💥 Фатальная ошибка: {e}")
        logging.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit_code = main()
    logging.info(f"🔚 Завершение работы с кодом: {exit_code}")
    sys.exit(exit_code)