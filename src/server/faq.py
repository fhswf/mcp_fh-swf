import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from mcp.server.fastmcp import FastMCP
import asyncio
from bs4 import BeautifulSoup
import logging

from urllib.parse import urljoin
import requests

FH_SCRAPE_URL = "https://www.fh-swf.de/de/studierende/studienorganisation/faqs_1.php"

mcp = FastMCP("FAQ")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ChromaDB Vektordatenbank und Embeddingfunktion definieren
client = chromadb.EphemeralClient()
embedder = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Collection mit eingebauter Embedding-Funktion erzeugen
collection = client.get_or_create_collection(
    name="faq",
    embedding_function=embedder
)

async def build_rag():
    doc_to_db()
    return

def doc_to_db():
    
    """ Scrape all informations from the website and store them in the vectordatabase
    """
    
    # Anfrage an die Webseite senden und alle <accordion> tags finden
    response = requests.get(FH_SCRAPE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    accordions = soup.find_all("div", class_="accordion")

    # Iterieren durch alle <accordion> tags der Webseite
    for i, accordion in enumerate(accordions):
        accordion_items = accordion.find_all("div", class_="accordion__item")
        
        # Iterieren durch alle Eintraege des jeweiligen <accordion> und extrahieren der Informationen
        for j, accordion_item in enumerate(accordion_items):
            headline = accordion_item.find("h3", class_="headline--3")
            headline_text = headline.get_text(strip=True) if headline else None

            accordion_body = accordion_item.find("div", class_="accordion__body")
            body_text = accordion_body.get_text(separator="\n", strip=True) if accordion_body else None

            information = f"""
Headline: {headline_text}
Text: {body_text}
"""
            # Weiterfuehrende Links suchen und speichern
            a_tags = accordion_item.find_all("a")
            if a_tags:
                for a_tag in a_tags:
                    information += f"Link Text: {a_tag.get_text(strip=True)}\n"
                    information += f"Link: {urljoin(FH_SCRAPE_URL, a_tag.get("href"))}"
            
            # Alle Informationen in die Vektordatenbank schreiben
            collection.add(
                documents=[information],
                ids=["doc" + str(i) + "_" + str(j)]
            )

@mcp.tool()
def get_context(search_term: str) -> str:
    """ search the vectordatabase for informations about a topic
    Args:
        search_termn: a string containing informations about the topic
    """
    
    logger.info(search_term)

    # Vektordatenbank nach Eintraegen durchsuchen und diese als Kontext bereitstellen
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

async def init():
    await build_rag()
    logger.info("Server bereit!")


if __name__ == "__main__":
    asyncio.run(init())
    mcp.run()