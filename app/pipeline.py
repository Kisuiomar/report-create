"""
Main Orchestrator / Workflow Controller for Offline Dossier Pipeline.
Coordinates file ingestion, parsing, cleaning, LLM extraction, and multi-format reporting.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from app.config import settings
from app.core.cleaner import TextCleaner
from app.core.llm_client import LLMClient
from app.core.schemas import DossierReport
from app.exporters import export_docx, export_json, export_pdf, export_xlsx
from app.parsers import ParsedDocument, get_parser_for_file

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Результат выполнения конвейера извлечения досье."""
    dossier: DossierReport
    raw_cleaned_text: str
    parsed_documents: List[ParsedDocument]
    markdown_report: str = ""
    generated_files: Dict[str, Path] = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    stats: Dict[str, Any] = field(default_factory=dict)


class DossierPipeline:
    """
    Главный оркестратор конвейера.
    Принимает файлы, извлекает и чистит текст, отправляет в локальную LLM
    и генерирует отчеты в нужных форматах.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        output_dir: Optional[Path] = None
    ):
        self.llm_client = llm_client or LLMClient()
        self.output_dir = output_dir or settings.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def process_files(
        self,
        file_paths: List[Union[str, Path]],
        export_formats: Optional[List[str]] = None,
        custom_output_name: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Основной цикл обработки одного или нескольких документов:
        1. Парсинг каждого документа через специализированные парсеры (PDF, DOCX, XLSX, HTML, JSON, OCR).
        2. Агрегация и чистка текста (дедупликация, сжатие токенов).
        3. Запрос к локальной LLM с JSON Schema (Structured Output).
        4. Валидация и экспорт отчетов (PDF, DOCX, XLSX, JSON).
        """
        start_time = time.time()
        export_formats = export_formats or ["json", "docx", "xlsx", "pdf"]

        yield {"type": "status", "message": "Запуск пайплайна: парсинг файлов...", "progress": 5}

        # 1. Сбор и парсинг файлов
        paths = [Path(p) for p in file_paths]
        parsed_docs: List[ParsedDocument] = []
        raw_text_chunks: List[str] = []

        logger.info("Starting processing for %d files...", len(paths))
        for p in paths:
            if not p.exists():
                logger.warning("File not found: %s", p)
                continue

            parser = get_parser_for_file(p)
            logger.info("Parsing file '%s' with parser %s", p.name, parser.__class__.__name__)
            try:
                doc = parser.parse(p)
                parsed_docs.append(doc)
                raw_text_chunks.append(f"=== [ДОКУМЕНТ: {doc.file_name} | Тип: {doc.source_type}] ===\n{doc.full_text}")
            except Exception as exc:
                logger.error("Failed to parse %s: %s", p.name, exc, exc_info=True)

        if not parsed_docs:
            raise ValueError("No valid documents were successfully parsed.")

        yield {"type": "status", "message": "Очистка и дедупликация извлеченного текста...", "progress": 25}

        # 2. Очистка и компрессия текста
        combined_text = "\n\n".join(raw_text_chunks)
        logger.info("Total raw extracted text: %d characters", len(combined_text))

        cleaned_text = TextCleaner.clean(combined_text)
        estimated_tokens = TextCleaner.estimate_tokens(cleaned_text)
        logger.info(
            "Text cleaned: %d characters, estimated tokens: %d (reduction: %.1f%%)",
            len(cleaned_text),
            estimated_tokens,
            100.0 * (1.0 - len(cleaned_text) / max(len(combined_text), 1))
        )

        # 3. Передача в локальную LLM (с авто-чанкингом при превышении контекстного окна)
        context_limit = int(settings.LLM_NUM_CTX * 0.85)  # 85% of context window
        logger.info("Invoking local LLM (%s via %s)...", self.llm_client.model, self.llm_client.provider)

        yield {"type": "status", "message": "Структурирование досье через Qwen LLM...", "progress": 40}

        if estimated_tokens > context_limit:
            logger.warning(
                "Document exceeds context window (%d tokens > %d limit). Splitting into chunks...",
                estimated_tokens, context_limit
            )
            chunks = TextCleaner.split_into_chunks(cleaned_text, max_chunk_tokens=context_limit)
            logger.info("Split into %d chunks for sequential processing.", len(chunks))

            prog1 = 40 + int(45 / len(chunks))
            yield {"type": "status", "message": f"Документ большой. Обработка чанка 1 из {len(chunks)}...", "progress": prog1}
            # Process first chunk as primary dossier
            dossier = await self.llm_client.generate_dossier(chunks[0])

            # Merge additional chunks' results into the primary dossier
            for chunk_idx, chunk in enumerate(chunks[1:], 2):
                prog_chunk = 40 + int(45 * chunk_idx / len(chunks))
                yield {"type": "status", "message": f"Обработка чанка {chunk_idx} из {len(chunks)}...", "progress": prog_chunk}
                logger.info("Processing chunk %d/%d...", chunk_idx, len(chunks))
                try:
                    partial = await self.llm_client.generate_dossier(chunk)
                    self._merge_partial_dossier(dossier, partial)
                except Exception as chunk_err:
                    logger.warning("Chunk %d processing failed, skipping: %s", chunk_idx, chunk_err)
        else:
            dossier = await self.llm_client.generate_dossier(cleaned_text)

        # Добавим метаданные конвейера
        dossier.metadata.update({
            "source_files": [d.file_name for d in parsed_docs],
            "total_pages_parsed": sum(d.total_pages for d in parsed_docs),
            "estimated_input_tokens": estimated_tokens,
        })

        yield {"type": "status", "message": "Генерация форензик-отчета по структурированным данным (в фоне)...", "progress": 85}

        # 3.5 Генерация глубокого аналитического отчета (Markdown, 14 разделов)
        logger.info("Generating comprehensive 14-section Forensic Markdown Report...")
        try:
            # Передаем сжатый JSON в Markdown генератор, а не сырой текст!
            dossier_json = dossier.model_dump_json(exclude_none=True)
            markdown_report = ""
            
            async for event in self.llm_client.generate_markdown_report(dossier_json):
                if event["type"] == "status":
                    yield event
                elif event["type"] == "result":
                    markdown_report = event["data"]
                    
            logger.info("Markdown report generated successfully (%d chars).", len(markdown_report))
        except Exception as exc:
            logger.error("Failed to generate Markdown report: %s", exc, exc_info=True)
            markdown_report = f"# Ошибка генерации отчета\n\nLLM не смогла сформировать текст: {exc}"

        yield {"type": "status", "message": "Сборка файлов отчета (Word, Excel, PDF)...", "progress": 95}

        # 4. Формирование базового имени для экспорта
        safe_subject = "".join(c for c in dossier.subject.full_name if c.isalnum() or c in (" ", "_", "-")).strip()
        safe_subject = safe_subject.replace(" ", "_") if safe_subject else "dossier"
        base_name = custom_output_name or f"Dossier_{safe_subject}_{int(time.time())}"

        # 5. Экспорт отчетов
        generated_files: Dict[str, Path] = {}
        for fmt in export_formats:
            fmt_lower = fmt.lower().strip()
            out_file = self.output_dir / f"{base_name}.{fmt_lower}"
            try:
                if fmt_lower == "json":
                    export_json(dossier, out_file)
                    generated_files["json"] = out_file
                elif fmt_lower == "docx":
                    export_docx(markdown_report, out_file)
                    generated_files["docx"] = out_file
                elif fmt_lower == "xlsx":
                    export_xlsx(dossier, out_file)
                    generated_files["xlsx"] = out_file
                elif fmt_lower == "pdf":
                    export_pdf(dossier, out_file)
                    generated_files["pdf"] = out_file
                logger.info("Successfully exported report: %s", out_file)
            except Exception as exp_err:
                logger.error("Failed to export format '%s': %s", fmt_lower, exp_err, exc_info=True)

        elapsed = time.time() - start_time
        stats = {
            "elapsed_seconds": round(elapsed, 2),
            "files_count": len(parsed_docs),
            "characters_extracted": len(combined_text),
            "estimated_tokens": estimated_tokens,
            "relatives_count": len(dossier.relatives_and_affiliates),
            "employments_count": len(dossier.employment_history),
            "addresses_count": len(dossier.addresses),
        }

        logger.info("Pipeline finished in %.2f s. Extracted subject: %s", elapsed, dossier.subject.full_name)

        result_obj = PipelineResult(
            dossier=dossier,
            raw_cleaned_text=cleaned_text,
            parsed_documents=parsed_docs,
            markdown_report=markdown_report,
            generated_files=generated_files,
            execution_time_seconds=elapsed,
            stats=stats
        )

        yield {
            "type": "result",
            "data": {
                "dossier": result_obj.dossier.model_dump(),
                "raw_cleaned_text": result_obj.raw_cleaned_text,
                "markdown_report": result_obj.markdown_report,
                "generated_files": {k: str(v.name) for k, v in result_obj.generated_files.items()},
                "execution_time_seconds": result_obj.execution_time_seconds,
                "stats": result_obj.stats
            }
        }

    @staticmethod
    def _merge_partial_dossier(primary: DossierReport, partial: DossierReport) -> None:
        """
        Мержит данные из частичного досье (от дополнительного чанка) в основное.
        Добавляет новых родственников, адреса, места работы (без дубликатов).
        """
        # Merge relatives (deduplicate by full_name)
        existing_names = {r.full_name.lower().strip() for r in primary.relatives_and_affiliates}
        for rel in partial.relatives_and_affiliates:
            if rel.full_name.lower().strip() not in existing_names:
                primary.relatives_and_affiliates.append(rel)
                existing_names.add(rel.full_name.lower().strip())

        # Merge employment (deduplicate by organization name)
        existing_orgs = {e.organization.lower().strip() for e in primary.employment_history}
        for emp in partial.employment_history:
            if emp.organization.lower().strip() not in existing_orgs:
                primary.employment_history.append(emp)
                existing_orgs.add(emp.organization.lower().strip())

        # Merge addresses (deduplicate by full_address)
        existing_addrs = {a.full_address.lower().strip() for a in primary.addresses}
        for addr in partial.addresses:
            if addr.full_address.lower().strip() not in existing_addrs:
                primary.addresses.append(addr)
                existing_addrs.add(addr.full_address.lower().strip())

        # Merge contacts (deduplicate)
        for phone in partial.contacts.phone_numbers:
            if phone not in primary.contacts.phone_numbers:
                primary.contacts.phone_numbers.append(phone)
        for email in partial.contacts.emails:
            if email not in primary.contacts.emails:
                primary.contacts.emails.append(email)
        for profile in partial.contacts.social_profiles:
            if profile not in primary.contacts.social_profiles:
                primary.contacts.social_profiles.append(profile)
