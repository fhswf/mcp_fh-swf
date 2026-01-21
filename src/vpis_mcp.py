from typing import List, Dict
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import aiohttp
import re
from src.common.vpis import *
from src.common.auth import get_user
from . import mcp


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
    """Get Information about the activities of a employee
    Args:
        employee: employee name
    """
    await check_and_update_vpis_data()
    employees = list(vpis_employee.keys())
    if employee not in employees:
        return "please call the tool again, employee must be in: " + ", ".join(employees)
    
    return format_information(vpis_employee[employee])


def _extract_selected_option(html: str, field_name: str) -> str | None:
    """Extract selected option value from an HTML select field."""
    pattern = rf'<select[^>]*name="{re.escape(field_name)}"[^>]*>(.*?)</select>'
    select_match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if not select_match:
        return None
    
    for opt in re.finditer(r'<option([^>]*)value="([^"]+)"([^>]*)>', select_match.group(1), re.IGNORECASE):
        if 'selected' in opt.group(1).lower() or 'selected' in opt.group(3).lower():
            return opt.group(2)
    return None


async def get_booking_form_defaults(room: str, date: str, begin: str, end: str, hostkey: str, suitability: str) -> dict:
    """Get pre-selected department and scheduler for a room booking."""
    semester =  get_current_semester()
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

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=post_data) as response:
            if response.status != 200:
                raise ValueError(f"Failed to get booking form: status {response.status}")
            html = await response.text(encoding='iso-8859-1')
    
    return {
        "department": _extract_selected_option(html, "Veranstaltung[Department]"),
        "scheduler": _extract_selected_option(html, "scheduler"),
    }


@mcp.tool()
async def book_room(room: str, date: str, begin: str, end: str, event_name: str, event_type: str) -> str:
    """Book a room for a specific location.

    Args:
        room: Room name (e.g., 'Is-A006', 'Ha-H102').
        date: Date in DD.MM.YYYY format.
        begin: Start time in HH:MM format.
        end: End time in HH:MM format.
        event_name: Name of the event.
        event_type: Event type key (bauarbeiten, buchen, coaching, etc.).

    Returns:
        Confirmation message or error description.
    """
    await check_and_update_vpis_data()

    event_type_lower = event_type.lower().strip()
    if event_type_lower not in EVENT_TYPE_MAP:
        return f"Invalid event_type '{event_type}'. Valid: {', '.join(EVENT_TYPE_MAP.keys())}"

    user = get_user()
    name = user.name  
    email = user.email  
    
    if not name or not email:
        return "Unauthorized: You have to have select in the settings to allow the MCP-server to get your name and email"

    # Room metadata
    try:
        location = get_location_from_room(room)
        hostkey = get_room_hostkey(room, vpis_room_meta)
        suitability = get_room_suitability(room, vpis_room_meta)
        weekday = get_weekday_from_date(date)
    except ValueError as e:
        return str(e)

    # Form defaults
    try:
        defaults = await get_booking_form_defaults(room, date, begin, end, hostkey, suitability)
        if not defaults.get("department"):
            return f"Could not determine department for room {room}."
        if not defaults.get("scheduler"):
            return f"Could not determine scheduler for room {room}."
    except Exception as e:
        return f"Failed to get booking form defaults: {e}"

    # Submit booking
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

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=post_data) as response:
                text = await response.text(encoding='iso-8859-1')
                if response.status != 200:
                    return f"Booking failed with status {response.status}: {text[:500]}"
                
                success = (
                    "Es wurde eine Raumbuchung " in text
                    and "Die/Der verantwortliche Planer/in" in text
                    and "wird die Veranstaltung freigeben (Schritt 3 von 3)." in text
                )

                if not success:
                    return "Error while booking a room!"
                
                return (
                    f"Raum '{room}' Buchungsanfrage gesendet!\n"
                    f"Datum: {date} ({weekday})\n"
                    f"Zeit: {begin} - {end}\n"
                    f"Veranstaltung: {event_name}\n"
                    "Bitte prüfen Sie die Bestätigung per E-Mail."
                )
    except aiohttp.ClientError as e:
        return f"Network error: {e}"