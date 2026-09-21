"""
Text cleaning, deduplication, and compression module.
Prepares parsed text for local LLM consumption while minimizing token usage.
"""

import re
import unicodedata
from typing import List, Optional


class TextCleaner:
    """Очиститель и оптимизатор текста для экономной передачи в LLM."""

    # Регулярные выражения для типовых артефактов
    PAGE_NUMBER_PATTERN = re.compile(
        r"(?:страница|стр\.?|page)\s*\d+(?:\s*(?:из|of|\/)\s*\d+)?",
        re.IGNORECASE
    )
    ASCII_TABLE_BORDERS = re.compile(r"^[\|\+\-\=\s]{4,}$", re.MULTILINE)
    MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
    MULTIPLE_SPACES = re.compile(r"[ \t]{2,}")
    REPEATED_CHARS = re.compile(r"([.\-_=~*])\1{4,}")

    @classmethod
    def clean(
        cls,
        text: str,
        remove_duplicate_paragraphs: bool = True,
        max_length: Optional[int] = None
    ) -> str:
        """
        Основной метод очистки:
        1. Нормализация Unicode (NFKC, удаление невидимых символов).
        2. Удаление колонтитулов, нумерации страниц, мусорных границ таблиц.
        3. Сжатие лишних пробелов и пустых строк.
        4. Дедупликация повторяющихся фрагментов/абзацев.
        5. Ограничение максимальной длины при необходимости.
        """
        if not text:
            return ""

        # 1. Нормализация Unicode
        cleaned = unicodedata.normalize("NFKC", text)
        # Удаление управляющих и невидимых символов (кроме перевода строк и табуляции)
        cleaned = "".join(
            ch for ch in cleaned
            if ch in ("\n", "\r", "\t") or not unicodedata.category(ch).startswith("C")
        )

        # 2. Замена Windows CRLF на Unix LF
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Удаление артефактов нумерации страниц
        cleaned = cls.PAGE_NUMBER_PATTERN.sub("", cleaned)

        # 4. Удаление псевдографики и мусорных линий-разделителей
        cleaned = cls.ASCII_TABLE_BORDERS.sub("", cleaned)
        cleaned = cls.REPEATED_CHARS.sub(r"\1\1\1", cleaned)

        # 5. Сжатие пробелов внутри строк
        lines = [cls.MULTIPLE_SPACES.sub(" ", line).strip() for line in cleaned.split("\n")]

        # 6. Дедупликация абзацев (сохраняя порядок появления)
        if remove_duplicate_paragraphs:
            seen = set()
            deduped_lines = []
            for line in lines:
                normalized_line = line.lower().strip()
                # Не дедуплицируем короткие строки или пустые строки
                if len(normalized_line) < 25:
                    deduped_lines.append(line)
                    continue

                if normalized_line not in seen:
                    seen.add(normalized_line)
                    deduped_lines.append(line)
            lines = deduped_lines

        # 7. Сборка обратно и сжатие пустых строк
        result = "\n".join(lines)
        result = cls.MULTIPLE_NEWLINES.sub("\n\n", result).strip()

        # 8. Ограничение длины при необходимости
        if max_length and len(result) > max_length:
            result = result[:max_length] + "\n\n[... Текст сокращен для соблюдения контекстного окна ...]"

        return result

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Приблизительная оценка количества токенов.
        Для кириллицы и смешанного русско-казахско-английского текста
        коэффициент обычно ~2.5 - 3.5 символа на токен (Qwen tokenizer).
        """
        if not text:
            return 0
        return max(1, int(len(text) / 3.2))

    @staticmethod
    def split_into_chunks(text: str, max_chunk_tokens: int = 32000, overlap_tokens: int = 1000) -> List[str]:
        """Разбиение сверхдлинного текста на чанки с перекрытием."""
        max_chars = int(max_chunk_tokens * 3.2)
        overlap_chars = int(overlap_tokens * 3.2)

        # Safety: overlap must be less than chunk size
        if overlap_chars >= max_chars:
            overlap_chars = max_chars // 4

        if len(text) <= max_chars:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + max_chars
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Поиск границы предложения для красивого разделения
            split_idx = text.rfind("\n\n", start, end)
            if split_idx == -1 or split_idx <= start:
                split_idx = text.rfind(". ", start, end)
            if split_idx == -1 or split_idx <= start:
                split_idx = end

            chunks.append(text[start:split_idx].strip())
            # Ensure forward progress: new start must be at least start + 1
            new_start = max(start + 1, split_idx - overlap_chars)
            if new_start <= start:
                new_start = start + max_chars // 2  # Force progress
            start = new_start

        return chunks
