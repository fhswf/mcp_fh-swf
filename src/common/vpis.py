from datetime import datetime, timedelta
import aiohttp
import asyncio
import xml.etree.ElementTree as ET

# Funktion zum Abrufen einer Webseite
async def fetch_page(session, url):
    async with session.get(url) as response:
        return await response.text()

# Funktion zum gleichzeitigen Abrufen mehrerer Webseiten
async def scrape_all_pages(base_urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_page(session, url) for url in base_urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return responses

# Funktion zum Parsen der XML-Antwort
def parse_xml_response(xml_content):
    v_name = {}
    v_room = {}
    v_employee = {}
    
    try:
        # ElementTree erstellen
        root = ET.fromstring(xml_content)
    except Exception as e:
        return {}, {}, {}

    # Bereich Staffs finden
    staffs = root.find('staffs')
    
    employees = {}
    # Staff-Elemente aus Staffs auslesen, um den vollständigen Namen der Personen zu erhalten
    if staffs is not None:
        for staff in staffs.findall('staff'):
            if 'surname' in staff.attrib:
                parts = [
                    (staff.get('title2') or '').strip(),
                    (staff.get('title1') or '').strip(),
                    staff.get('forename') or '',
                    staff.get('surname') or ''
                ]
                key = staff.findtext('name')
                value = ' '.join(part for part in parts if part)
                if key:
                    employees[key] = value

    # Bereich Locations finden
    locations = root.find('locations')
    locations_description = {}
    if locations is not None:
        for location in locations.findall('location'):
            key = location.findtext('name')
            value = location.findtext('description')
            if key:
                locations_description[key] = value

    # Bereich Activities finden
    activities = root.find('activities')
    # Activitiy-Elemente aus Activities auslesen, um den Namen der Veranstaltung, den Veranstaltungstyp,
    # die Termine, den Raum und die Lehrpersonen zu ermitteln
    if activities is not None:
        for activity in activities.findall('activity'):
            act = {}
            name = activity.findtext('name')
            act['name'] = name

            activity_type = activity.findtext('activity-type')
            act['activity_type'] = activity_type

            termine = []
            for date_elem in activity.findall('./activity-dates/activity-date'):
                termine.append({
                    'date': date_elem.get('date'),
                    'begin': date_elem.get('begin'),
                    'end': date_elem.get('end')
                })
            act['dates'] = termine

            ort = activity.findtext('./activity-locations/activity-location')
            act['room'] = ort
            act['room_description'] = locations_description.get(ort, 'Unknown')

            # kurzen Namen aus der Aktivität mit dem langen Namen aus dem staff Tag ersetzen
            lehrpersonal = [p.text for p in activity.findall('./activity-staffs/activity-staff')]
            names = [employees[key] for key in lehrpersonal if key in employees]
            act['employees'] = names

            # Informationen in den dicts nach unterschiedlichen Schlüsseln speichern
            if name not in v_name:
                v_name[name] = []
            if act not in v_name[name]:
                v_name[name].append(act)

            if ort not in v_room:
                v_room[ort] = []
            if act not in v_room[ort]:
                v_room[ort].append(act)

            for employee in names:
                if employee not in v_employee:
                    v_employee[employee] = []
                if act not in v_employee[employee]:
                    v_employee[employee].append(act)

    return v_name, v_room, v_employee

# Funktion zum Sammeln der VPIS-Daten
async def collect_vpis_data():
    # Daten für die nächsten 14 Tage abrufen, um zweiwöchige Veranstaltungen zu erfassen
    today = datetime.today()
    next_14_days = [today + timedelta(days=i) for i in range(14)]
    formatted_dates = [date.strftime('%Y-%m-%d') for date in next_14_days]
    # Standorte
    location_strings = ["Iserlohn", "Hagen", "Meschede", "Soest"]

    # URLs für alle Standorte und die nächsten 14 Tage erstellen
    urls = []
    for loc in location_strings:
        base_url = f'https://vpis.fh-swf.de/WS2025/raum.php3?Raum=&Standort={loc[:2]}&Template=XML&Tag='
        urls.extend([base_url + date for date in formatted_dates])

    # Daten abrufen
    responses = await scrape_all_pages(urls)

    vpis_name = {}
    vpis_room = {}
    vpis_employee = {}
    
    # Antworten auslesen und in gemeinsamem Dictionary speichern
    for resp in responses:
        if resp and not isinstance(resp, Exception):
            v_name, v_room, v_employee = parse_xml_response(resp)
            # Dicts zusammenführen
            for key, value in v_name.items():
                if key not in vpis_name:
                    vpis_name[key] = []
                vpis_name[key].extend(value if isinstance(value, list) else [value])
            
            for key, value in v_room.items():
                if key not in vpis_room:
                    vpis_room[key] = []
                vpis_room[key].extend(value if isinstance(value, list) else [value])
            
            for key, value in v_employee.items():
                if key not in vpis_employee:
                    vpis_employee[key] = []
                vpis_employee[key].extend(value if isinstance(value, list) else [value])

    return vpis_name, vpis_room, vpis_employee
