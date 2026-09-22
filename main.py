"""
Offline Dossier & Entity Extraction Pipeline.
Main entry point supporting both Typer CLI and FastAPI Web Server.
"""

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

# Reconfigure Windows console to UTF-8 to prevent cp1251 encoding errors with emojis and symbols
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import typer
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.llm_client import LLMClient
from app.pipeline import DossierPipeline

from rich.logging import RichHandler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)]
)
logger = logging.getLogger("offline_dossier")

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="100% Offline Air-Gapped Entity & Kinship Extraction Engine"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
static_dir = Path(__file__).resolve().parent / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serves the main Octopus Web UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Offline Dossier Pipeline API running. Static UI not found."}


# Cached LLM client singleton for health checks (avoids creating new instance per request)
_health_llm_client: Optional[LLMClient] = None


def _get_health_client() -> LLMClient:
    global _health_llm_client
    if _health_llm_client is None:
        _health_llm_client = LLMClient()
    return _health_llm_client


@app.get("/api/health")
async def health_check():
    """Healthcheck endpoint reporting local LLM status and environment."""
    client = _get_health_client()
    llm_status = client.check_health()
    return {
        "status": "online",
        "version": settings.VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "llm_base_url": settings.LLM_BASE_URL,
        "llm_status": llm_status,
        "upload_dir": str(settings.UPLOAD_DIR),
        "output_dir": str(settings.OUTPUT_DIR)
    }


@app.post("/api/process")
async def process_documents(files: List[UploadFile] = File(...)):
    """Uploads documents and executes the end-to-end dossier extraction pipeline."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    import json
    
    async def event_generator():
        saved_paths = []
        try:
            # Save uploaded files to temporary storage
            for file in files:
                safe_name = Path(file.filename).name
                target_path = settings.UPLOAD_DIR / safe_name
                with open(target_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                saved_paths.append(target_path)

            # Run pipeline
            pipeline = DossierPipeline()
            async for event in pipeline.process_files(saved_paths):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("Processing failed: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            # Close file handles
            for f in files:
                await f.close()
            
            # Clean up uploaded files (cache)
            for path in saved_paths:
                try:
                    if path.exists():
                        path.unlink()
                        logger.info("Deleted cached file: %s", path.name)
                except Exception as cleanup_err:
                    logger.error("Failed to delete cached file %s: %s", path.name, cleanup_err)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Downloads an exported report file (PDF, DOCX, XLSX, JSON)."""
    safe_name = Path(filename).name
    file_path = settings.OUTPUT_DIR / safe_name

    # Prevent path traversal attacks
    if not file_path.resolve().is_relative_to(settings.OUTPUT_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found")

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type="application/octet-stream"
    )


# ---------------------------------------------------------------------------
# CLI Commands using Typer
# ---------------------------------------------------------------------------
cli = typer.Typer(
    name="dossier",
    help="100% Offline Dossier & Entity Extraction Pipeline CLI",
    add_completion=False
)


@cli.command("serve")
def run_server(
    host: str = typer.Option(settings.SERVER_HOST, "--host", "-h", help="Bind host"),
    port: int = typer.Option(settings.SERVER_PORT, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload on code change")
):
    """Start the FastAPI Web Server and Octopus UI."""
    typer.echo(f"Starting Dossier Pipeline Web Server on http://{host}:{port} ...")
    uvicorn.run("main:app", host=host, port=port, reload=reload)


@cli.command("extract")
def run_extraction(
    files: List[Path] = typer.Argument(..., help="Path(s) to document files to process"),
    export: str = typer.Option("pdf,docx,xlsx,json", "--export", "-e", help="Comma-separated export formats"),
    output_dir: Optional[Path] = typer.Option(None, "--out", "-o", help="Custom output directory"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override LLM model name")
):
    """Process documents through the extraction pipeline and export reports."""
    formats = [f.strip().lower() for f in export.split(",") if f.strip()]
    target_out = output_dir or settings.OUTPUT_DIR

    llm = LLMClient(model=model) if model else None
    pipeline = DossierPipeline(llm_client=llm, output_dir=target_out)

    typer.echo(f"Processing {len(files)} files...")
    for f in files:
        typer.echo(f"  - {f}")

    try:
        result = pipeline.process_files(files, export_formats=formats)
        typer.secho("\n--- EXTRACTION COMPLETED SUCCESSFULLY ---", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"Subject: {result.dossier.subject.full_name}")
        typer.echo(f"IIN: {result.dossier.subject.iin or 'N/A'}")
        typer.echo(f"Relatives & Affiliates found: {len(result.dossier.relatives_and_affiliates)}")
        typer.echo(f"Employment history records: {len(result.dossier.employment_history)}")
        typer.echo(f"Time taken: {result.execution_time_seconds:.2f} s")
        
        typer.secho("\nGenerated Reports:", fg=typer.colors.CYAN, bold=True)
        for fmt, path in result.generated_files.items():
            typer.echo(f"  [{fmt.upper()}] -> {path}")

    except Exception as exc:
        typer.secho(f"\nError: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@cli.command("check-llm")
def test_llm_connection():
    """Verify local LLM connectivity (Ollama / vLLM)."""
    client = LLMClient()
    typer.echo(f"Checking connection to {client.provider} at {client.base_url} ...")
    status = client.check_health()
    if status.get("status") == "ok":
        typer.secho("✓ Local LLM server is ONLINE and responsive!", fg=typer.colors.GREEN, bold=True)
        models = status.get("models", [])
        typer.echo(f"Available models ({len(models)}): {', '.join(models[:10])}")
    else:
        typer.secho(f"✗ Could not reach LLM server: {status.get('message')}", fg=typer.colors.RED)
        typer.echo("Ensure Ollama (`ollama serve`) or vLLM is running locally.")


if __name__ == "__main__":
    cli()
