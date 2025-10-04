#!/usr/bin/env python3
"""
Скрипт для очистки диалогов от китайских иероглифов, опечаток и артефактов генерации
"""

import json
import logging
import re
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path

# Добавляем путь к корневой директории для импортов
sys.path.append(str(Path(__file__).parent.parent))

from core.api_client import APIClient
from config.config_manager import ConfigManager


class DialogCleaner:
    """
    Очистка диалогов от артефактов с использованием AI
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация очистителя
        
        Args:
            config_path: Путь к конфигурационному файлу
        """
        self.config_manager = ConfigManager(config_path)
        self.api_client = APIClient(self.config_manager.get_api_config())
        
        # Паттерны для обнаружения артефактов
        self.artifact_patterns = [
            r'[\u4e00-\u9fff]',  # Китайские иероглифы
            r'[\u3040-\u309f]',  # Хирагана (японский)
            r'[\u30a0-\u30ff]',  # Катакана (японский)
            r'[�]',  # Символы замены
        ]
        
        logging.info("🧹 DialogCleaner инициализирован")
    
    def has_artifacts(self, text: str) -> bool:
        """
        Проверка наличия артефактов в тексте
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если найдены артефакты
        """
        for pattern in self.artifact_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def build_cleaning_prompt(self, theme: str, text: str, language: str) -> str:
        """
        Создание промпта для очистки текста
        
        Args:
            theme: Тема диалога
            text: Текст для очистки
            language: Язык текста
            
        Returns:
            Промпт для AI
        """
        language_names = {
            'ru': 'русском',
            'en': 'английском', 
            'de': 'немецком',
            'fr': 'французском',
            'es': 'испанском',
            'it': 'итальянском',
            'zh': 'китайском',
            'ja': 'японском'
        }
        
        lang_name = language_names.get(language, language)
        
        prompt = f"""
Тема диалога: "{theme}"

Получена строка текста на {lang_name} языке, которая может содержать китайские/японские символы, опечатки или грамматические ошибки.

Исходный текст: "{text}"

Задача:
1. Заменить все китайские/японские символы на эквиваленты на {lang_name} языке
2. Исправить грамматические ошибки и опечатки
3. Сохранить исходный стиль и смысл высказывания
4. Не добавлять дополнительный текст

Формат ответа (JSON):
{{
    "cleaned_text": "исправленная строка текста"
}}

ВАЖНО: Верни только JSON объект без дополнительного текста.
"""
        return prompt.strip()
    
    def clean_single_line(self, theme: str, text: str, language: str) -> Optional[str]:
        """
        Очистка одной строки текста
        
        Args:
            theme: Тема диалога
            text: Текст для очистки
            language: Язык текста
            
        Returns:
            Очищенный текст или None при ошибке
        """
        try:
            # Если нет артефактов, возвращаем оригинал
            if not self.has_artifacts(text):
                return text
            
            logging.info(f"🧹 Очистка строки: {text[:50]}...")
            
            prompt = self.build_cleaning_prompt(theme, text, language)
            
            # Используем низкую температуру для детерминированного исправления
            response = self.api_client.generate_dialog(prompt, temperature=0.1)
            
            if response and 'cleaned_text' in response:
                cleaned_text = response['cleaned_text']
                logging.debug(f"✅ Очищено: {text[:30]}... → {cleaned_text[:30]}...")
                return cleaned_text
            else:
                logging.warning(f"⚠️ Неверный формат ответа от API: {response}")
                return text
                
        except Exception as e:
            logging.error(f"❌ Ошибка очистки строки: {e}")
            return text
    
    def clean_dialog_file(self, input_file: str, output_file: str, batch_size: int = 10) -> bool:
        """
        Очистка всего файла с диалогами
        
        Args:
            input_file: Входной файл с диалогами
            output_file: Выходной файл для очищенных диалогов
            batch_size: Размер батча для обработки
            
        Returns:
            True если успешно
        """
        try:
            input_path = Path(input_file)
            output_path = Path(output_file)
            
            if not input_path.exists():
                logging.error(f"❌ Входной файл не найден: {input_file}")
                return False
            
            # Читаем все диалоги
            dialogs = []
            with open(input_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            dialogs.append(data)
                        except json.JSONDecodeError as e:
                            logging.warning(f"⚠️ Ошибка JSON в строке {line_num}: {e}")
            
            total_dialogs = len(dialogs)
            cleaned_count = 0
            
            # Обрабатываем батчами
            for i in range(0, total_dialogs, batch_size):
                batch = dialogs[i:i + batch_size]
                logging.info(f"🔧 Обработка батча {i//batch_size + 1}/{(total_dialogs + batch_size - 1)//batch_size}")
                
                for dialog in batch:
                    try:
                        original_dialog = dialog.copy()
                        cleaned_dialog = self.clean_single_dialog(dialog)
                        
                        # Проверяем, были ли изменения
                        if cleaned_dialog != original_dialog:
                            cleaned_count += 1
                        
                        # Записываем результат
                        with open(output_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(cleaned_dialog, ensure_ascii=False) + '\n')
                            
                    except Exception as e:
                        logging.error(f"❌ Ошибка обработки диалога: {e}")
                        # Записываем оригинал при ошибке
                        with open(output_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(dialog, ensure_ascii=False) + '\n')
            
            logging.info(f"🎯 Очистка завершена. Обработано: {total_dialogs}, очищено: {cleaned_count}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка очистки файла: {e}")
            return False
    
    def clean_single_dialog(self, dialog_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Очистка одного диалога
        
        Args:
            dialog_data: Данные диалога
            
        Returns:
            Очищенный диалог
        """
        try:
            if 'dialog' not in dialog_data or not isinstance(dialog_data['dialog'], list):
                return dialog_data
            
            cleaned_dialog = []
            theme = dialog_data.get('theme', '')
            language = dialog_data.get('language', 'ru')
            needs_cleaning = False
            
            for text in dialog_data['dialog']:
                if self.has_artifacts(text):
                    needs_cleaning = True
                    cleaned_text = self.clean_single_line(theme, text, language)
                    cleaned_dialog.append(cleaned_text)
                else:
                    cleaned_dialog.append(text)
            
            if needs_cleaning:
                dialog_data['dialog'] = cleaned_dialog
                # Добавляем метку о очистке
                dialog_data['cleaned'] = True
            
            return dialog_data
            
        except Exception as e:
            logging.error(f"❌ Ошибка очистки диалога: {e}")
            return dialog_data
    
    def analyze_file_artifacts(self, input_file: str) -> Dict[str, Any]:
        """
        Анализ файла на наличие артефактов
        
        Args:
            input_file: Входной файл для анализа
            
        Returns:
            Статистика по артефактам
        """
        try:
            input_path = Path(input_file)
            if not input_path.exists():
                return {"error": "File not found"}
            
            stats = {
                "total_dialogs": 0,
                "dialogs_with_artifacts": 0,
                "total_lines": 0,
                "lines_with_artifacts": 0,
                "artifact_types": {},
                "sample_artifacts": []
            }
            
            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        stats["total_dialogs"] += 1
                        
                        if 'dialog' in data and isinstance(data['dialog'], list):
                            dialog_has_artifacts = False
                            
                            for text in data['dialog']:
                                stats["total_lines"] += 1
                                
                                for pattern in self.artifact_patterns:
                                    matches = re.findall(pattern, text)
                                    if matches:
                                        stats["lines_with_artifacts"] += 1
                                        dialog_has_artifacts = True
                                        
                                        # Собираем статистику по типам артефактов
                                        artifact_type = "chinese" if '\u4e00' <= matches[0] <= '\u9fff' else \
                                                       "japanese_hiragana" if '\u3040' <= matches[0] <= '\u309f' else \
                                                       "japanese_katakana" if '\u30a0' <= matches[0] <= '\u30ff' else \
                                                       "replacement_char"
                                        
                                        stats["artifact_types"][artifact_type] = stats["artifact_types"].get(artifact_type, 0) + 1
                                        
                                        # Сохраняем примеры
                                        if len(stats["sample_artifacts"]) < 5:
                                            stats["sample_artifacts"].append({
                                                "text": text[:100],
                                                "artifacts": matches[:3]
                                            })
                                        break
                            
                            if dialog_has_artifacts:
                                stats["dialogs_with_artifacts"] += 1
                                
                    except json.JSONDecodeError:
                        continue
            
            return stats
            
        except Exception as e:
            logging.error(f"❌ Ошибка анализа файла: {e}")
            return {"error": str(e)}


def main():
    """
    Главная функция скрипта очистки
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Очистка диалогов от артефактов')
    parser.add_argument('--input', '-i', help='Входной файл с диалогами')
    parser.add_argument('--output', '-o', help='Выходной файл')
    parser.add_argument('--config', '-c', default='config.json', help='Файл конфигурации')
    parser.add_argument('--analyze', '-a', action='store_true', help='Только анализ файла')
    parser.add_argument('--batch-size', '-b', type=int, default=10, help='Размер батча для обработки')
    
    args = parser.parse_args()
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    try:
        cleaner = DialogCleaner(args.config)
        
        if args.analyze and args.input:
            # Режим анализа
            stats = cleaner.analyze_file_artifacts(args.input)
            print("\n📊 Анализ артефактов в файле:")
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            sys.exit(0)
            
        elif args.input and args.output:
            # Режим очистки
            success = cleaner.clean_dialog_file(args.input, args.output, args.batch_size)
            
            if success:
                logging.info(f"✅ Файл успешно обработан: {args.input} -> {args.output}")
                sys.exit(0)
            else:
                logging.error("❌ Ошибка обработки файла")
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()