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

        # 3. Индексация в Qdrant (Full RAG Pipeline - Опция Б)
        import uuid
        session_id = str(uuid.uuid4())
        
        yield {"type": "status", "message": "Индексация всего документа в Qdrant...", "progress": 30}
        from app.core.vector_store import VectorKnowledgeBase
        vkb = VectorKnowledgeBase()
        
        file_names = ", ".join([d.file_name for d in parsed_docs])
        await vkb.index_document(cleaned_text, source_name=file_names, session_id=session_id)
        
        # 4. Пошаговый RAG конвейер
        yield {"type": "status", "message": "RAG Шаг 1: Идентификация главного субъекта...", "progress": 40}
        
        q_subject = await vkb.search("Главный субъект документа, ФИО, ИИН, ИНН, дата рождения, паспорт, кто этот человек?", limit=5, session_id=session_id)
        prompt_1 = f"Извлеки базовые данные о главном лице документа из этих фрагментов. Игнорируй остальных людей пока.\n\nФрагменты:\n{q_subject}"
        dossier_step1 = await self.llm_client.generate_dossier(prompt_1)
        
        subject_name = dossier_step1.subject.full_name or "Неизвестный субъект"
        
        yield {"type": "status", "message": f"RAG Шаг 2: Поиск связей и родственников ({subject_name})...", "progress": 55}
        q_relatives = await vkb.search(f"Родственники, мать, отец, супруг, жена, муж, дети, братья, сестры, учредители, компании связанные с {subject_name}", limit=10, session_id=session_id)
        prompt_2 = (
            f"Текущее базовое досье:\n{dossier_step1.model_dump_json(exclude_unset=True)}\n\n"
            f"Внимательно изучи фрагменты ниже. Найди всех родственников и бизнес-связи для {subject_name} и добавь их в досье.\n\n"
            f"Фрагменты:\n{q_relatives}"
        )
        dossier_step2 = await self.llm_client.generate_dossier(prompt_2)
        
        yield {"type": "status", "message": "RAG Шаг 3: Поиск адресов и места работы...", "progress": 70}
        q_addr = await vkb.search(f"Место работы, должность, компания, увольнение, адрес проживания, прописка, недвижимость {subject_name}", limit=10, session_id=session_id)
        prompt_3 = (
            f"Текущее досье:\n{dossier_step2.model_dump_json(exclude_unset=True)}\n\n"
            f"Внимательно изучи фрагменты ниже. Найди историю работы (должности) и адреса для {subject_name} и добавь их в досье.\n\n"
            f"Фрагменты:\n{q_addr}"
        )
        dossier = await self.llm_client.generate_dossier(prompt_3)

        # Добавим метаданные конвейера
        dossier.metadata.update({
            "source_files": [d.file_name for d in parsed_docs],
            "total_pages_parsed": sum(d.total_pages for d in parsed_docs),
            "estimated_input_tokens": estimated_tokens,
        })

        # 3.5 Генерация детального Markdown отчета через LLM
        logger.info("Generating detailed Markdown Report via LLM...")
        dossier_json = dossier.model_dump_json(indent=2)
        markdown_report = ""
        
        async for chunk in self.llm_client.generate_markdown_report(dossier_json, cleaned_text):
            if chunk["type"] == "status":
                yield chunk
            elif chunk["type"] == "result":
                markdown_report = chunk["data"]


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

    @staticmethod
    def _generate_static_markdown(dossier: DossierReport) -> str:
        """
        Быстро генерирует Markdown из структурированного JSON, чтобы не тратить время на LLM генерацию.
        """
        md = []
        md.append(f"# Аналитический отчет: {dossier.subject.full_name}")
        md.append(f"ИИН/ИНН: {dossier.subject.iin or '-'}")
        md.append("\n")

        # 1. Резюме
        md.append("## 1. Резюме (Executive Summary)")
        md.append(f"{dossier.executive_summary}\n")
        
        # 2. Анкетные данные
        md.append("## 2. Анкетные данные субъекта")
        md.append("| Параметр | Значение |")
        md.append("| -------- | -------- |")
        md.append(f"| ФИО | **{dossier.subject.full_name}** |")
        md.append(f"| ИИН/ИНН | {dossier.subject.iin or '-'} |")
        md.append(f"| Дата рождения | {dossier.subject.birth_date or '-'} |")
        md.append(f"| Место рождения | {dossier.subject.birth_place or '-'} |")
        md.append(f"| Гражданство | {dossier.subject.citizenship or '-'} |")
        md.append(f"| Пол | {dossier.subject.gender or '-'} |")
        md.append("\n")
        
        # 3. Контакты
        md.append("## 3. Контакты и адреса")
        if dossier.contacts.phone_numbers:
            md.append(f"**Телефоны:** {', '.join(dossier.contacts.phone_numbers)}")
        if dossier.contacts.emails:
            md.append(f"**Email:** {', '.join(dossier.contacts.emails)}")
        if dossier.contacts.social_profiles:
            md.append(f"**Соц. сети:** {', '.join(dossier.contacts.social_profiles)}")
            
        if dossier.addresses:
            md.append("\n**Адреса:**")
            md.append("| Тип | Адрес | Город | Регион |")
            md.append("| --- | --- | --- | --- |")
            for a in dossier.addresses:
                md.append(f"| {a.address_type} | {a.full_address} | {a.city or '-'} | {a.region or '-'} |")
        md.append("\n")

        # 4. Трудоустройство
        md.append("## 4. Места работы")
        if dossier.employment_history:
            md.append("| Организация | Должность | Период | БИН | Примечания |")
            md.append("| --- | --- | --- | --- | --- |")
            for e in dossier.employment_history:
                md.append(f"| **{e.organization}** | {e.position or '-'} | {e.period or '-'} | {e.bin or '-'} | {e.notes or '-'} |")
        else:
            md.append("Нет данных о трудоустройстве.")
        md.append("\n")

        # 5. Родственники
        md.append("## 5. Родственные и аффилированные связи")
        if dossier.relatives_and_affiliates:
            md.append("| ФИО | Тип связи | ИИН | Дата рождения | Общие признаки | Примечания |")
            md.append("| --- | --- | --- | --- | --- | --- |")
            for r in dossier.relatives_and_affiliates:
                shared = ', '.join(r.shared_attributes) if r.shared_attributes else '-'
                md.append(f"| **{r.full_name}** | {r.relation_type} | {r.iin or '-'} | {r.birth_date or '-'} | {shared} | {r.notes or '-'} |")
        else:
            md.append("Нет данных о связях.")
            
        # 6. Дополнительные аналитические разделы
        if hasattr(dossier, 'analytical_sections') and dossier.analytical_sections:
            for i, section in enumerate(dossier.analytical_sections, start=6):
                md.append(f"\n## {i}. {section.title}")
                md.append(f"{section.content}\n")
            
        return "\n".join(md)

