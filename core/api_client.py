"""
Безопасный клиент для работы с OpenAI-совместимыми API с retry логикой и мониторингом
"""
import httpx
import logging
import json
import time
import random
from typing import Dict, Any, Optional, List
from openai import OpenAI
from openai.types.chat import ChatCompletion
import requests.exceptions


class APIClient:
    """
    Безопасный клиент для работы с API с retry логикой и обработкой ошибок
    """
    
    def __init__(self, api_config: Dict[str, Any]):
        """
        Инициализация API клиента
        
        Args:
            api_config: Конфигурация API
        """
        self.api_config = api_config
        self.client: Optional[OpenAI] = None
        self._initialize_client()
        
        # Статистика
        self.request_count = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_tokens_used = 0
        
        # Retry конфигурация
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 10.0
        
        logging.debug("🌐 APIClient инициализирован")
    
    def _initialize_client(self) -> None:
        """
        Инициализация OpenAI клиента с поддержкой прокси
        """
        try:
            # Настройка HTTP клиента с прокси (если указан)
            http_client_kwargs = {}
            
            # Проверяем наличие прокси в конфиге
            proxy = self.api_config.get('proxy')
            if proxy and isinstance(proxy, str) and proxy.strip():
                http_client_kwargs['proxy'] = proxy
                logging.info(f"🔌 Используется прокси: {proxy}")
            else:
                logging.debug("ℹ️ Прокси не настроен, используется прямое соединение")
            
            # Создаем HTTP клиент с прокси (если указан)
            if http_client_kwargs:
                http_client = httpx.Client(**http_client_kwargs)
            else:
                http_client = httpx.Client()
            
            self.client = OpenAI(
                base_url=self.api_config.get('base_url', 'https://api.openai.com/v1'),
                api_key=self.api_config.get('api_key'),
                timeout=self.api_config.get('timeout', 30.0),
                max_retries=0,  # Мы сами реализуем retry логику
                http_client=http_client,
            )
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации API клиента: {e}")
            raise
    
    def generate_dialog(self, prompt: str, temperature: float) -> Optional[Dict[str, Any]]:
        """
        Генерация диалога через API
        
        Args:
            prompt: Промпт для генерации
            temperature: Температура для генерации
            
        Returns:
            Сгенерированный диалог или None при ошибке
        """
        self.request_count += 1
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self._make_api_call(prompt, temperature, attempt)
                
                if response and response.choices:
                    self.successful_requests += 1
                    return self._process_response(response)
                else:
                    logging.warning(f"⚠️ Пустой ответ от API (попытка {attempt + 1})")
                    
            except Exception as e:
                self.failed_requests += 1
                error_message = f"Ошибка API (попытка {attempt + 1}/{self.max_retries + 1}): {e}"
                
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logging.warning(f"⚠️ {error_message}. Повтор через {delay:.1f}с")
                    time.sleep(delay)
                else:
                    logging.error(f"❌ {error_message}. Превышено максимальное количество попыток")
        
        return None
    
    def _make_api_call(self, prompt: str, temperature: float, attempt: int) -> Optional[ChatCompletion]:
        """
        Вызов API с обработкой специфичных ошибок
        
        Args:
            prompt: Промпт для генерации
            temperature: Температура для генерации
            attempt: Номер текущей попытки
            
        Returns:
            Ответ API или None при ошибке
        """
        try:
            # Динамический timeout в зависимости от попытки
            dynamic_timeout = self.api_config.get('timeout', 30) * (attempt + 1)
            
            response = self.client.chat.completions.create(
                model=self.api_config['model'],
                messages=[
                    {
                        "role": "system", 
                        "content": "Всегда возвращай валидный JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=self.api_config.get('max_tokens', 2000),
                timeout=dynamic_timeout,
                extra_body={"reasoning": {"enabled": self.api_config.get('enable_reasoning', False)}}
            )
            
            return response
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout ({dynamic_timeout}с)")
        except requests.exceptions.ConnectionError:
            raise Exception("Ошибка соединения")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise Exception("Превышен лимит запросов (rate limit)")
            elif e.response.status_code == 401:
                raise Exception("Неверный API ключ")
            elif e.response.status_code == 403:
                raise Exception("Доступ запрещен")
            else:
                raise Exception(f"HTTP ошибка {e.response.status_code}")
        except Exception as e:
            raise Exception(f"Неизвестная ошибка: {e}")
    
    def _process_response(self, response: ChatCompletion) -> Optional[Dict[str, Any]]:
        """
        Обработка ответа от API
        
        Args:
            response: Ответ от API
            
        Returns:
            Распарсенные данные или None при ошибке
        """
        try:
            content = response.choices[0].message.content.strip()
            if not content:
                # Пробуем взять из reasoning поля если доступно
                if hasattr(response.choices[0].message, 'reasoning') and response.choices[0].message.reasoning:
                    reasoning_parts = response.choices[0].message.reasoning.partition("</think>")
                    if reasoning_parts:
                        content = reasoning_parts[2].strip()
            
            # Удаляем маркеры кода
            content = content.replace("```json", "").replace("```", "")

            if not content:
                logging.warning("⚠️ Пустой контент в ответе API")
                return None
            
            # Парсим JSON
            data = json.loads(content)
            
            # Обновляем статистику токенов
            if response.usage:
                self.total_tokens_used += response.usage.total_tokens
            
            logging.debug(f"✅ Успешный ответ API, токенов: {response.usage.total_tokens if response.usage else 'N/A'}")
            return data
            
        except json.JSONDecodeError as e:
            logging.error(f"❌ Ошибка парсинга JSON из ответа API: {e}")
            logging.debug(f"Сырой ответ: {content[:200]}...")
            return None
        except Exception as e:
            logging.error(f"❌ Ошибка обработки ответа API: {e}")
            return None
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Расчет задержки для retry с exponential backoff и jitter
        
        Args:
            attempt: Номер попытки
            
        Returns:
            Задержка в секундах
        """
        # Exponential backoff
        delay = self.base_delay * (2 ** attempt)
        
        # Добавляем jitter (случайность)
        jitter = random.uniform(0.1, 0.3) * delay
        
        # Ограничиваем максимальную задержку
        final_delay = min(delay + jitter, self.max_delay)
        
        return final_delay
    
    def test_connection(self) -> bool:
        """
        Тестирование соединения с API
        
        Returns:
            True если соединение успешно
        """
        try:
            # Простой запрос для проверки соединения
            self.client.models.list(limit=1)
            logging.info("✅ Соединение с API успешно")
            return True
        except Exception as e:
            logging.error(f"❌ Ошибка соединения с API: {e}")
            return False
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Получение статистики использования API
        
        Returns:
            Словарь со статистикой
        """
        total_requests = self.request_count
        success_rate = (self.successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': round(success_rate, 1),
            'total_tokens_used': self.total_tokens_used,
            'estimated_cost': self._estimate_cost()
        }
    
    def _estimate_cost(self) -> float:
        """
        Оценка стоимости использованных токенов
        
        Returns:
            Примерная стоимость в USD
        """
        # Примерные цены за 1K токенов (актуальные цены нужно уточнять)
        model_prices = {
            'gpt-3.5-turbo': 0.002,  # $0.002 per 1K tokens
            'gpt-4': 0.03,            # $0.03 per 1K tokens
            'gpt-4-turbo': 0.01,      # $0.01 per 1K tokens
        }
        
        model = self.api_config.get('model', 'gpt-3.5-turbo')
        price_per_1k = model_prices.get(model, 0.002)
        
        cost = (self.total_tokens_used / 1000) * price_per_1k
        return round(cost, 4)
    
    def cleanup(self) -> None:
        """
        Очистка ресурсов клиента
        """
        try:
            if self.client:
                # Закрываем HTTP сессию если доступно
                if hasattr(self.client, '_session') and self.client._session:
                    self.client._session.close()
                
            logging.debug("🧹 APIClient ресурсы очищены")
        except Exception as e:
            logging.error(f"❌ Ошибка очистки APIClient: {e}")
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированная очистка ресурсов"""
        self.cleanup()