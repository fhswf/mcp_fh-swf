"""
Prüfungsordnungs-Verwaltung API

FastAPI App mit allen Endpoints für PO-Management.
po_app wird in main.py unter /api/v1 gemountet.
ui_app wird in main.py unter /ui gemountet.
"""

import asyncio
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.common.po_auth import get_current_user
from src.common.po_s3 import S3Handler
from src.common.po_repository import PORepository
from src.common.po_pipeline import POPipeline
from src import neo_handler

logger = logging.getLogger(__name__)

# API Sub-App
po_app = FastAPI(
    title="Prüfungsordnungs-Verwaltung API",
    version="1.0.0",
    description="API zur Verwaltung von Prüfungsordnungen der FH-SWF",
)

po_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UI Sub-App (Frontend)
ui_app = FastAPI()
ui_app.mount("/static", StaticFiles(directory="static"), name="static")

@ui_app.get("/")
async def root():
    return FileResponse("static/po_verwaltung.html")

# Handler initialisieren
s3_handler = S3Handler()
po_repository = PORepository(neo_handler.driver)
pipeline = POPipeline(s3_handler, po_repository)

# In-Memory Job-Store
jobs: Dict[str, Any] = {}


# ==================== Pydantic Schemas ====================

class ModuleOut(BaseModel):
    name: str
    kuerzel: str
    semester: str
    ects: float
    pruefungsform: str
    dozent: Optional[str] = None


class PODetail(BaseModel):
    id: str
    studiengang: str
    version: str
    gueltig_ab: date
    status: str = Field(..., description="processing | ready | error")
    s3_key: str
    module: List[ModuleOut] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class POListItem(BaseModel):
    id: str
    studiengang: str
    version: str
    gueltig_ab: date
    status: str
    created_at: datetime
    module_count: int = 0


class POUpdateRequest(BaseModel):
    studiengang: Optional[str] = None
    version: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class JobStep(BaseModel):
    name: str
    status: str  # pending | processing | done | error


class JobStatus(BaseModel):
    id: str
    status: str  # pending | processing | ready | error
    steps: List[JobStep]
    po_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


class JobCreated(BaseModel):
    job_id: str


# ==================== Job-Hilfsfunktionen ====================

def make_job(job_id: str) -> Dict:
    return {
        "id": job_id,
        "status": "pending",
        "steps": [
            {"name": "PDF validieren",     "status": "pending"},
            {"name": "PDF konvertieren",   "status": "pending"},
            {"name": "Module extrahieren", "status": "pending"},
            {"name": "S3 Upload",          "status": "pending"},
            {"name": "Neo4j speichern",    "status": "pending"},
        ],
        "po_id": None,
        "error": None,
        "created_at": datetime.utcnow(),
        # Payload für Retry gespeichert
        "_file_content": None,
        "_filename": None,
        "_studiengang": None,
        "_version": None,
        "_gueltig_ab": None,
    }


def set_step(job: Dict, index: int, status: str):
    job["steps"][index]["status"] = status


