from mcp.server.fastmcp import FastMCP

import logging

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Mitarbeiter")

# Zugriff auf die ChromaDB gewaehren
client = chromadb.PersistentClient(path="C:\\aaUniMaster\\Semester5\\Projekt\\Umsetzung\\chroma_db_employees")
embedder = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

try:
    collection = client.get_collection("employees")
except Exception:
    collection = client.create_collection("employees", embedding_function=embedder)

@mcp.tool()
def get_context(search_term: str) -> str:
    
    """ Search the vectordatabase for informations about an employee
    Args:
        search_termn: a string containing informations about the employee
    """
    
    logger.info(search_term)
    
    # Vektordatenbank wird nach Eintraegen durchsucht, die fuer den search_termn relevant sein k�nnen
    results = collection.query(
        query_texts=[search_term],
        n_results=1
    )
    
    logger.info(results)
    if results and results['documents'][0]:
        context = results['documents'][0][0]
    else:
        return "Keine Ergebnisse gefunden"

    return context

if __name__ == "__main__":
    mcp.run()
