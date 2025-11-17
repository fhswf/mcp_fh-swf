from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from typing import List, Dict, Any
import demjson3
from urllib.parse import urljoin
import requests

from . import mcp

# Globale Variablen
news_cache = []
events_cache = []
last_update = None
CACHE_DURATION = timedelta(hours=2)

FH_SCRAPE_URL = "https://www.fh-swf.de/de/ueber_uns/events_3/index.php"

# Daten bei einer Anfrage aktualisieren, wenn die Daten älter als CACHE_DURATION sind
async def check_and_update_data():
    global last_update

    if last_update is None or datetime.now() - last_update > CACHE_DURATION:
        await scrape_fh_news_events()
        last_update = datetime.now()

# Funktion die alle News und Events der FH-SWF Webseite scraped
async def scrape_fh_news_events():
    global news_cache, events_cache
    
    response = requests.get(FH_SCRAPE_URL)
    response.raise_for_status()
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
async def get_all_fhswf_news() -> str:
    """Get all news from FH SWF"""
    await check_and_update_data()
    return format_news(news_cache)

@mcp.tool()
async def get_all_fhswf_events(limit: int = 10, offset: int = 0) -> str:
    """Get all events from FH SWF
    Args:
        limit: number of events to return
        offset: offset for pagination
    """
    await check_and_update_data()
    return format_events(events_cache[offset:offset+limit])

@mcp.tool()
async def get_fhswf_news_details(headline: str) -> str:
    """ Get news details to a given headline
    Args:
        headline: headline of the news
    """
    await check_and_update_data()
    res = [n for n in news_cache if headline.lower() in n['ueberschrift'].lower()]
    if not res:
        return f"No News for title '{headline}' found."
    n = res[0]
    
    response = requests.get(n["artikel_link"])
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div", class_="content-wrapper")
            
    return div.get_text()

@mcp.tool()
async def get_fhswf_event_details(headline: str) -> str:
    """ Get event details to a given headline
    Args:
        headline: headline of the event
    """
    await check_and_update_data()
    res = [e for e in events_cache if headline.lower() in e['headline'].lower()]
    if not res:
        return f"No Event for title '{headline}' found."
    e = res[0]
    
    response = requests.get(e["link"])
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("main")

    return div.get_text()
