from typing import  Annotated, List, Dict
from datetime import datetime, timedelta
from pydantic import Field
import aiohttp
import re
from src.common.vpis import *
from mcp_auth_middleware import get_user
from fastmcp.utilities.logging import get_logger
from . import mcp

logger = get_logger(__name__)
vpis_name = {}
vpis_room = {}
vpis_employee = {}
vpis_room_meta = {}
last_update = None
CACHE_DURATION = timedelta(hours=2)

# Daten bei einer Anfrage aktualisieren, wenn die Daten älter als CACHE_DURATION sind
async def check_and_update_vpis_data():
    global vpis_name, vpis_room, vpis_employee, vpis_room_meta, last_update

    if last_update is None or datetime.now() - last_update > CACHE_DURATION:
        vpis_name, vpis_room, vpis_employee, vpis_room_meta  = await collect_vpis_data()
        last_update = datetime.now()

def format_information(modules: List[Dict[str, any]]) -> str:
    res = "-----------\n"
    for m in modules:
        res += f"""
Activity Name: {m.get('name', 'Unknown')}
Activity Type: {m.get('activity_type', 'Unknown')}
Room: {m.get('room', 'Unknown')}
Room Description: {m.get('room_description', 'Unknown')}
"""     
        for e in m['employees']:
            res += "Employee: " + e + "\n"
        res += "Dates: \n"
        for d in m['dates']:
            res += f"Date: {d["date"]}, Start: {d["begin"]}, End: {d["end"]}\n"
        res += "\n-----------\n"
    
    return res

@mcp.tool()
async def get_activity_information(modul: str):
    """Get Information about the activities of a modul
    Args:
        modul: modul name
    """
    await check_and_update_vpis_data()
    modules = list(vpis_name.keys())
    if modul not in modules:
        return "please call the tool again, modul must be in: " + ", ".join(modules)
    
    return format_information(vpis_name[modul])

@mcp.tool()
async def get_room_activity_information(room: str):
    """Get Information about the activities in a room
    Args:
        room: room name
    """
    await check_and_update_vpis_data()
    rooms = list(vpis_room.keys())
    if room not in rooms:
        return "please call the tool again, room must be in: " + ", ".join(rooms)
    
    return format_information(vpis_room[room])

@mcp.tool()
async def get_all_rooms(location: str=None):
    """Get Information about all rooms
    Args:
        location: select rooms from a location
    """
    await check_and_update_vpis_data()
    location_prefixes = {
    "Iserlohn": "Is",
    "Hagen": "Ha",
    "Soest": "So",
    "Meschede": "Me",
    "Lüdenscheid": "Ls",
    }
    if location and location not in location_prefixes:
        return "please call the tool again, location must be in: " + ", ".join(location_prefixes)
    if location:
        prefix = location_prefixes[location]
        all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(prefix)]
        return "all rooms at location " + location + ": " + ", ".join(all_rooms)
    else:
        return "all rooms: " + ", ".join(vpis_room.keys())

@mcp.tool()
async def get_all_free_rooms(location: str, date: str, begin: str, end: str, building: str=None):
    """Get Information about all free rooms
    Args:
        location: select rooms from a location
        building: select rooms from a buildung at a location
        date: date in format %Y-%m-%d
        begin: begin time in format %H:%M
        end: end time in format %H:%M
    """
    await check_and_update_vpis_data()
    locations = ["Iserlohn", "Hagen", "Soest", "Meschede"]
    if location and location not in locations:
        return "please call the tool again, location must be in: " + ", ".join(locations)
    if not location or not date or not begin or not end:
        return "please call the tool again, please provide location, date, begin and end"
    
    if building:
        all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(location[:2] + "-" + building)]
    else:
        all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(location[:2])]

    begin = datetime.strptime(begin, "%H:%M").time()
    end = datetime.strptime(end, "%H:%M").time()
    free_rooms = []
    for room in all_rooms:
        counter = 0
        for activity in vpis_room[room]:
            for d in activity["dates"]:
                if d["date"] == date:
                    d_begin = datetime.strptime(d["begin"], "%H:%M").time()
                    d_end = datetime.strptime(d["end"], "%H:%M").time()
                    if begin < d_end and d_begin < end:
                        counter += 1
                        break
            if counter > 0:
                break
        if counter == 0:
            free_rooms.append(room)

    if building:
        return "all free rooms at location " + location + " in buildung " + building + " at the " + date + " from " + str(begin) + " to " + str(end) + ": " + ", ".join(free_rooms)
    else:
        return "all free rooms at location " + location + " at the " + date + " from " + str(begin) + " to " + str(end) + ": " + ", ".join(free_rooms)

