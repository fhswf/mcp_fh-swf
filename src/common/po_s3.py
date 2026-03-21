"""
S3-Client für Prüfungsordnungs-PDFs auf s3.ki.fh-swf.de

Funktionen:
- PDF hochladen
- PDF herunterladen
- PDF löschen
- Presigned URLs generieren (1 Stunde gültig)
"""

import os
import logging
from typing import Optional
from datetime import timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Handler:
    """Handler für S3-Operationen auf s3.ki.fh-swf.de"""

    def __init__(self):
        """
        Initialisiert den S3-Client mit Credentials aus Umgebungsvariablen.
        """
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL")
        self.access_key = os.getenv("S3_ACCESS_KEY")
        self.secret_key = os.getenv("S3_SECRET_KEY")
        self.bucket = os.getenv("S3_BUCKET", "pruefungsordnungen")

        if not all([self.endpoint_url, self.access_key, self.secret_key]):
            raise ValueError(
                "S3-Konfiguration fehlt! "
                "Benötigt: S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY"
            )

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def generate_key(self, studiengang: str, version: str, uuid: str) -> str:
        """
        Generiert den S3-Key nach dem Schema: po/{studiengang}/{version}/{uuid}.pdf

        Args:
            studiengang: Name des Studiengangs
            version: Version (z.B. WS2024)
            uuid: Eindeutige ID

        Returns:
            Formatierter S3-Key
        """
        # Sonderzeichen und Leerzeichen entfernen
        studiengang_clean = studiengang.replace(" ", "_").replace("/", "-")
        version_clean = version.replace(" ", "_").replace("/", "-")
        return f"po/{studiengang_clean}/{version_clean}/{uuid}.pdf"

    async def upload_pdf(
        self, file_content: bytes, studiengang: str, version: str, uuid: str
    ) -> str:
        """
        Lädt PDF auf S3 hoch.

        Args:
            file_content: Binärer PDF-Inhalt
            studiengang: Name des Studiengangs
            version: Version (z.B. WS2024)
            uuid: Eindeutige ID

        Returns:
            S3-Key des hochgeladenen Files

        Raises:
            ClientError: Bei S3-Fehler
        """
        s3_key = self.generate_key(studiengang, version, uuid)

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=file_content,
                ContentType="application/pdf",
            )
            logger.info(f"PDF erfolgreich hochgeladen: {s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"Fehler beim Upload: {e}")
            raise

    async def download_pdf(self, s3_key: str) -> bytes:
        """
        Lädt PDF von S3 herunter.

        Args:
            s3_key: S3-Key der Datei

        Returns:
            Binärer PDF-Inhalt

        Raises:
            ClientError: Bei S3-Fehler oder wenn Datei nicht existiert
        """
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=s3_key)
            content = response["Body"].read()
            logger.info(f"PDF erfolgreich heruntergeladen: {s3_key}")
            return content

        except ClientError as e:
            logger.error(f"Fehler beim Download: {e}")
            raise

    async def delete_pdf(self, s3_key: str) -> bool:
        """
        Löscht PDF von S3.

        Args:
            s3_key: S3-Key der Datei

        Returns:
            True bei Erfolg

        Raises:
            ClientError: Bei S3-Fehler
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            logger.info(f"PDF erfolgreich gelöscht: {s3_key}")
            return True

        except ClientError as e:
            logger.error(f"Fehler beim Löschen: {e}")
            raise

    def generate_presigned_url(
        self, s3_key: str, expiration: int = 3600
    ) -> Optional[str]:
        """
        Generiert eine Presigned URL für temporären Zugriff.

        Args:
            s3_key: S3-Key der Datei
            expiration: Gültigkeit in Sekunden (Standard: 1 Stunde)

        Returns:
            Presigned URL oder None bei Fehler
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expiration,
            )
            logger.info(f"Presigned URL generiert für: {s3_key}")
            return url

        except ClientError as e:
            logger.error(f"Fehler bei Presigned URL: {e}")
            return None

    async def file_exists(self, s3_key: str) -> bool:
        """
        Prüft, ob eine Datei auf S3 existiert.

        Args:
            s3_key: S3-Key der Datei

        Returns:
            True wenn Datei existiert, sonst False
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False
