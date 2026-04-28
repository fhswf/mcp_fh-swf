"""
Prüfungsordnungs-Verwaltung API

FastAPI App mit allen Endpoints für PO-Management.
po_app wird in main.py unter /api/v1 gemountet.
ui_app wird in main.py unter /ui gemountet.
"""

import logging
from typing import List, Optional
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


# ==================== Pydantic Schemas ====================

class POUploadRequest(BaseModel):
    """Request-Schema für PO-Upload"""
    studiengang: str = Field(..., description="Name des Studiengangs")
    version: str = Field(..., description="Version (z.B. WS2024)")
    gueltig_ab: date = Field(..., description="Gültigkeitsdatum")


class ModuleOut(BaseModel):
    """Response-Schema für Module"""
    name: str
    kuerzel: str
    semester: str
    ects: float
    pruefungsform: str
    dozent: Optional[str] = None


class PODetail(BaseModel):
    """Response-Schema für PO-Details"""
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
    """Response-Schema für PO-Liste"""
    id: str
    studiengang: str
    version: str
    gueltig_ab: date
    status: str
    created_at: datetime


class POUpdateRequest(BaseModel):
    """Request-Schema für PO-Metadaten-Update"""
    studiengang: Optional[str] = None
    version: Optional[str] = None


class HealthResponse(BaseModel):
    """Response-Schema für Health Check"""
    status: str
    timestamp: datetime


# ==================== Endpoints ====================

@po_app.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
    }


@po_app.post("/po", response_model=PODetail, status_code=201)
async def upload_po(
    file: UploadFile = File(..., description="PDF-Datei des Modulhandbuchs"),
    studiengang: str = Form(..., description="Name des Studiengangs"),
    version: str = Form(..., description="Version (z.B. WS2024)"),
    gueltig_ab: date = Form(..., description="Gültigkeitsdatum (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """Modulhandbuch hochladen und verarbeiten."""
    try:
        file_content = await file.read()
        result = await pipeline.process_pdf(
            file_content=file_content,
            filename=file.filename,
            studiengang=studiengang,
            version=version,
            gueltig_ab=gueltig_ab.isoformat(),
        )
        po_detail = await po_repository.get_po_by_id(result["id"])
        if not po_detail:
            raise HTTPException(status_code=500, detail="PO konnte nicht abgerufen werden")
        return po_detail
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Fehler beim PO-Upload: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.get("/po", response_model=List[POListItem])
async def list_pos(
    current_user: dict = Depends(get_current_user),
):
    """Alle Prüfungsordnungen auflisten."""
    try:
        return await po_repository.get_all_pos()
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der POs: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.get("/po/{po_id}", response_model=PODetail)
async def get_po_detail(
    po_id: str,
    current_user: dict = Depends(get_current_user),
):
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
async def delete_po(
    po_id: str,
    current_user: dict = Depends(get_current_user),
):
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
