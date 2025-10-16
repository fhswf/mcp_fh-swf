import os
import fitz  # PyMuPDF, für PDF Text Extraktion
from mcp.server.fastmcp import FastMCP

import asyncio
import logging

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# lokaler Pfad zum Ordner mit den Pruefungsordnungen
PDF_FOLDER = "C:\\aaUniMaster\\Semester5\\Projekt\\Umsetzung\\pruefungsordnungen"

mcp = FastMCP("Pruefungsordnungen")

# persistenten ChromaDB Client initialisieren
client = chromadb.PersistentClient(path="C:\\aaUniMaster\\Semester5\\Projekt\\Umsetzung\\chroma_db")
# Embedder initialisieren
embedder = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

try:
    collection = client.get_collection("pruefungsordnungen")
except Exception:
    collection = client.create_collection("pruefungsordnungen", embedding_function=embedder)



@mcp.tool()
def get_context(search_term: str) -> str:
    """Get context information about a search term from the examination regulations

    Args:
        search_term: keyword from the examination regulations
    """
    logger.info(search_term)
    
    # Suche in der Vektordatenbank
    results = collection.query(
        query_texts=[search_term],
        n_results=2
    )
    logger.info(results)
    if results and results['documents'][0]:
        context = results['documents'][0][0]
    else:
        return "Keine Ergebnisse gefunden"

    
    return context

@mcp.tool()
def list_subjects() -> list[str]:
    """Get all possible file names and thus subjects"""
    # Liste alle PDF-Dateien (ohne .pdf) im Ordner als Fächer/Liste zurück
    files = os.listdir(PDF_FOLDER + '/')
    subjects = [f[:-4] for f in files if f.lower().endswith(".pdf")]
    return subjects

@mcp.tool()
def get_exam_regulation(subject: str, subjects: list[str] = list_subjects()) -> str:
    """Get information about a specific subject

    Args:
        subject: subject for the specific information
        subjects: should not be used, the default argument is the list of all possible subjects
    """
    if subject not in subjects:
        return f"Ungültiges Fach: {subject}. Bitte wähle eines aus: {', '.join(subjects)}"
    # Lade und extrahiere Text der PDF zur Prüfungsordnung für das ausgewählte Fach
    path = os.path.join(PDF_FOLDER, f"{subject}.pdf")
    if not os.path.exists(path):
        return f"Prüfungsordnung für {subject} nicht gefunden."
    try:
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return f"Fehler beim Lesen der Prüfungsordnung: {e}"


if __name__ == "__main__":
    mcp.run()
