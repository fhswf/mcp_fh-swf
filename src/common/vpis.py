from datetime import datetime, timedelta
import aiohttp
import asyncio
import xml.etree.ElementTree as ET

from fastmcp.utilities.logging import get_logger
logger = get_logger(__name__)

LOCATION_PREFIXES = {"Is": "Is-", "Ha": "Ha-", "Me": "Me-", "So": "So-", "Ls": "Ls-"}

# Funktion zum Abrufen einer Webseite
async def fetch_page(session, url):
    logger.debug(f"Fetching URL: {url}")  
    try:
        async with session.get(url) as response:
            if response.status != 200: 
                logger.warning(f"Non-200 response ({response.status}) for URL: {url}")
            return await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        raise

# Funktion zum gleichzeitigen Abrufen mehrerer Webseiten
async def scrape_all_pages(base_urls):
    logger.info(f"Starting to fetch {len(base_urls)} URLs") 
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_page(session, url) for url in base_urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        failures = sum(1 for r in responses if isinstance(r, Exception))
        if failures > 0:
            logger.warning(f"Failed to fetch {failures}/{len(base_urls)} URLs")
        else:
            logger.debug(f"Successfully fetched all {len(base_urls)} URLs")
        
        return responses

# Funktion zum bestimmten des aktuellen Semesters
def get_current_semester():
    today = datetime.today()
    month, year = today.month, today.year
    if 3 <= month <= 8:
        semester = f"SS{year}"
    elif month in [1, 2]:
        year -= 1
        semester = f"WS{year}"
    else:
        semester = f"WS{year}"
    
    logger.debug(f"Current semester determined: {semester}")  
    return semester

# Funktion zum Parsen der XML-Antwort
def parse_xml_response(xml_content):
    v_name = {}
    v_room = {}
    v_employee = {}
    v_room_meta = {}
    
    try:
        # ElementTree erstellen
        root = ET.fromstring(xml_content)
        logger.debug("XML parsing started")
    except Exception as e:
        logger.error(f"Unexpected error parsing XML: {e}")
        return {}, {}, {}, {}

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
        logger.debug(f"Parsed {len(employees)} staff members")

    # Bereich Locations finden
    locations = root.find('locations')
    locations_description = {}
    if locations is not None:
        for location in locations.findall('location'):
            key = location.findtext('name')
            value = location.findtext('description')
            if key:
                locations_description[key] = value
                hostkey_elem = location.find('hostkey')
                v_room_meta[key] = {
                    "size": location.get('size'),
                    "sizeklausur": location.get('sizeklausur'),
                    "hostkey": hostkey_elem.text if hostkey_elem is not None else None,
                    "description": value,
                    "suitabilities": []
                }
                suitabilities = location.find('location-suitabilities')
                if suitabilities is not None:
                    for suit in suitabilities.findall('location-suitability'):
                        v_room_meta[key]["suitabilities"].append({
                            "id": suit.text,
                            "primary": suit.get('primary') == 'J',
                            "secondary": suit.get('secondary') == 'J'
                        })
        logger.debug(f"Parsed {len(locations_description)} locations")

    # Bereich Activities finden
    activities = root.find('activities')
    activity_count = 0
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
            activity_count += 1
    
    logger.debug(f"Parsed {activity_count} activities")
    return v_name, v_room, v_employee, v_room_meta 

