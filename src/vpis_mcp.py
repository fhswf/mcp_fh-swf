from typing import  Annotated, List, Dict
from datetime import datetime, timedelta
from pydantic import Field
import aiohttp
import re
import src.common.vpis as vpis
from mcp_auth_middleware import get_user
from fastmcp.utilities.logging import get_logger
from urllib.parse import urlencode
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
        vpis_name, vpis_room, vpis_employee, vpis_room_meta  = await vpis.collect_vpis_data()
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
            res += f"Date: {d['date']}, Start: {d['begin']}, End: {d['end']}\n"
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
def extract_form_defaults(html: str) -> dict:
    logger.debug("Extracting form defaults from HTML")
    defaults = {}
    
    patterns = {
        "department": r'name="Veranstaltung\[Department\]"[^>]*>.*?<option[^>]*value="([^"]+)"[^>]*selected',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            defaults[key] = match.group(1)
            logger.debug(f"Found {key}: {defaults[key]}")
        else:
            defaults[key] = None
            logger.debug(f"No selected option found for {key}")

    # Special handling for scheduler: use selected option, or fallback to the first option
    scheduler_block = re.search(r'name="scheduler"[^>]*>(.*?)</select>', html, re.DOTALL | re.IGNORECASE)
    if scheduler_block:
        defaults["scheduler"] = None
        first_valid_val = None
        selected_val = None
        
        for match in re.finditer(r'<option([^>]*)value="([^"]*)"([^>]*)>(.*?)</option>', scheduler_block.group(1), re.IGNORECASE | re.DOTALL):
            attrs_before = match.group(1).lower()
            val = match.group(2).strip()
            attrs_after = match.group(3).lower()
            text = match.group(4).strip()
            
            is_selected = 'selected' in attrs_before or 'selected' in attrs_after
            is_valid = bool(val) and "kein planer" not in text.lower()
            
            if is_valid:
                if first_valid_val is None:
                    first_valid_val = val
                if is_selected:
                    selected_val = val
                    break
        
        if selected_val:
            defaults["scheduler"] = selected_val
            logger.debug(f"Found scheduler (selected): {defaults['scheduler']}")
        elif first_valid_val:
            defaults["scheduler"] = first_valid_val
            logger.debug(f"Found scheduler (first valid option fallback): {defaults['scheduler']}")
        else:
            logger.debug("No valid option found for scheduler")
    else:
        defaults["scheduler"] = None
        logger.debug("No scheduler select block found")
    
    event_types = {}
    art_block = re.search(
        r'name="Veranstaltung\[Art\]"[^>]*>(.*?)</select>',
        html, re.DOTALL | re.IGNORECASE
    )
    if art_block:
        for match in re.finditer(
            r'<option\s+value="([^"]+)"\s*>(.*?)</option>',
            art_block.group(1), re.DOTALL
        ):
            code = match.group(1)
            label = match.group(2).strip().lower()
            if code:  
                event_types[label] = code
        logger.debug(f"Found {len(event_types)} event types")
    
    defaults["event_types"] = event_types
    return defaults

# stellt die Anfrage um den zuständigen Planer und Fachbereich zu ermitteln
async def get_booking_form_defaults(room: str, date: str, begin: str, end: str, hostkey: str, suitability: str) -> dict:
    logger.debug(f"Getting booking form defaults for room {room}, date {date}, time {begin}-{end}") 
    
    semester = vpis.get_current_semester()
    url = f"https://vpis.fh-swf.de/{semester}/raumsuche.php3"
    
    post_data = {
        "Auswahl": "Buchungsanfrageformular",
        "Standort": vpis.get_location_from_room(room),
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
        Field(description="Date in YYYY-MM-DD format (e.g., 2026-03-07)")
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
            description=f"Type of event. Must be one of: {', '.join(vpis.VALID_EVENT_TYPES)}",
            json_schema_extra={"enum": vpis.VALID_EVENT_TYPES}
        )
    ]
) -> str:
    """Book a room at FH SWF."""
    logger.info(f"Room booking request: room={room}, date={date}, time={begin}-{end}, event='{event_name}', type={event_type}")  
    
    await check_and_update_vpis_data()

    event_type_lower = event_type.lower().strip()

    # ISO-Format (YYYY-MM-DD) -> VPIS-Format (DD.MM.YYYY)
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        date_vpis = date_obj.strftime("%d.%m.%Y")
    except ValueError:
        return f"Invalid date format '{date}'. Expected YYYY-MM-DD (e.g., 2026-03-07)"

    user = get_user()
    name = user.name
    email = user.email
    print(f"User info: name={name}, email={email}")
    
    if not name or not email:
        logger.warning("Booking attempted without user credentials") 
        return "Unauthorized: You have to have select in the settings to allow the MCP-server to get your name and email"

    try:
        location = vpis.get_location_from_room(room)
        hostkey = vpis.get_room_hostkey(room, vpis_room_meta)
        suitability = vpis.get_room_suitability(room, vpis_room_meta)
        weekday = vpis.get_weekday_from_date(date_vpis)
        logger.debug(f"Room metadata: location={location}, hostkey={hostkey}, suitability={suitability}, weekday={weekday}")  
    except ValueError as e:
        logger.error(f"Room metadata error: {e}") 
        return str(e)

    try:
        defaults = await get_booking_form_defaults(room, date_vpis, begin, end, hostkey, suitability)
        if not defaults.get("department"):
            logger.error(f"Could not determine department for room {room}") 
            return f"Could not determine department for room {room}."
        if not defaults.get("scheduler"):
            logger.error(f"Could not determine scheduler for room {room}") 
            return f"Could not determine scheduler for room {room}."
    except Exception as e:
        logger.error(f"Failed to get booking form defaults: {e}")  
        return f"Failed to get booking form defaults: {e}"

    event_type_code = defaults["event_types"].get(event_type_lower)
    if not event_type_code:
        available = ", ".join(defaults["event_types"].keys())
        logger.warning(f"Event type '{event_type_lower}' not found in form. Available: {available}")
        return f"Event type '{event_type}' not available. Available types: {available}"

    # führt eine Buchung aus 
    semester = vpis.get_current_semester()
    url = f"https://vpis.fh-swf.de/{semester}/raumsuche.php3"
    
    post_data = {
        "Auswahl": "Buchungsanfrageformular",
        "Veranstaltung[LocationSuitability]": suitability,
        "Template": "2021",
        "Standort": location,
        "Wochentag": weekday,
        "SucheDatum": date_vpis,
        "SucheStart": begin,
        "SucheEnde": end,
        "Raum[]": hostkey,
        "Veranstaltung[Department]": defaults["department"],
        "Veranstaltung[Name]": event_name,
        "Veranstaltung[Art]": event_type_code,
        "Nutzer[Name]": name,
        "Nutzer[eMail]": email,
        "Nutzung": "",
        "url": "",
        "scheduler": defaults["scheduler"],
        "submit": "absenden",
    }

    logger.debug(f"Submitting booking request to {url}") 
    logger.debug(f"URL-encoded payload: {urlencode(post_data)}")

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