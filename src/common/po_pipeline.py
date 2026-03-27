"""
Verarbeitungs-Pipeline für Prüfungsordnungen

Pipeline-Schritte:
1. PDF validieren (nur .pdf, max. 50 MB)
2. PDF via Docling in Markdown umwandeln
3. Markdown parsen → Module, ECTS, Prüfungsformen, Dozenten extrahieren
4. PDF auf S3 hochladen
5. Alles in Neo4j speichern (idempotent mit MERGE)
6. Bei Fehler: Transaktion zurückrollen, S3-Upload rückgängig machen
"""

import os
import re
import logging
import tempfile
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import uuid

from docling.document_converter import DocumentConverter, FormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend

from .po_s3 import S3Handler
from .po_repository import PORepository

logger = logging.getLogger(__name__)

# Docling Converter global initialisieren (einmalig)
pipeline_options = PdfPipelineOptions(do_table_structure=True)
pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
pipeline_options.do_ocr = False

docling_converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
    format_options={
        InputFormat.PDF: FormatOption(
            pipeline_cls=StandardPdfPipeline,
            pipeline_options=pipeline_options,
            backend=DoclingParseV4DocumentBackend,
        )
    },
)


class POPipeline:
    """Pipeline zur Verarbeitung von Prüfungsordnungs-PDFs"""

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    ALLOWED_MIME_TYPES = ["application/pdf"]

    def __init__(self, s3_handler: S3Handler, po_repository: PORepository):
        """
        Args:
            s3_handler: S3Handler Instanz
            po_repository: PORepository Instanz
        """
        self.s3 = s3_handler
        self.repo = po_repository

    async def validate_pdf(self, file_content: bytes, filename: str) -> Tuple[bool, str]:
        """
        Validiert PDF-Datei.

        Args:
            file_content: Binärer PDF-Inhalt
            filename: Dateiname

        Returns:
            (is_valid, error_message)
        """
        # Dateigröße prüfen
        if len(file_content) > self.MAX_FILE_SIZE:
            return False, f"Datei zu groß ({len(file_content)} bytes). Max: {self.MAX_FILE_SIZE} bytes"

        # Dateiendung prüfen
        if not filename.lower().endswith(".pdf"):
            return False, "Nur PDF-Dateien erlaubt"

        # PDF-Magic-Bytes prüfen
        if not file_content.startswith(b"%PDF"):
            return False, "Ungültige PDF-Datei (fehlerhafte Magic Bytes)"

        return True, ""

    async def pdf_to_markdown(self, pdf_path: str) -> str:
        """
        Konvertiert PDF zu Markdown via Docling.

        Args:
            pdf_path: Pfad zur PDF-Datei

        Returns:
            Markdown-String

        Raises:
            Exception bei Konvertierungsfehler
        """
        try:
            result = docling_converter.convert(pdf_path)
            docling_doc = result.document
            markdown = docling_doc.export_to_markdown()
            logger.info(f"PDF erfolgreich zu Markdown konvertiert: {pdf_path}")
            return markdown
        except Exception as e:
            logger.error(f"Fehler bei Docling-Konvertierung: {e}")
            raise

    async def extract_modules_from_markdown(self, markdown: str) -> List[Dict]:
        """
        Extrahiert Modul-Informationen aus Markdown.

        Einfache Regex-basierte Extraktion. Kann später durch NLP ersetzt werden.

        Args:
            markdown: Markdown-String

        Returns:
            Liste von Modul-Dictionaries
        """
        modules = []

        # Pattern für Modulnamen (z.B. "## Modul: Einführung in die Programmierung")
        modul_pattern = r"#{1,3}\s*(?:Modul:?\s*)?([A-ZÄÖÜa-zäöüß0-9\s\-]+)"

        # Pattern für ECTS (z.B. "ECTS: 5", "5 CP", "Credits 6 CP", "5 ECTS")
        ects_pattern = r"(?i)(?:ECTS|CP|Credits?(?:[-_]Punkte)?)\s*:?\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:ECTS|CP|Credits?)"

        # Pattern für Semester (z.B. "Semester: 1", "1. Sem.", "1. Semester")
        semester_pattern = r"(?i)(?:Semester|Sem\.)\s*:?\s*(\d+)|(\d+)\.\s*(?:Semester|Sem\.?)"

        # Pattern für Prüfungsform (z.B. "Prüfungsformen Klausur (Bitte...")
        pruefungsform_pattern = r"(?i)(?:Pr[üu]fungsform(?:en)?|Prüfungsart|Modulprüfung)\s*:?\s*([^|]+)|(Kombinationsprüfung|Ausarbeitung|Hausarbeit|Portfolio|Klausur|Mündliche Prüfung|Projekt|Referat|Kolloquium|Praktikum)"

        # Pattern für Kürzel (z.B. "Kürzel: PROG1")
        kuerzel_pattern = r"(?i)K[üu]rzel\s*:?\s*([A-Z0-9\-]+)"

        # Pattern für Professor / Dozent ("Modulbeauftragte*r und hauptamtlich Lehrende Prof. Dr. Heiner Giefers")
        dozent_pattern = r"(?i)(?:Dozent(?:in)?|Prof\.|Professor(?:in)?|Modulverantwortliche[r*]?|Lehrende[r*]?)\s*:?\s*([^|]+)"

        lines = markdown.split("\n")
        current_module = None

        for i, line in enumerate(lines):
            # Neues Modul erkannt
            modul_match = re.search(modul_pattern, line)
            if modul_match and ("Modul" in line or line.startswith("#")):
                modul_name = modul_match.group(1).strip()
                
                # Filtern von falschen Modulen (Unterkapitel oder Dokument-Header)
                is_subchapter = bool(re.match(r"^\d+\s+", modul_name))
                is_blacklisted = any(inv in modul_name.lower() for inv in [
                    "modulhandbuch", "studienverlaufsplan", "inhaltsverzeichnis", 
                    "pflichtmodule", "wahlpflichtmodule", "studiengang", 
                    "bachelor", "master", "lernergebnisse", "inhalte", "container", 
                    "handbuch", "kompetenzen", "funktionen", "Die Ziele des Kurses sind"
                ])
                
                if not is_subchapter and not is_blacklisted and len(modul_name) > 3:
                    if current_module:
                        modules.append(current_module)
    
                    current_module = {
                        "name": modul_name,
                        "kuerzel": "",
                        "semester": "1",
                        "ects": 0.0,
                        "pruefungsform": "N/A",
                        "dozent": None,
                        "pflicht_oder_wahl": "Pflicht",
                    }

            # Wenn wir in einem Modul sind, Details extrahieren
            if current_module:
                # ECTS
                ects_match = re.search(ects_pattern, line)
                if ects_match:
                    val = ects_match.group(1) or ects_match.group(2)
                    if val:
                        current_module["ects"] = float(val.replace(",", "."))

                # Semester
                semester_match = re.search(semester_pattern, line)
                if semester_match:
                    val = semester_match.group(1) or semester_match.group(2)
                    if val:
                        current_module["semester"] = str(val).strip()

                # Prüfungsform
                pruefungsform_match = re.search(pruefungsform_pattern, line)
                if pruefungsform_match:
                    val = pruefungsform_match.group(1) or pruefungsform_match.group(2)
                    if val:
                        val = val.strip()
                        # Unnötige Boilerplate-Texte entfernen, aber wichtige Klammern (wie §-Verweise) behalten
                        val = re.sub(r"(?i)\(Bitte beachten Sie den Prüfungsplan[^)]*\)", "", val).strip()
                        if len(val) > 2:
                            current_module["pruefungsform"] = val

                # Kürzel
                kuerzel_match = re.search(kuerzel_pattern, line)
                if kuerzel_match:
                    current_module["kuerzel"] = kuerzel_match.group(1).strip()
                
                # Dozent
                dozent_match = re.search(dozent_pattern, line)
                if dozent_match:
                    val = dozent_match.group(1).strip()
                    # Wenn der Name mehr als 2 Zeichen hat, übernehmen
                    if len(val) > 2:
                        current_module["dozent"] = val

        # Letztes Modul hinzufügen
        if current_module:
            modules.append(current_module)

        logger.info(f"{len(modules)} Module aus Markdown extrahiert")
        return modules

    async def process_pdf(
        self,
        file_content: bytes,
        filename: str,
        studiengang: str,
        version: str,
        gueltig_ab: str,
    ) -> Dict:
        """
        Vollständige Pipeline-Verarbeitung.

        Args:
            file_content: Binärer PDF-Inhalt
            filename: Dateiname
            studiengang: Studiengangsname
            version: Version (z.B. WS2024)
            gueltig_ab: Gültigkeitsdatum (ISO-Format)

        Returns:
            Dictionary mit PO-ID und Status

        Raises:
            Exception bei Verarbeitungsfehler
        """
        po_id = str(uuid.uuid4())
        s3_key = None
        temp_pdf_path = None

        try:
            # 1. PDF validieren
            is_valid, error_msg = await self.validate_pdf(file_content, filename)
            if not is_valid:
                raise ValueError(error_msg)

            # 2. PO in Neo4j erstellen (Status: processing)
            await self.repo.create_pruefungsordnung(
                po_id=po_id,
                studiengang=studiengang,
                version=version,
                gueltig_ab=gueltig_ab,
                s3_key="",  # Wird später aktualisiert
                status="processing",
            )

            # 3. PDF temporär speichern für Docling
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file_content)
                temp_pdf_path = temp_file.name

            # 4. PDF zu Markdown konvertieren
            markdown = await self.pdf_to_markdown(temp_pdf_path)

            # 5. Module aus Markdown extrahieren
            modules = await self.extract_modules_from_markdown(markdown)

            # 6. PDF auf S3 hochladen
            s3_key = await self.s3.upload_pdf(file_content, studiengang, version, po_id)

            # 7. S3-Key in Neo4j aktualisieren
            await self.repo.create_pruefungsordnung(
                po_id=po_id,
                studiengang=studiengang,
                version=version,
                gueltig_ab=gueltig_ab,
                s3_key=s3_key,
                status="processing",
            )

            # 8. Module in Neo4j speichern
            for idx, modul in enumerate(modules):
                modul_id = f"{po_id}-modul-{idx}"

                # Modul erstellen
                await self.repo.create_modul(
                    po_id=po_id,
                    modul_id=modul_id,
                    name=modul["name"],
                    kuerzel=modul.get("kuerzel", ""),
                    semester=modul.get("semester", "1"),
                    pflicht_oder_wahl=modul.get("pflicht_oder_wahl", "Pflicht"),
                )

                # ECTS hinzufügen
                if modul.get("ects", 0) > 0:
                    await self.repo.create_ects(
                        modul_id=modul_id,
                        punkte=modul["ects"],
                        workload_h=int(modul["ects"] * 30),  # Schätzung: 30h pro ECTS
                    )

                # Prüfungsform hinzufügen
                if modul.get("pruefungsform"):
                    await self.repo.create_pruefungsform(
                        modul_id=modul_id, typ=modul["pruefungsform"]
                    )

                # Dozent hinzufügen (falls vorhanden)
                if modul.get("dozent"):
                    await self.repo.create_dozent(name=modul["dozent"])
                    await self.repo.link_modul_to_dozent(modul_id, modul["dozent"])

            # 9. Status auf "ready" setzen
            await self.repo.update_po_status(po_id, "ready")

            logger.info(f"PO erfolgreich verarbeitet: {po_id}")
            return {
                "id": po_id,
                "status": "ready",
                "studiengang": studiengang,
                "version": version,
                "modules_count": len(modules),
            }

        except Exception as e:
            logger.error(f"Fehler bei Pipeline-Verarbeitung: {e}")

            # Rollback: Status auf "error" setzen
            if po_id:
                try:
                    await self.repo.update_po_status(po_id, "error")
                except Exception as rollback_error:
                    logger.error(f"Fehler beim Rollback: {rollback_error}")

            # Rollback: S3-Upload rückgängig machen
            if s3_key:
                try:
                    await self.s3.delete_pdf(s3_key)
                except Exception as s3_error:
                    logger.error(f"Fehler beim S3-Rollback: {s3_error}")

            raise

        finally:
            # Temporäre Datei löschen
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