# Funktion zum Sammeln der VPIS-Daten
async def collect_vpis_data():
    # Daten für die nächsten 14 Tage abrufen, um zweiwöchige Veranstaltungen zu erfassen
    logger.info("Starting VPIS data collection")
    today = datetime.today()
    next_14_days = [today + timedelta(days=i) for i in range(14)]
    formatted_dates = [date.strftime('%Y-%m-%d') for date in next_14_days]
    # Semester für URL bestimmen
    semester = get_current_semester()
    logger.debug(f"Collecting data for semester {semester}, dates: {formatted_dates[0]} to {formatted_dates[-1]}")

    # URLs für alle Standorte und die nächsten 14 Tage erstellen
    urls = []
    for loc in LOCATION_PREFIXES.keys():
        base_url = f'https://vpis.fh-swf.de/{semester}/raum.php3?Raum=&Standort={loc}&Template=XML&Tag='
        urls.extend([base_url + date for date in formatted_dates])

    logger.debug(f"Generated {len(urls)} URLs for {len(LOCATION_PREFIXES)} locations")
    # Daten abrufen
    responses = await scrape_all_pages(urls)

    vpis_name = {}
    vpis_room = {}
    vpis_employee = {}
    vpis_room_meta = {}

    successful_parses = 0
    
    # Antworten auslesen und in gemeinsamem Dictionary speichern
    for resp in responses:
        if resp and not isinstance(resp, Exception):
            v_name, v_room, v_employee, v_room_meta  = parse_xml_response(resp)
            # Dicts zusammenführen
            for key, value in v_name.items():
                if key not in vpis_name:
                    vpis_name[key] = []
                vpis_name[key].extend(value)
            
            for key, value in v_room.items():
                if key not in vpis_room:
                    vpis_room[key] = []
                vpis_room[key].extend(value)
            
            for key, value in v_employee.items():
                if key not in vpis_employee:
                    vpis_employee[key] = []
                vpis_employee[key].extend(value)

            vpis_room_meta.update(v_room_meta)
            successful_parses += 1

    logger.info(
        f"VPIS data collection complete: "
        f"{len(vpis_name)} activities, "
        f"{len(vpis_room)} rooms, "
        f"{len(vpis_employee)} employees "
        f"(from {successful_parses}/{len(responses)} successful responses)"
    )

    return vpis_name, vpis_room, vpis_employee, vpis_room_meta  


# übersetzt den eingegeben Event Typ in eine  vom Buchungsystem verarbeitbares Format
VALID_EVENT_TYPES = [
    "bauarbeiten", "buchen", "coaching", "elearning", "exkursion",
    "info", "klausur", "klausur_online", "kolloquium", "kompaktseminar",
    "lerngruppe", "servicearbeiten", "sitzung", "sitzung_online",
    "sprechstunde", "tagesseminar", "tagung", "training", "tutorium",
    "tutorium_online", "vortrag", "workshop",
]

WEEKDAY_MAP = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}

# Funktion zum holen eines Wochentages
def get_weekday_from_date(date_str: str) -> str:
    try:
        weekday = WEEKDAY_MAP[datetime.strptime(date_str, "%d.%m.%Y").weekday()]
        logger.debug(f"Date {date_str} -> weekday {weekday}")  
        return weekday
    except ValueError as e: 
        logger.error(f"Invalid date format '{date_str}': {e}")
        raise

# Holt den Raum für einen Standort
def get_location_from_room(room_name: str) -> str:
    for loc, prefix in LOCATION_PREFIXES.items():
        if room_name.startswith(prefix):
            logger.debug(f"Room {room_name} -> location {loc}") 
            return loc
    logger.error(f"Unknown location prefix in room: {room_name}")  
    raise ValueError(f"Unknown location prefix in room: {room_name}")

# Funktion zum holen des jeweiligen Keys der zu einem Raum gehört
def get_room_hostkey(room_name: str, vpis_room_meta: dict) -> str:
    if room_name not in vpis_room_meta:
        logger.error(f"Room not found in metadata: {room_name}") 
        raise ValueError(f"Unknown room: {room_name}")
    hostkey = vpis_room_meta[room_name].get("hostkey")
    if not hostkey:
        logger.error(f"No hostkey found for room: {room_name}") 
        raise ValueError(f"No hostkey for room: {room_name}")
    logger.debug(f"Room {room_name} -> hostkey {hostkey}")  
    return hostkey

# Raumsuchkriterium ist wichtig für Dinge wie Raumbuchung
def get_room_suitability(room_name: str, vpis_room_meta: dict) -> str:
    if room_name not in vpis_room_meta:
        logger.error(f"Room not found in metadata: {room_name}") 
        raise ValueError(f"Unknown room: {room_name}")
    suitabilities = vpis_room_meta[room_name].get("suitabilities", [])
    if not suitabilities:
        logger.error(f"No suitabilities found for room: {room_name}") 
        raise ValueError(f"No suitabilities for room: {room_name}")
    logger.debug(f"Room {room_name} -> suitability {suitabilities[0]['id']}")  
    return suitabilities[0]["id"]

