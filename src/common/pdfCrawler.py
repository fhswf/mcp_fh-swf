import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin

# URL zu den Studiengaengen
BASE_URL = "https://www.fh-swf.de/de/studienangebot/studiengaenge"
# Start der Download URL
DOWNLOAD_BASE = "https://www.fh-swf.de/media/neu_np/hv_2"

# Verzeichnis zum Speichern der PDFs
DOWNLOAD_DIR = "downloaded_pdf"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# besuchte URLs
visited_urls = set()

# Funktion um zu prüfen, ob die URL mit '#' und dann keine '/' endet
# Somit werden URL mit Positionsmarkierungen ignoriert
def has_hash_without_slash(url):
    hash_pos = url.find("#")
    if hash_pos == -1:
        return False
    # Prüfen, ob nach dem '#' noch ein '/' im Rest des Strings vorkommt
    rest = url[hash_pos + 1:]
    return "/" not in rest


def is_valid_url(url):
    # Nur URLs zulassen, die mit BASE_URL beginnen und keine Positionsmarkierung haben
    return url.startswith(BASE_URL) and not has_hash_without_slash(url)

# Funktion zum Download der PDFs, die unterhalb der Download URL liegen
def download_pdf(pdf_url):
    if not pdf_url.startswith(DOWNLOAD_BASE):
        print(f"Skipping (outside download base): {pdf_url}")
        return
    local_filename = os.path.join(DOWNLOAD_DIR, pdf_url.split("/")[-1])
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
        with open(local_filename, "wb") as f:
            f.write(response.content)
        print(f"Downloaded: {pdf_url}")
    except Exception as e:
        print(f"Fehler beim Download von {pdf_url}: {e}")

# rekursive Funktion zum durchlaufen aller Links beginnend bei der Base URL
def crawl(url):
    if url in visited_urls:
        return
    if not is_valid_url(url):
        return
    
    print(f"Crawling: {url}")
    visited_urls.add(url)
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        for link in soup.find_all("a", href=True):
            href = link['href']
            full_url = urljoin(url, href)
            if full_url.lower().endswith(".pdf"):
                download_pdf(full_url)
            elif full_url.startswith(BASE_URL) and full_url not in visited_urls:
                crawl(full_url)
    except Exception as e:
        print(f"Fehler beim Zugriff auf {url}: {e}")

if __name__ == "__main__":
    crawl(BASE_URL)
