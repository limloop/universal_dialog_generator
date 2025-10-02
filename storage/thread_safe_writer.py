"""
Потокобезопасный writer с кроссплатформенной поддержкой и гарантированной сохранностью данных
"""

import os
import json
import logging
import threading
import time
import fcntl  # Для Linux/MacOS файловых блокировок
import platform
from typing import Dict, Any, Optional
from pathlib import Path
import errno


class FileLockException(Exception):
    """Исключение для ошибок блокировки файлов"""
    
    def __init__(self, message: str, filename: Optional[str] = None, 
                 error_code: Optional[int] = None, system: Optional[str] = None):
        """
        Инициализация исключения блокировки файла
        
        Args:
            message: Сообщение об ошибке
            filename: Имя файла для которого не удалось получить блокировку
            error_code: Код ошибки ОС (errno)
            system: Операционная система
        """
        self.message = message
        self.filename = filename
        self.error_code = error_code
        self.system = system or platform.system()
        
        # Человеко-читаемое описание ошибки
        error_details = []
        if filename:
            error_details.append(f"file: {filename}")
        if error_code:
            error_details.append(f"error_code: {error_code}")
        if system:
            error_details.append(f"system: {system}")
            
        full_message = f"{message}"
        if error_details:
            full_message += f" [{', '.join(error_details)}]"
            
        super().__init__(full_message)
    
    def __str__(self) -> str:
        return self.args[0] if self.args else self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Представление исключения в виде словаря для логирования"""
        return {
            "error": self.message,
            "filename": self.filename,
            "error_code": self.error_code,
            "system": self.system
        }


class CrossPlatformFileLock:
    """
    Кроссплатформенная файловая блокировка для Linux/Windows/MacOS
    """
    
    def __init__(self, filename: str):
        """
        Инициализация блокировки
        
        Args:
            filename: Путь к файлу для блокировки
        """
        self.filename = filename
        self.lockfile = f"{filename}.lock"
        self._lock_file = None
        self._is_locked = False
        self._system = platform.system().lower()
        
    def acquire(self, timeout: float = 10.0) -> bool:
        """
        Получение эксклюзивной блокировки файла
        
        Args:
            timeout: Таймаут в секундах
            
        Returns:
            True если блокировка получена
            
        Raises:
            FileLockException: При ошибке получения блокировки
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if self._system == "windows":
                    return self._acquire_windows()
                else:
                    return self._acquire_unix()
            except (IOError, OSError) as e:
                if e.errno != errno.EAGAIN:
                    raise FileLockException(
                        f"Системная ошибка при получении блокировки",
                        filename=self.filename,
                        error_code=e.errno,
                        system=self._system
                    )
                time.sleep(0.1)
        
        # Таймаут
        raise FileLockException(
            f"Таймаут получения блокировки",
            filename=self.filename,
            system=self._system
        )
    
    def _acquire_unix(self) -> bool:
        """Получение блокировки на Unix-системах (Linux/MacOS)"""
        try:
            self._lock_file = open(self.lockfile, 'w')
            
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._is_locked = True
                return True
            except (IOError, OSError) as e:
                self._lock_file.close()
                self._lock_file = None
                # Конкретизируем тип ошибки блокировки
                if e.errno in [errno.EAGAIN, errno.EACCES]:
                    return False  # Файл уже заблокирован - нормальная ситуация
                else:
                    raise FileLockException(
                        f"Ошибка системной блокировки файла",
                        filename=self.filename,
                        error_code=e.errno,
                        system=self._system
                    )
        except Exception as e:
            if not isinstance(e, FileLockException):
                raise FileLockException(
                    f"Неожиданная ошибка при блокировке файла: {e}",
                    filename=self.filename,
                    system=self._system
                )
            raise

    def _acquire_windows(self) -> bool:
        """Получение блокировки на Windows"""
        try:
            # На Windows используем эксклюзивное создание файла как блокировку
            self._lock_file = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            self._is_locked = True
            return True
        except (IOError, OSError) as e:
            if e.errno == errno.EEXIST:
                return False  # Файл уже существует = блокировка занята
            else:
                raise FileLockException(
                    f"Ошибка создания блокировки на Windows",
                    filename=self.filename,
                    error_code=e.errno,
                    system=self._system
                )
        except Exception as e:
            raise FileLockException(
                f"Неожиданная ошибка при блокировке на Windows: {e}",
                filename=self.filename,
                system=self._system
            )

    def release(self) -> None:
        """Освобождение блокировки"""
        if not self._is_locked:
            return
            
        try:
            if self._system == "windows" and self._lock_file:
                os.close(self._lock_file)
                os.unlink(self.lockfile)
            elif self._lock_file:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
                if os.path.exists(self.lockfile):
                    os.unlink(self.lockfile)
        except Exception as e:
            logging.warning(f"Ошибка при освобождении блокировки: {e}")
        finally:
            self._is_locked = False
            self._lock_file = None
    
    def __enter__(self):
        """Поддержка context manager"""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированное освобождение блокировки"""
        self.release()


class ThreadSafeWriter:
    """
    Потокобезопасный writer с гарантированной сохранностью данных и ротацией файлов
    """
    
    def __init__(self, 
                 filename: str, 
                 max_file_size_mb: int = 100,
                 backup_count: int = 5,
                 encoding: str = 'utf-8'):
        """
        Инициализация writer'а
        
        Args:
            filename: Путь к выходному файлу
            max_file_size_mb: Максимальный размер файла в MB перед ротацией
            backup_count: Количество хранимых backup файлов
            encoding: Кодировка файла
        """
        self.filename = Path(filename)
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Конвертация в байты
        self.backup_count = backup_count
        self.encoding = encoding
        
        # Примитивы синхронизации
        self._write_lock = threading.RLock()  # Reentrant lock для вложенных вызовов
        self._file_lock = CrossPlatformFileLock(str(self.filename))
        
        # Статистика и состояние
        self._written_count = 0
        self._error_count = 0
        self._is_closed = False
        
        # Создание директории если нужно
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        
        # Инициализация файла
        self._initialize_file()
        
        logging.info(f"📝 ThreadSafeWriter инициализирован для {self.filename}")
    
    def _initialize_file(self) -> None:
        """Инициализация файла и проверка целостности"""
        with self._write_lock:
            try:
                # Проверяем существующий файл на целостность JSONL
                if self.filename.exists():
                    self._validate_existing_file()
                    self._update_written_count()
                else:
                    # Создаем новый файл
                    with open(self.filename, 'w', encoding=self.encoding) as f:
                        f.write("")  # Создаем пустой файл
                    
                    logging.info(f"✅ Создан новый файл: {self.filename}")
                    
            except Exception as e:
                logging.error(f"❌ Ошибка инициализации файла {self.filename}: {e}")
                raise
    
    def _validate_existing_file(self) -> None:
        """Валидация целостности существующего файла"""
        try:
            with open(self.filename, 'r', encoding=self.encoding) as f:
                lines = f.readlines()
                
            # Проверяем каждую строку на валидность JSON
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line:  # Пропускаем пустые строки
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        logging.warning(f"⚠️ Невалидная JSON строка {i} в {self.filename}: {e}")
                        
            logging.info(f"✅ Файл {self.filename} прошел валидацию, строк: {len(lines)}")
            
        except Exception as e:
            logging.error(f"❌ Ошибка валидации файла {self.filename}: {e}")
            # Создаем backup поврежденного файла
            self._backup_corrupted_file()
            raise
    
    def _backup_corrupted_file(self) -> None:
        """Создание backup поврежденного файла"""
        try:
            timestamp = int(time.time())
            backup_name = self.filename.with_suffix(f".corrupted.{timestamp}.jsonl")
            self.filename.rename(backup_name)
            logging.warning(f"📦 Создан backup поврежденного файла: {backup_name}")
        except Exception as e:
            logging.error(f"❌ Ошибка создания backup поврежденного файла: {e}")
    
    def _update_written_count(self) -> None:
        """Обновление счетчика записанных строк"""
        try:
            with open(self.filename, 'r', encoding=self.encoding) as f:
                lines = [line for line in f.readlines() if line.strip()]
            self._written_count = len(lines)
        except Exception as e:
            logging.warning(f"⚠️ Не удалось обновить счетчик строк: {e}")
            self._written_count = 0
    
    def _needs_rotation(self) -> bool:
        """Проверка необходимости ротации файла"""
        try:
            if not self.filename.exists():
                return False
            return self.filename.stat().st_size >= self.max_file_size
        except OSError as e:
            logging.warning(f"⚠️ Ошибка проверки размера файла: {e}")
            return False
    
    def _rotate_file(self) -> None:
        """Ротация файла при достижении максимального размера"""
        with self._write_lock:
            try:
                if not self._needs_rotation():
                    return
                
                logging.info(f"🔄 Ротация файла {self.filename} (размер: {self.filename.stat().st_size})")
                
                # Удаляем самый старый backup если нужно
                oldest_backup = self.filename.with_suffix(f".{self.backup_count}.jsonl")
                if oldest_backup.exists():
                    oldest_backup.unlink()
                
                # Сдвигаем существующие backups
                for i in range(self.backup_count - 1, 0, -1):
                    old_backup = self.filename.with_suffix(f".{i}.jsonl")
                    new_backup = self.filename.with_suffix(f".{i + 1}.jsonl")
                    if old_backup.exists():
                        old_backup.rename(new_backup)
                
                # Создаем новый backup
                first_backup = self.filename.with_suffix(".1.jsonl")
                self.filename.rename(first_backup)
                
                # Создаем новый пустой файл
                with open(self.filename, 'w', encoding=self.encoding) as f:
                    f.write("")
                
                self._written_count = 0
                logging.info(f"✅ Ротация завершена, создан backup: {first_backup}")
                
            except Exception as e:
                logging.error(f"❌ Ошибка ротации файла: {e}")
                raise
    
    def write_dialog(self, dialog_data: Dict[str, Any]) -> bool:
        """
        Потокобезопасная запись диалога в файл
        
        Args:
            dialog_data: Данные диалога для записи
            
        Returns:
            True если запись успешна
        """
        if self._is_closed:
            logging.error("❌ Попытка записи в закрытый writer")
            return False
        
        with self._write_lock:
            try:
                # Проверяем и выполняем ротацию если нужно
                self._rotate_file()
                
                # Получаем эксклюзивную блокировку файла
                with self._file_lock:
                    # Сериализуем данные
                    json_line = json.dumps(dialog_data, ensure_ascii=False)
                    
                    # Атомарная запись в файл
                    with open(self.filename, 'a', encoding=self.encoding) as f:
                        f.write(json_line + '\n')
                        f.flush()  # Принудительная запись на диск
                        os.fsync(f.fileno())  # Гарантируем запись на физический носитель
                    
                    self._written_count += 1
                    
                    if self._written_count % 100 == 0:
                        logging.info(f"📝 Записано {self._written_count} диалогов в {self.filename}")
                    
                    return True
                    
            except FileLockException as e:
                logging.error(f"🔒 Ошибка блокировки файла: {e}")
                self._error_count += 1
                return False
            except Exception as e:
                logging.error(f"❌ Ошибка записи диалога: {e}")
                self._error_count += 1
                return False
    
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики writer'а
        
        Returns:
            Словарь со статистикой
        """
        return {
            "filename": str(self.filename),
            "written_count": self._written_count,
            "error_count": self._error_count,
            "is_closed": self._is_closed,
            "file_size_mb": self.filename.stat().st_size / (1024 * 1024) if self.filename.exists() else 0
        }
    
    def close(self) -> None:
        """Безопасное закрытие writer'а"""
        if self._is_closed:
            return
        
        with self._write_lock:
            try:
                self._is_closed = True
                self._file_lock.release()
                logging.info(f"🔚 ThreadSafeWriter закрыт. Статистика: {self.get_stats()}")
            except Exception as e:
                logging.error(f"❌ Ошибка при закрытии writer'а: {e}")
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированное закрытие"""
        self.close()