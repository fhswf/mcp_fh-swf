import re

from bs4 import BeautifulSoup

import demjson3
from urllib.parse import urljoin
import requests

BASE_URL = "https://www.fh-swf.de/de/studienangebot/studiengaenge/index.php"

# Funktion crawlt die Übersicht der Studiengänge und gibt ein dict mit Kurzbeschreibung, Standort und Link zum Studiengang zurück
def get_study_programs_information():
    response = requests.get(BASE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # script Tag finden
    script = soup.find("script", id="course-data")
       
    # JSON ähnliches Objekt aus dem script Tag auslesen
    match = re.search(
        r'window\.COURSE_APP_DATA\s*=\s*(\[.*?\]);',
        script.string,
        re.DOTALL
    )

    if not match:
        raise ValueError("window.COURSE_APP_DATA JSON-Objekt konnte nicht extrahiert werden")

    raw_json_str = match.group(1)

    data = demjson3.decode(raw_json_str)

    data = data[0]

    study_programs = {}
    # Daten aus JSON Objekt auslesen und formartiert in der Vektordatenbank ChromaDB speichern
    for course in data['courses']:
        information = {
            "text": course["text"],
            "location": course["categories"]["location"][0]["name"],
            "link": urljoin(BASE_URL, course["link"])
        } 

        study_programs[course["headline"]] = information
    
    return study_programs
        