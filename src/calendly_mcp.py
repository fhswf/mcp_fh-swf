import logging
from src.common.calendly import *

from . import mcp

from datetime import date, datetime, timedelta, time


# Funktion macht API Call an Calendly und fragt alle freien Termine in einem Zeitraum ab
async def make_calendly_request(start_time, end_time) -> str:
    result = ""
    
    # UUID des Calendly Nutzers herausfinden
    user = get_current_user()["resource"]
    user_uri = user["uri"]
    user_name = user["name"]
    
    result += "Host name: " + user_name + "\n" 
    
    # Event Typen und URI herausfinden
    events = get_event_type(user_uri)
    
    for e in events["collection"]:
        
        result += "Meeting type: " + e["name"] + "\n"
        result += "Duration in minutes: " + str(e["duration"]) + "\n"
        result += "Scheduling URL for meeting type: " + e["scheduling_url"] + "\n"
    
        event_type = e["uri"]
        
        
        # Freie Termine fuer das Event in einem Zeitraum suchen
        event_times = list_event_type_available_times(event_type = event_type, start_time = start_time, end_time = end_time)
        
        if event_times["collection"]:
            for slot in event_times["collection"]:
                
                # UTC Zeit zurueck nach MEZ und freie Slots mit Link speichern
                utc_time = datetime.fromisoformat(slot["start_time"])
                mez_time = utc_time.astimezone(ZoneInfo("Europe/Berlin"))
                start_time = mez_time.strftime("%Y-%m-%d %H:%M:%S")
    
                result += "Free meeting slot (start time): " + str(start_time) + "\n"
                result += "Scheduling URL for the meeting slot: " + slot["scheduling_url"] + "\n\n"
        else:
            return "No free slots in the given timespan"
            
    return result

@mcp.tool()
async def get_meeting_slots(start_date: str, end_date: str):
    """Get all free meeting slots between start_date and end_date. start_date and end_date cannot be apart more than 7 days.
    
    Args:
        start_date: starting date (YYYY-MM-DD)
        end_date: end date (YYYY-MM-DD)
    """
    
    # Unwandeln der Strings in date-Objekte
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        return "please call the tool again, Invalid start_date format"
    
    try:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return "please call the tool again, Invalid end_date format"

    # Pruefen ob das Enddatum nach dem Startdatum liegt und nicht mehr als 7 Tage entfernt ist
    if end_date < start_date:
        return "please call the tool again, Invalid date, end_date is before the start_date"
    
    elif end_date > start_date + timedelta(days = 7):
        return "please call the tool again, Invalid date, end_date is more than 7 days away"
    
    # Bei aktuellem Tag 60 Sekunden addieren um Datum in der Vergangenheit zu vermeiden
    if start_date == date.today():
        start_date = datetime.now() + timedelta(seconds = 60)
    
    # Ansonsten immer um 0 Uhr beginnen
    else:
        start_date = datetime.combine(start_date, time(0,0,0))

    # Enddatum immer bis 23:59 Uhr
    end_date = datetime.combine(end_date, time(23, 59, 0))
    
    result = await make_calendly_request(start_time = start_date, end_time = end_date)
        
    return result


    