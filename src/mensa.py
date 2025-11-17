import requests
from bs4 import BeautifulSoup
from datetime import datetime

from . import mcp

# Funktion zum Abrufen des Mensaspeiseplans an den Standorten und verschiedenen Zeiten
def fetch_mensa_speiseplan(date: str, location: str):
    
    """Get the menu at a specific cafeteria at a given date.
    Args:
        date: when the menu is served
        location: where the cafeteria is
    """
    #url = "https://www.stwdo.de/mensa-cafes-und-catering/fh-suedwestfalen/iserlohn/2025-09-17"
    
    # Bei keiner Angabe eines Datum das aktuelle im Format yyyy-mm-dd verwenden
    
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    except ValueError:
        return "Invalid date format, please use YYYY-MM-DD"
        
        
    # Pruefen ob der Standort gueltig ist
    if not location.lower() in ["iserlohn", "hagen", "meschede", "soest"]:
        return "location must be in [iserlohn, hagen, meschede, soest]"
    location = location.lower()
    
    # Datum in URL-Format bringen (yyyy-mm-dd) und Anfrage an Website mit Standort und Datum senden
    date_str = date_obj.strftime("%Y-%m-%d")
    url = f"https://www.stwdo.de/mensa-cafes-und-catering/fh-suedwestfalen/{location}/{date_str}"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Auslesen des Speiseplans über alle <table> Elemente
    tables = soup.find_all("table")
    speiseplan_text = ""
    for table in tables:
        speiseplan_text += table.get_text(separator="\n") + "\n\n"
    return speiseplan_text.strip()


@mcp.tool()
def get_cafeteria_menu(datum: str, location: str):
    """Get the menu at a specific cafeteria at a given date and location
    Args:   
        datum: date in format YYYY-MM-DD
        location: cafeteria location (iserlohn, hagen, meschede, soest)
    """
    try:
        speiseplan = fetch_mensa_speiseplan(datum, location)
        return {"speiseplan": speiseplan}
    except Exception as e:
        return {"error": str(e)}