@mcp.tool()
async def get_employee_activity_information(employee: str):
    await check_and_update_vpis_data()
    employees = list(vpis_employee.keys())
    if employee not in employees:
        return "please call the tool again, employee must be in: " + ", ".join(employees)
    
    return format_information(vpis_employee[employee])

# holt die Daten von Planer und zugehörigen Fachbereich der Buchung vom VPIS
def extract_form_defaults(html: str) -> dict[str, str | None]:
    logger.debug("Extracting form defaults from HTML")
    defaults = {}
    
    patterns = {
        "department": r'name="Veranstaltung\[Department\]"[^>]*>.*?<option[^>]*value="([^"]+)"[^>]*selected',
        "scheduler": r'name="scheduler"[^>]*>.*?<option[^>]*value="([^"]+)"[^>]*selected',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            defaults[key] = match.group(1)
            logger.debug(f"Found {key}: {defaults[key]}")
        else:
            defaults[key] = None
            logger.debug(f"No selected option found for {key}")
    
    return defaults

# stellt die Anfrage um den zuständigen Planer und Fachbereich zu ermitteln
async def get_booking_form_defaults(room: str, date: str, begin: str, end: str, hostkey: str, suitability: str) -> dict:
    logger.debug(f"Getting booking form defaults for room {room}, date {date}, time {begin}-{end}") 
    
    semester = get_current_semester()
    url = f"https://vpis.fh-swf.de/{semester}/raumsuche.php3"
    
    post_data = {
        "Auswahl": "Buchungsanfrageformular",
        "Standort": get_location_from_room(room),
        "LocationSuitability": suitability,
        "Template": "2021",
        "SucheDatum": date,
        "SucheStart": begin,
        "SucheEnde": end,
        "Raum[]": hostkey,
    }

    logger.debug(f"Posting to {url} to get form defaults")  
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=post_data) as response:
                if response.status != 200:
                    logger.error(f"Failed to get booking form: HTTP {response.status}")  
                    raise ValueError(f"Failed to get booking form: status {response.status}")
                html = await response.text(encoding='iso-8859-1')
    except aiohttp.ClientError as e:
        logger.error(f"Network error getting booking form defaults: {e}")  
        raise
    
    defaults = extract_form_defaults(html)
    
    logger.debug(f"Booking form defaults: department={defaults['department']}, scheduler={defaults['scheduler']}")  
    return defaults

