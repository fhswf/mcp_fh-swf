"""
Prüfungsordnungs-Verwaltung API

FastAPI App mit allen Endpoints für PO-Management.
Wird als Sub-App in main.py unter /po gemountet.
"""

import logging
from typing import List, Optional
from datetime import date, datetime

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form
from pydantic import BaseModel, Field

from src.common.po_auth import get_current_user
from src.common.po_s3 import S3Handler
from src.common.po_repository import PORepository
from src.common.po_pipeline import POPipeline
from src import neo_handler

logger = logging.getLogger(__name__)

# FastAPI Sub-App
po_app = FastAPI(
    title="Prüfungsordnungs-Verwaltung API",
    version="1.0.0",
    description="API zur Verwaltung von Prüfungsordnungen der FH-SWF",
)

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
    semester: int
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

@po_app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """
    Health Check Endpoint.

    Returns:
        Status und Timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
    }


@po_app.post("/api/v1/upload", response_model=PODetail, status_code=201)
async def upload_po(
    file: UploadFile = File(..., description="PDF-Datei der Prüfungsordnung"),
    studiengang: str = Form(..., description="Name des Studiengangs"),
    version: str = Form(..., description="Version (z.B. WS2024)"),
    gueltig_ab: date = Form(..., description="Gültigkeitsdatum (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """
    PDF hochladen und verarbeiten.

    Pipeline:
    1. PDF validieren
    2. Via Docling zu Markdown konvertieren
    3. Module extrahieren
    4. PDF auf S3 hochladen
    5. In Neo4j speichern
    """
    try:
        # Datei einlesen
        file_content = await file.read()

        # Pipeline ausführen
        result = await pipeline.process_pdf(
            file_content=file_content,
            filename=file.filename,
            studiengang=studiengang,
            version=version,
            gueltig_ab=gueltig_ab.isoformat(),
        )

        # PO-Details abrufen
        po_detail = await po_repository.get_po_by_id(result["id"])
        if not po_detail:
            raise HTTPException(status_code=500, detail="PO konnte nicht abgerufen werden")

        return po_detail

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Fehler beim PO-Upload: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.get("/api/v1/", response_model=List[POListItem])
async def list_pos(
    current_user: dict = Depends(get_current_user),
):
    """
    Alle Prüfungsordnungen auflisten.

    Returns:
        Liste von POs mit Basisdaten
    """
    try:
        pos = await po_repository.get_all_pos()
        return pos
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der POs: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.get("/api/v1/{po_id}", response_model=PODetail)
async def get_po_detail(
    po_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    PO Details + extrahierte Module abrufen.

    Args:
        po_id: PO-ID

    Returns:
        PO mit allen Modulen
    """
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


@po_app.get("/api/v1/{po_id}/modules", response_model=List[ModuleOut])
async def get_po_modules(
    po_id: str,
    semester: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Alle Module einer PO abrufen.

    Args:
        po_id: PO-ID
        semester: Semester-Filter (optional)

    Returns:
        Liste von Modulen
    """
    try:
        modules = await po_repository.get_modules_by_po(po_id, semester)
        return modules
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Module für PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.put("/api/v1/{po_id}", response_model=PODetail)
async def update_po_metadata(
    po_id: str,
    update_data: POUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Metadaten einer PO aktualisieren.

    Args:
        po_id: PO-ID
        update_data: Neue Metadaten

    Returns:
        Aktualisierte PO
    """
    try:
        success = await po_repository.update_po_metadata(
            po_id=po_id,
            studiengang=update_data.studiengang,
            version=update_data.version,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Prüfungsordnung nicht gefunden")

        # Aktualisierte PO abrufen
        po = await po_repository.get_po_by_id(po_id)
        return po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Update der PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@po_app.delete("/api/v1/{po_id}", status_code=204)
async def delete_po(
    po_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    PO + S3-Datei + Neo4j-Graph löschen.

    Args:
        po_id: PO-ID
    """
    try:
        # PO abrufen für S3-Key
        po = await po_repository.get_po_by_id(po_id)
        if not po:
            raise HTTPException(status_code=404, detail="Prüfungsordnung nicht gefunden")

        # S3-Datei löschen
        if po.get("s3_key"):
            await s3_handler.delete_pdf(po["s3_key"])

        # Neo4j-Daten löschen
        await po_repository.delete_po(po_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Löschen der PO {po_id}: {e}")
        raise HTTPException(status_code=500, detail="Interner Serverfehler")
