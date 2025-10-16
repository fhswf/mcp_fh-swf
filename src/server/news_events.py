from mcp.server.fastmcp import FastMCP
import httpx
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
import logging

import re
import json
from typing import List, Dict, Any

import demjson3
from urllib.parse import urljoin

mcp = FastMCP("FH SWF News & Events Live")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Globale Variablen
news_cache = []
events_cache = []
last_update = None

FH_SCRAPE_URL = "https://www.fh-swf.de/de/ueber_uns/events_3/index.php"

# Funktion die alle News und Events der FH-Webseite scraped
async def scrape_fh_news_events():
    """ Scrape the FH-SWF website for all news and events."""
    global news_cache, events_cache, last_update
    logger.info("Starte Scraping FH SWF Events & News ...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(FH_SCRAPE_URL)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            
            script = soup.find("script", id="events-data")
            
            match = re.search(r'window\.EVENTS_APP_DATA\s*=\s*({.*?});?\s*$', script.string, re.DOTALL)
            if not match:
                raise ValueError("window.EVENTS_APP_DATA JSON-Objekt konnte nicht extrahiert werden")
            
            raw_json_str = match.group(1)

            # Lade JSON
            data = demjson3.decode(raw_json_str)

            

            events = []
            # Extrahieren aller Events mit den jeweiligen Informationen
            for event in data['events']:
                headline = event.get('headline')
                link = event.get('link')
                
                # Datum 
                dates = event.get('categories', {}).get('date', [])
                datename = dates[0]['name'] if dates else ''

                # Standort 
                locations = event.get('categories', {}).get('location', [])
                location_names = [loc['name'] for loc in locations]

                events.append({
                    'headline': headline,
                    'link': urljoin(FH_SCRAPE_URL, link),
                    'date': datename,
                    'locations': location_names
                })

            articles = []
            # Extrahieren aller News mit den jeweiligen Informationen
            for article in soup.find_all("article"):
                # Standort
                location = article.find('span', class_='f-weight--700', itemprop='location')
                standort = location.get_text(strip=True)[:-2] if location else None

                # Überschrift
                headline = article.find('div', class_='headline--5 mb--16 lg-mb--32', itemprop='name')
                ueberschrift = headline.get_text(strip=True) if headline else None

                # Datum
                header = article.find('header', class_='news-teaser__location')
                datum = None
                if header:
                    time_tag = header.find('time', itemprop='startDate')
                    datum = time_tag.get_text(strip=True) if time_tag else None

                # Text
                text_block = article.find('p', class_='mb--16 lg-mb--40')
                text = text_block.get_text(strip=True) if text_block else None

                # Link
                link_tag = article.find('a', class_='button button--secondary')
                artikel_link = link_tag['href'].strip() if link_tag else None

                articles.append({
                    'standort': standort,
                    'ueberschrift': ueberschrift,
                    'datum': datum,
                    'text': text,
                    'artikel_link': urljoin("https://www.fh-swf.de", artikel_link)
                })
            news_cache = articles
            events_cache = events
            last_update = datetime.now()
            logger.info(f"News: {len(news_cache)}, Events: {len(events_cache)}")
    except Exception as e:
        logger.error(f"Scraping Fehler: {e}")

# Funktion zur Formatierung aller News in einen String
def format_news(news: List[Dict[str, str]]) -> str:
    res = "-----------\n"
    for n in news:
        res += f"""
location: {n.get('standort', 'Unknown')}
headline: {n.get('ueberschrift', 'Unknown')}
date: {n.get('datum', 'Unknown')}
text: {n.get('text', 'Unknown')}
link: {n.get('artikel_link', 'Unknown')}
"""
        res += "\n-----------\n"
    
    return res

# Funktion zur Formatierung aller Events in einen String
def format_events(events: List[Dict[str, Any]]) -> str:
    res = "-----------\n"
    for e in events:
        res += f"""
location: {e.get('locations', 'Unknown')}
headline: {e.get('headline', 'Unknown')}
date: {e.get('date', 'Unknown')}
link: {e.get('link', 'Unknown')}
"""
        res += "\n-----------\n"
    
    return res


@mcp.tool()
def refresh_data() -> str:
    """Scrape the data from the FH-SWF website."""
    asyncio.create_task(scrape_fh_news_events())
    return f"Daten werden im Hintergrund aktualisiert ... Letzter Stand: {last_update}"

@mcp.tool()
def get_all_news() -> str:
    """Get all news"""
    if not news_cache:
        return "Keine News geladen. Bitte erst refresh_data() aufrufen."
    return format_news(news_cache)

@mcp.tool()
def get_all_events() -> str:
    """Get all events"""
    if not events_cache:
        return "Keine Events geladen. Bitte erst refresh_data() aufrufen."
    return format_events(events_cache[:10])

@mcp.tool()
async def get_news_details(headline: str) -> str:
    """ Get news to a given headline
    Args:
        headline: headline of the news
    """
    res = [n for n in news_cache if headline.lower() in n['ueberschrift'].lower()]
    if not res:
        return f"Keine News für Titel '{headline}' gefunden."
    n = res[0]
    async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(n["artikel_link"])
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            div = soup.find("div", class_="content-wrapper")
            
    return div.get_text()

@mcp.tool()
async def get_event_details(headline: str) -> str:
    """ Get events to a given headline
    Args:
        headline: headline of the event
    """
    res = [e for e in events_cache if headline.lower() in e['headline'].lower()]
    if not res:
        return f"Kein Event für Titel '{headline}' gefunden."
    e = res[0]
    async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(e["link"])
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            div = soup.find("main")
    return div.get_text()

async def init():
    await scrape_fh_news_events()
    logger.info("Server bereit!")

if __name__ == "__main__":
    asyncio.run(init())
    mcp.run()