async def run_pipeline(job_id: str):
    job = jobs[job_id]
    job["status"] = "processing"

    file_content = job["_file_content"]
    filename     = job["_filename"]
    studiengang  = job["_studiengang"]
    version      = job["_version"]
    gueltig_ab   = job["_gueltig_ab"]

    try:
        # Schritt 0: PDF validieren
        set_step(job, 0, "processing")
        is_valid, error_msg = await pipeline.validate_pdf(file_content, filename)
        if not is_valid:
            set_step(job, 0, "error")
            job["status"] = "error"
            job["error"] = error_msg
            return
        set_step(job, 0, "done")

        # Schritt 1: PDF konvertieren
        set_step(job, 1, "processing")
        import tempfile, os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        try:
            markdown = await pipeline.pdf_to_markdown(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        set_step(job, 1, "done")

        # Schritt 2: Module extrahieren
        set_step(job, 2, "processing")
        modules = await pipeline.extract_modules_from_markdown(markdown)
        set_step(job, 2, "done")

        # PO in Neo4j anlegen
        po_id = str(uuid.uuid4())
        await po_repository.create_pruefungsordnung(
            po_id=po_id,
            studiengang=studiengang,
            version=version,
            gueltig_ab=gueltig_ab,
            s3_key="",
            status="processing",
        )

        # Schritt 3: S3 Upload
        set_step(job, 3, "processing")
        s3_key = await s3_handler.upload_pdf(file_content, studiengang, version, po_id)
        await po_repository.create_pruefungsordnung(
            po_id=po_id,
            studiengang=studiengang,
            version=version,
            gueltig_ab=gueltig_ab,
            s3_key=s3_key,
            status="processing",
        )
        set_step(job, 3, "done")

        # Schritt 4: Neo4j speichern
        set_step(job, 4, "processing")
        for idx, modul in enumerate(modules):
            modul_id = f"{po_id}-modul-{idx}"
            await po_repository.create_modul(
                po_id=po_id,
                modul_id=modul_id,
                name=modul["name"],
                kuerzel=modul.get("kuerzel", ""),
                semester=modul.get("semester", "1"),
                pflicht_oder_wahl=modul.get("pflicht_oder_wahl", "Pflicht"),
            )
            if modul.get("ects", 0) > 0:
                await po_repository.create_ects(
                    modul_id=modul_id,
                    punkte=modul["ects"],
                    workload_h=int(modul["ects"] * 30),
                )
            if modul.get("pruefungsform"):
                await po_repository.create_pruefungsform(
                    modul_id=modul_id, typ=modul["pruefungsform"]
                )
            if modul.get("dozent"):
                await po_repository.create_dozent(name=modul["dozent"])
                await po_repository.link_modul_to_dozent(modul_id, modul["dozent"])

        await po_repository.update_po_status(po_id, "ready")
        set_step(job, 4, "done")

        job["po_id"] = po_id
        job["status"] = "ready"
        logger.info(f"Job {job_id} abgeschlossen: PO {po_id}")

    except Exception as e:
        logger.error(f"Fehler in Job {job_id}: {e}")
        # Aktuell laufenden Schritt auf error setzen
        for step in job["steps"]:
            if step["status"] == "processing":
                step["status"] = "error"
        job["status"] = "error"
        job["error"] = str(e)


# ==================== Endpoints ====================

@po_app.get("/health", response_model=HealthResponse)
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@po_app.post("/job", response_model=JobCreated, status_code=202)
async def create_job(
    file: UploadFile = File(..., description="PDF-Datei des Modulhandbuchs"),
    studiengang: str = Form(...),
    version: str = Form(...),
    gueltig_ab: date = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Modulhandbuch hochladen – startet asynchrone Verarbeitung und gibt Job-ID zurück."""
    file_content = await file.read()
    job_id = str(uuid.uuid4())
    job = make_job(job_id)
    job["_file_content"] = file_content
    job["_filename"]     = file.filename
    job["_studiengang"]  = studiengang
    job["_version"]      = version
    job["_gueltig_ab"]   = gueltig_ab.isoformat()
    jobs[job_id] = job

    asyncio.create_task(run_pipeline(job_id))
    return {"job_id": job_id}


@po_app.get("/job/{job_id}/status", response_model=JobStatus)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Status eines Verarbeitungs-Jobs abrufen."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return {
        "id":         job["id"],
        "status":     job["status"],
        "steps":      job["steps"],
        "po_id":      job["po_id"],
        "error":      job["error"],
        "created_at": job["created_at"],
    }


@po_app.put("/job/{job_id}", response_model=JobCreated, status_code=202)
async def retry_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fehlgeschlagenen Job neu starten."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["status"] != "error":
        raise HTTPException(status_code=400, detail="Nur fehlgeschlagene Jobs können neu gestartet werden")

    # Schritte zurücksetzen
    for step in job["steps"]:
        step["status"] = "pending"
    job["status"] = "pending"
    job["error"] = None
    job["po_id"] = None

    asyncio.create_task(run_pipeline(job_id))
    return {"job_id": job_id}


@po_app.get("/po", response_model=List[POListItem])
async def list_pos(current_user: dict = Depends(get_current_user)):
    """Alle Prüfungsordnungen auflisten."""
    try:
        return await po_repository.get_all_pos()
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der POs: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.get("/po/{po_id}", response_model=PODetail)
async def get_po_detail(po_id: str, current_user: dict = Depends(get_current_user)):
    """PO Details + extrahierte Module abrufen."""
    try:
        po = await po_repository.get_po_by_id(po_id)
        if not po:
            raise HTTPException(status_code=404, detail="Prüfungsordnung nicht gefunden")
        return po
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.get("/modules", response_model=List[ModuleOut])
async def get_modules(
    po_id: str,
    semester: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Alle Module einer PO abrufen, optional nach Semester gefiltert."""
    try:
        return await po_repository.get_modules_by_po(po_id, semester)
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Module für PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.put("/po/{po_id}", response_model=PODetail)
async def update_po_metadata(
    po_id: str,
    update_data: POUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Metadaten einer PO aktualisieren."""
    try:
        success = await po_repository.update_po_metadata(
            po_id=po_id,
            studiengang=update_data.studiengang,
            version=update_data.version,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Prüfungsordnung nicht gefunden")
        return await po_repository.get_po_by_id(po_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Update der PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.delete("/po/{po_id}", status_code=204)
async def delete_po(po_id: str, current_user: dict = Depends(get_current_user)):
    """PO + S3-Datei + Neo4j-Graph löschen."""
    try:
        po = await po_repository.get_po_by_id(po_id)
        if not po:
            raise HTTPException(status_code=404, detail="Prüfungsordnung nicht gefunden")
        if po.get("s3_key"):
            await s3_handler.delete_pdf(po["s3_key"])
        await po_repository.delete_po(po_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Löschen der PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")
