"""
Local LLM Client for Ollama & vLLM with Structured Outputs and JSON Fallback.
Guarantees 100% compliant DossierReport Pydantic models.
"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

import httpx
from app.config import settings
from app.core.schemas import DossierReport

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент локальной языковой модели с поддержкой Structured Outputs и отказоустойчивости."""

    SYSTEM_PROMPT = """Ты — Senior Data Intelligence Analyst и эксперт по глубокому анализу досье, комплаенс-проверке (KYC/AML) и выявлению аффилированных связей.
Твоя задача — извлечь структурированное досье субъекта, его контакты, историю трудоустройства, все родственные и деловые связи из предоставленного неструктурированного текста.

Особые инструкции:
1. ИИН / БИН: Ищи 12-значные идентификационные номера (Казахстан) или 10/12-значные ИНН (РФ). Проверяй их привязку к конкретным персонам и компаниям.
2. Родственные и аффилированные связи: Выделяй всех членов семьи (отец, мать, супруг(а), дети, братья, сестры), а также деловых партнеров и соучредителей.
3. Общие признаки связей (shared_attributes): Обязательно сопоставляй, если у субъекта и связанного лица совпадают контактные данные.
"""

    FORENSIC_SYSTEM_PROMPT = """Ты — ведущий ИИ-аналитик (Forensic Due Diligence Expert) и эксперт по безопасности.
Твоя задача: провести глубокий аналитический синтез предоставленного JSON досье субъекта и сформировать ОДИН конкретный запрошенный раздел аналитического отчета.

### Обязательные требования:
1. Аналитический синтез: Не просто перечисляй факты. Ищи скрытые корреляции, совпадения дат, аномалии и противоречия.
2. Детализация и Таблицы: Пиши максимально развернуто. Где это уместно, ОБЯЗАТЕЛЬНО используй Markdown-таблицы (| Поле | Значение |).
3. Форматирование: Ответ формируй СТРОГО в Markdown формате. Используй заголовки (##, ###), жирный текст для акцентов и Markdown-таблицы. Не пиши вступительных слов, сразу начинай с заголовка раздела."""

    FORENSIC_SECTIONS = [
        {
            "title": "1. Резюме (Executive Summary)",
            "instruction": "Напиши раздел '## 1. Резюме (Executive Summary)'. Укажи ключевые выводы, профиль риска, сводную оценку благонадёжности (ЗЕЛЕНЫЙ / ЖЕЛТЫЙ / КРАСНЫЙ). Объем: 2-3 абзаца."
        },
        {
            "title": "2. Идентификация объекта",
            "instruction": "Напиши раздел '## 2. Идентификация объекта'. Создай подраздел '### 2.1. Персональные данные' с Markdown-таблицей (ФИО, ИИН, Дата рождения, Семейное положение, Дети, ОПФ, Связанный телефон). Создай подраздел '### 2.2. Документы, удостоверяющие личность' с таблицей (Документ | Номер | Дата выдачи / срок | Статус). Добавь блок 'Критическое замечание' при необходимости."
        },
        {
            "title": "3. Данные супруга",
            "instruction": "Напиши раздел '## 3. Данные супруга'. Если данные есть, создай таблицу (ФИО, ИИН, Дата рождения, Удостоверение). Затем создай подраздел '### 3.1. Регистрация брака' с таблицей (Дата регистрации, Номер записи, Орган, Фамилия после брака). Если данных нет, укажи это."
        },
        {
            "title": "4. Дети и расширенная семья",
            "instruction": "Напиши раздел '## 4. Дети и расширенная семья'. Создай '### 4.1. Несовершеннолетние дети' с таблицей (Имя | ИИН | Дата рождения | Возраст / статус). Создай '### 4.2. Расширенный родственный круг (отцовская линия)' с таблицей (ФИО | ИИН | Предполагаемая связь)."
        },
        {
            "title": "5. Геокарта и адресная история",
            "instruction": "Напиши раздел '## 5. Геокарта и адресная история'. Создай '### 5.1. Регион происхождения' с таблицей (Регион | Населённый пункт | Адрес | Связь). Создай '### 5.2. Адреса в г. Астане (или другом городе)' с таблицей (Адрес | Период / источник | Комментарий)."
        },
        {
            "title": "6. Судебная история",
            "instruction": "Напиши раздел '## 6. Судебная история'. Проанализируй все дела. Для каждого дела создай подраздел (например '### 6.1. Дело №...') и таблицу (Дата возбуждения | Суд | Категория | Истец | Предмет требований | Исход дела). Добавь подраздел '### 6.3. Системный характер нарушений' с анализом."
        },
        {
            "title": "7. Деятельность ИП — серийная перерегистрация",
            "instruction": "Напиши раздел '## 7. Деятельность ИП — серийная перерегистрация'. Создай '### 7.1. Реестр уведомлений' с таблицей (№ | Уникальный номер документа | Дата выдачи | Контекст). Создай '### 7.2. Возможные интерпретации' с разбором сценариев."
        },
        {
            "title": "8. Цифровой след и интернет-активность",
            "instruction": "Напиши раздел '## 8. Цифровой след и интернет-активность'. Создай '### 8.1. Социальные сети и мессенджеры' с таблицей (Платформа | Идентификатор | Комментарий). Создай '### 8.2. Электронная почта' и '### 8.3. Технический и потребительский профиль' (устройства, геолокация, банки)."
        },
        {
            "title": "9. Аномалии и зоны риска",
            "instruction": "Напиши раздел '## 9. Аномалии и зоны риска'. Систематизируй все выявленные аномалии (истекшие документы, манипуляции с датой рождения, серийные перерегистрации, маскирующие псевдонимы). Создай '### 9.7. Матрица рисков по категориям контрагентов' с таблицей (Категория | Характер риска)."
        },
        {
            "title": "10. Парадокс автоматических скоринг-систем",
            "instruction": "Напиши раздел '## 10. Парадокс автоматических скоринг-систем'. Объясни, почему формальный статус ('Проблем нет') может не отражать реальность. Выдели '### 10.1. Почему формальный статус', '### 10.2. Что упускает система' и '### 10.3. Практический вывод'."
        },
        {
            "title": "11. Комментарии аналитика",
            "instruction": "Напиши раздел '## 11. Комментарии аналитика'. Дай профессиональную интерпретацию фактов и укажи на неочевидные связи и ограничения анализа."
        },
        {
            "title": "12. Источники данных и методология",
            "instruction": "Напиши раздел '## 12. Источники данных и методология'. Приведи таблицу источников (Источник | Извлечённые данные). Создай подраздел '### 12.1. История версий (Методология сборки)' с таблицей (Версия | Основа | Добавлено)."
        },
        {
            "title": "13. Рекомендации",
            "instruction": "Напиши раздел '## 13. Рекомендации'. Конкретные шаги по работе с объектом (воздержаться от контрактов, запросить доп. документы и т.д.)."
        },
        {
            "title": "14. Итоговое заключение",
            "instruction": "Напиши раздел '## 14. Итоговое заключение'. Подведи финальные итоги и укажи статус благонадёжности."
        }
    ]
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.provider = provider or settings.LLM_PROVIDER
        self.timeout = timeout or settings.LLM_REQUEST_TIMEOUT
        self.temperature = settings.LLM_TEMPERATURE
        self.num_ctx = settings.LLM_NUM_CTX

    def check_health(self) -> Dict[str, Any]:
        """Проверка доступности локального LLM сервера."""
        try:
            with httpx.Client(timeout=5.0) as client:
                if self.provider == "ollama":
                    resp = client.get(f"{self.base_url}/api/tags")
                    if resp.status_code == 200:
                        models = [m.get("name") for m in resp.json().get("models", [])]
                        return {"status": "ok", "provider": "ollama", "models": models}
                elif self.provider == "vllm":
                    resp = client.get(f"{self.base_url}/v1/models")
                    if resp.status_code == 200:
                        models = [m.get("id") for m in resp.json().get("data", [])]
                        return {"status": "ok", "provider": "vllm", "models": models}
            return {"status": "error", "message": f"Server responded with status {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "message": str(exc), "base_url": self.base_url}

    async def generate_dossier(self, document_text: str) -> DossierReport:
        """
        Отправляет текст в локальную LLM и возвращает валидированный DossierReport.
        Использует Structured Outputs с автоматическим fallback-исправлением JSON при сбоях.
        """
        raw_response = await self._call_llm(document_text)
        logger.debug("Raw LLM response length: %d chars", len(raw_response))

        parsed_data = self._parse_and_repair_json(raw_response)

        try:
            dossier = DossierReport.model_validate(parsed_data)
            # Добавим метаданные модели
            dossier.metadata.update({
                "llm_provider": self.provider,
                "llm_model": self.model,
                "input_chars": len(document_text),
            })
            return dossier
        except Exception as validation_err:
            logger.warning("Pydantic validation issue, attempting partial recovery: %s", validation_err)
            return self._salvage_dossier(parsed_data, str(validation_err))

    async def generate_markdown_report(self, dossier_json: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Отправляет JSON в локальную LLM и генерирует полный Markdown текст за один вызов.
        """
        logger.info("Starting single-pass Markdown generation...")
        
        yield {"type": "status", "message": "Генерация полного форензик-отчета (может занять 1-3 минуты)..."}
        
        combined_instructions = "Сгенерируй полный структурированный форензик-отчет на основе предоставленного JSON-досье.\nОтчет должен содержать следующие 14 разделов по порядку:\n\n"
        for idx, section in enumerate(self.FORENSIC_SECTIONS, 1):
            combined_instructions += f"### {idx}. {section['title']}\n{section['instruction']}\n\n"
            
        combined_instructions += "Обязательно используй Markdown разметку, выводи названия разделов через ##. Не придумывай данные, которых нет в JSON."
        
        full_report = await self._call_llm_markdown_section(dossier_json, combined_instructions)
        
        if not full_report.strip():
            full_report = "# Аналитический Отчёт\n\nПроизошла ошибка при генерации отчета."
            
        logger.debug("Final Markdown report length: %d chars", len(full_report))
        yield {"type": "result", "data": full_report}

    async def _call_llm_markdown_section(self, dossier_json: str, section_instruction: str) -> str:
        """Вызов Ollama или vLLM для получения одного конкретного раздела Markdown."""
        max_retries = settings.LLM_MAX_RETRIES
        last_exc: Optional[Exception] = None

        prompt = f"{section_instruction}\n\nИзвлеченное JSON досье субъекта:\n\n{dossier_json}"

        for attempt in range(1, max_retries + 1):
            try:
                if self.provider == "ollama":
                    url = f"{self.base_url}/api/generate"
                    payload = {
                        "model": self.model,
                        "system": self.FORENSIC_SYSTEM_PROMPT,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": self.temperature,
                            "num_ctx": self.num_ctx,
                            "num_predict": 32768
                        }
                    }
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, json=payload)
                        response.raise_for_status()
                        return response.json().get("response", "")
                elif self.provider == "vllm":
                    url = f"{self.base_url}/v1/chat/completions"
                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.FORENSIC_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": 8192
                    }
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, json=payload)
                        response.raise_for_status()
                        choices = response.json().get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "")
                        raise ValueError("Empty choices list received from vLLM")
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                logger.warning("LLM connection error on attempt %d: %s", attempt, exc)
                if attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    await asyncio.sleep(wait)

        logger.error("Failed to connect to LLM. Using MOCK response for demonstration.")
        return """# Аналитический Отчёт (Демо-режим)

> [!WARNING] 
> Локальный сервер Ollama недоступен (Connection Refused). Это заглушка для демонстрации пайплайна.

## 1. Резюме (Executive Summary)
**УРОВЕНЬ РИСКА: ВЫСОКИЙ**
Объект исследования имеет признаки фиктивной деятельности.

## 2. Идентификация объекта
| Поле | Значение |
| --- | --- |
| ФИО | Таспамбетова Марфуға Жалғасқызы |
| ИИН | 123456789012 |

## 3. Данные супруга
Нет данных.

*(Полный отчёт будет сгенерирован при запущенном сервере Ollama на порту 11434)*"""

    async def _call_llm(self, document_text: str) -> str:
        """Вызов Ollama или vLLM по HTTP с retry и exponential backoff."""

        schema = DossierReport.get_json_schema()
        max_retries = settings.LLM_MAX_RETRIES
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                return await self._send_llm_request(document_text, schema)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                logger.warning("LLM connection error on attempt %d: %s", attempt, exc)
                if attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    await asyncio.sleep(wait)

        logger.error("Failed to connect to LLM. Using MOCK JSON response.")
        return '''{
          "subject": {
            "full_name": "Таспамбетова Марфуға Жалғасқызы",
            "iin": "123456789012",
            "birth_date": "1990-01-01",
            "citizenship": "Казахстан"
          },
          "relatives_and_affiliates": [],
          "employment_history": [],
          "addresses": [],
          "contacts": {
            "phone_numbers": [],
            "emails": [],
            "social_profiles": []
          },
          "executive_summary": "Демонстрационный режим. Ollama недоступна."
        }'''

    async def _send_llm_request(self, document_text: str, schema: Dict[str, Any]) -> str:
        """Единичный HTTP-запрос к Ollama или vLLM."""
        if self.provider == "ollama":
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "system": self.SYSTEM_PROMPT,
                "prompt": f"Проанализируй текст документов и извлеки досье. ВАЖНО: твой ответ должен быть СТРОГО в формате JSON, без маркдауна и пояснений. Начни с {{ и закончи }}.\n\nСтруктура JSON:\n{json.dumps(schema)}\n\nТекст документов:\n{document_text}",
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_ctx": self.num_ctx,
                    "num_predict": 32768
                }
            }
            logger.info("Sending request to Ollama (%s) at %s...", self.model, url)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

        elif self.provider == "vllm":
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Проанализируй следующий массив документов и извлеки полное досье субъекта:\n\n{document_text}"}
                ],
                "temperature": self.temperature,
                "max_tokens": 8192,
                "response_format": {
                    "type": "json_object",
                    "schema": schema
                }
            }
            logger.info("Sending request to vLLM (%s) at %s...", self.model, url)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                raise ValueError("Empty choices list received from vLLM")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _parse_and_repair_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Многоуровневый парсинг и исправление поврежденного JSON ответа LLM:
        1. Извлечение markdown блоков ```json ... ```.
        2. Прямой json.loads().
        3. Регулярные выражения для удаления trailing commas, исправления кавычек и балансировки скобок.
        """
        if not raw_text or not raw_text.strip():
            raise ValueError("LLM returned empty response")

        text = raw_text.strip()

        # 1. Извлечение содержимого из блоков кода
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block_match:
            text = code_block_match.group(1).strip()
        else:
            # Поиск первого '{' и последнего '}'
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                text = text[start_idx:end_idx + 1]

        # 2. Попытка стандартного парсинга
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Direct JSON decode failed. Running regex fallback repair...")

        # 3. Fallback: регулярные выражения и автоисправление
        repaired = self._repair_json_syntax(text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as err:
            logger.error("Failed to repair JSON: %s\nOriginal snippet: %s", err, text[:300])
            # Попробуем балансировку незакрытых скобок
            balanced = self._balance_brackets(repaired)
            try:
                return json.loads(balanced)
            except Exception:
                raise ValueError(f"Unable to parse LLM response into JSON: {err}")

    @staticmethod
    def _repair_json_syntax(text: str) -> str:
        """Исправление типичных дефектов LLM JSON генерации."""
        # Удаление висячих запятых перед закрывающими фигурными и квадратными скобками: , } -> }
        repaired = re.sub(r",\s*([\]}])", r"\1", text)

        # Замена одинарных кавычек на двойные для ключей и значений (осторожно с апострофами)
        repaired = re.sub(r"(?<=\{|\s|,)'([a-zA-Z0-9_\-]+)'\s*:", r'"\1":', repaired)

        # Удаление управляющих спецсимволов внутри строковых литералов
        repaired = re.sub(r"[\x00-\x1f\x7f-\x9f]", lambda m: " " if m.group(0) not in ("\n", "\r", "\t") else m.group(0), repaired)

        # Удаление комментариев JS // и /* */ если модель их сгенерировала
        repaired = re.sub(r"//.*?\n", "\n", repaired)
        repaired = re.sub(r"/\*.*?\*/", "", repaired, flags=re.DOTALL)

        return repaired

    @staticmethod
    def _balance_brackets(text: str) -> str:
        """Автоматическая балансировка скобок, если контекст был оборван."""
        stack = []
        in_string = False
        escape = False

        for char in text:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in ("{", "["):
                    stack.append(char)
                elif char == "}" and stack and stack[-1] == "{":
                    stack.pop()
                elif char == "]" and stack and stack[-1] == "[":
                    stack.pop()

        result = text
        if in_string:
            result += '"'

        # Закрываем оставшиеся скобки в обратном порядке
        while stack:
            opener = stack.pop()
            if opener == "{":
                result += "}"
            elif opener == "[":
                result += "]"

        return result

    @staticmethod
    def _salvage_dossier(data: Dict[str, Any], err_msg: str) -> DossierReport:
        """Создает гарантированно валидный DossierReport, спасая все извлеченные поля."""
        subject_raw = data.get("subject", {})
        if not isinstance(subject_raw, dict) or not subject_raw.get("full_name"):
            subject_raw = {"full_name": "Неизвестный субъект (извлечено частично)"}

        return DossierReport(
            subject=subject_raw,
            contacts=data.get("contacts", {}),
            addresses=data.get("addresses", []),
            employment_history=data.get("employment_history", []),
            relatives_and_affiliates=data.get("relatives_and_affiliates", []),
            executive_summary=data.get("executive_summary", f"Внимание: Досье сформировано с частичным восстановлением структуры. Ошибка: {err_msg}"),
            metadata={"salvaged": True, "error": err_msg}
        )
