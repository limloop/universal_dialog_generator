"""
Универсальный загрузчик датасетов (локальные файлы + Hugging Face)
"""

import json
import jsonlines
import logging
from typing import Dict, Any, Iterator, Optional, List
from pathlib import Path

class DatasetLoader:
    """Загрузчик датасетов из разных источников"""
    
    def __init__(self, dataset_config: Dict[str, Any]):
        self.config = dataset_config
        self.source = dataset_config.get('source', 'local')
        
    def load_items(self) -> Iterator[Dict[str, Any]]:
        """
        Итерирует по элементам датасета
        
        Returns:
            Генератор словарей с полями id (если есть) и text
        """
        if self.source == 'huggingface':
            return self._load_from_huggingface()
        else:
            return self._load_from_local()
    
    def _load_from_huggingface(self):
        """Загрузка из Hugging Face datasets"""
        try:
            from datasets import load_dataset
            
            dataset_path = self.config['path']
            split = self.config.get('split', 'train')
            
            logging.info(f"📚 Загрузка датасета из Hugging Face: {dataset_path} (split: {split})")
            dataset = load_dataset(dataset_path, split=split)
            
            # Применяем фильтры если есть
            if 'filter' in self.config:
                for field, value in self.config['filter'].items():
                    dataset = dataset.filter(lambda x: x[field] == value)
            
            # Ограничиваем количество
            if 'limit' in self.config:
                dataset = dataset.select(range(min(self.config['limit'], len(dataset))))
            
            fields = self.config['fields']
            id_field = fields.get('id')
            text_field = fields['text']
            
            for idx, item in enumerate(dataset):
                yield {
                    'id': item.get(id_field, idx) if id_field else idx,
                    'text': item[text_field]
                }
                
        except ImportError:
            logging.error("❌ datasets библиотека не установлена. Установите: pip install datasets")
            raise
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки из Hugging Face: {e}")
            raise
    
    def _load_from_local(self):
        """Загрузка из локального файла (JSON, JSONL или CSV)"""
        file_path = self.config['path']
        file_ext = Path(file_path).suffix.lower()
        
        logging.info(f"📁 Загрузка локального датасета: {file_path}")
        
        items = []
        fields = self.config['fields']
        id_field = fields.get('id')
        text_field = fields['text']
        
        if file_ext == '.jsonl':
            with jsonlines.open(file_path) as reader:
                for idx, obj in enumerate(reader):
                    items.append({
                        'id': obj.get(id_field, idx) if id_field else idx,
                        'text': obj[text_field]
                    })
        elif file_ext == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for idx, obj in enumerate(data):
                        items.append({
                            'id': obj.get(id_field, idx) if id_field else idx,
                            'text': obj[text_field]
                        })
                else:
                    raise ValueError("JSON файл должен содержать массив объектов")
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_ext}")
        
        # Применяем лимит
        if 'limit' in self.config and self.config['limit'] < len(items):
            items = items[:self.config['limit']]
        
        for item in items:
            yield item