# Tool zum Aufruf einer Raumbuchung
@mcp.tool()
async def book_room(
    room: str,
    date: Annotated[
        str,
        Field(description="Date in DD.MM.YYYY format (e.g., 02.02.2026)")
    ],
    begin: Annotated[
        str,
        Field(description="Start time in HH:MM format (e.g., 09:00)")
    ],
    end: Annotated[
        str,
        Field(description="End time in HH:MM format (e.g., 10:30)")
    ],
    event_name: str,
    event_type: Annotated[
        str,
        Field(
            description=f"Type of event. Must be one of: {', '.join(VALID_EVENT_TYPES)}",
            json_schema_extra={"enum": VALID_EVENT_TYPES}
        )
    ]
) -> str:
    """Book a room at FH SWF."""
    logger.info(f"Room booking request: room={room}, date={date}, time={begin}-{end}, event='{event_name}', type={event_type}")  
    
    await check_and_update_vpis_data()

    event_type_lower = event_type.lower().strip()
    if event_type_lower not in EVENT_TYPE_MAP:
        logger.warning(f"Invalid event type: '{event_type}'")  
        return f"Invalid event_type '{event_type}'. Valid: {', '.join(EVENT_TYPE_MAP.keys())}"

    user = get_user()
    name = user.name
    email = user.email
    
    if not name or not email:
        logger.warning("Booking attempted without user credentials") 
        return "Unauthorized: You have to have select in the settings to allow the MCP-server to get your name and email"

    try:
        location = get_location_from_room(room)
        hostkey = get_room_hostkey(room, vpis_room_meta)
        suitability = get_room_suitability(room, vpis_room_meta)
        weekday = get_weekday_from_date(date)
        logger.debug(f"Room metadata: location={location}, hostkey={hostkey}, suitability={suitability}, weekday={weekday}")  
    except ValueError as e:
        logger.error(f"Room metadata error: {e}") 
        return str(e)

    try:
        defaults = await get_booking_form_defaults(room, date, begin, end, hostkey, suitability)
        if not defaults.get("department"):
            logger.error(f"Could not determine department for room {room}") 
            return f"Could not determine department for room {room}."
        if not defaults.get("scheduler"):
            logger.error(f"Could not determine scheduler for room {room}") 
            return f"Could not determine scheduler for room {room}."
    except Exception as e:
        logger.error(f"Failed to get booking form defaults: {e}")  
        return f"Failed to get booking form defaults: {e}"

    # führt eine Buchung aus 
    semester = get_current_semester()
    url = f"https://vpis.fh-swf.de/{semester}/raumsuche.php3"
    
    post_data = {
        "Auswahl": "Buchungsanfrageformular",
        "Veranstaltung[LocationSuitability]": suitability,
        "Template": "2021",
        "Standort": location,
        "Wochentag": weekday,
        "SucheDatum": date,
        "SucheStart": begin,
        "SucheEnde": end,
        "Raum[]": hostkey,
        "Veranstaltung[Department]": defaults["department"],
        "Veranstaltung[Name]": event_name,
        "Veranstaltung[Art]": EVENT_TYPE_MAP[event_type_lower],
        "Nutzer[Name]": name,
        "Nutzer[eMail]": email,
        "Nutzung": "",
        "url": "",
        "scheduler": defaults["scheduler"],
        "submit": "absenden",
    }

    logger.debug(f"Submitting booking request to {url}") 

   # überprüft ob eine Raumbuchung stattgefunden hat
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=post_data) as response:
                text = await response.text(encoding='iso-8859-1')
                if response.status != 200:
                    logger.error(f"Booking request failed: HTTP {response.status}")  
                    return f"Booking failed with status {response.status}: {text[:500]}"
                
                success = (
                    "Es wurde eine Raumbuchung " in text
                    and "Die/Der verantwortliche Planer/in" in text
                    and "wird die Veranstaltung freigeben (Schritt 3 von 3)." in text
                )

                if not success:
                    logger.error(f"Booking response did not contain success markers")  
                    logger.debug(f"Response preview: {text[:500]}") 
                    return "Error while booking a room!"
                
                logger.info(f"Room booking successful: {room} on {date} ({weekday}), {begin}-{end}")  
                return (
                    f"Raum '{room}' Buchungsanfrage gesendet!\n"
                    f"Datum: {date} ({weekday})\n"
                    f"Zeit: {begin} - {end}\n"
                    f"Veranstaltung: {event_name}\n"
                    "Bitte prüfen Sie die Bestätigung per E-Mail."
                )
    except aiohttp.ClientError as e:
        logger.error(f"Network error during booking submission: {e}")  
        return f"Network error: {e}"