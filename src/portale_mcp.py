from bs4 import BeautifulSoup
import requests
from typing import List, Dict

from . import mcp

# HTML Struktur eines Login Portals
"""
<p>
<strong>
<a alt="Öffnet in neuem Tab oder Fenster" class="link link__text fc--primary" href="http://vsc.fh-swf.de/" target="_blank" title="VSC"><span class="">
</span>
<span class="link__text fc--primary">Virtuelles Service-Center</span>
</a>
</strong>
<br/>Prüfungsan- und -abmeldungen (Prüfungsordnungsversion bis 2021), Notenspiegel, Dreamspark-Datenweitergabe u.ä.</p>
"""

# URL zu der Übersicht der Login Seiten
BASE_URL = "https://www.fh-swf.de/de/login_1.php"

result = []

# Informationen der Login Portale aus dem HTML Code der Webseite auslesen
async def scrape_fh_swf_login():
    global result

    response = requests.get(BASE_URL)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    for strong_tag in soup.find_all('strong'):
        a_tag = strong_tag.find('a', href=True)
        next_sibling = strong_tag.next_sibling
        # Whitespaces/Text überspringen, bis zum nächsten Tag
        while next_sibling and (not hasattr(next_sibling, 'name') or next_sibling.name is None):
            next_sibling = next_sibling.next_sibling

        if next_sibling and next_sibling.name == 'br' and a_tag:
            text_after_br = next_sibling.next_sibling.strip() if next_sibling.next_sibling else ''
            entry = {
                'link_text': a_tag.text,
                'link_href': a_tag['href'],
                'text_after_br': text_after_br
            }
            result.append(entry)

# Funktion zur Formartierung der Informationen
def format_portals(portale: List[Dict[str, str]]) -> str:
    res = "-----------\n"
    for p in portale:
        res += f"""
Portal: {p.get('link_text', 'Unknown')}
Link: {p.get('link_href', 'Unknown')}
Description: {p.get('text_after_br', 'Unknown')}
"""
        res += "\n-----------\n"
    
    return res

@mcp.tool()
async def get_fhswf_login_portals():
    """Get Information about the login portals of the FH SWF"""
    return format_portals(result)


async def init():
    await scrape_fh_swf_login()
