from typing import List, Dict
from datetime import datetime, timedelta
from src.common.vpis import collect_vpis_data

from . import mcp

vpis_name = {}
vpis_room = {}
vpis_employee = {}
last_update = None
CACHE_DURATION = timedelta(hours=2)

# Daten bei einer Anfrage aktualisieren, wenn die Daten älter als CACHE_DURATION sind
async def check_and_update_vpis_data():
    global vpis_name, vpis_room, vpis_employee, last_update

    if last_update is None or datetime.now() - last_update > CACHE_DURATION:
        vpis_name, vpis_room, vpis_employee = await collect_vpis_data()
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
        return "modul must be in: " + ", ".join(modules)
    
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
        return "room must be in: " + ", ".join(rooms)
    
    return format_information(vpis_room[room])

@mcp.tool()
async def get_all_rooms(location: str=None):
    """Get Information about all rooms
    Args:
        location: select rooms from a location
    """
    await check_and_update_vpis_data()
    locations = ["Iserlohn", "Hagen", "Soest", "Meschede"]
    if location and location not in locations:
        return "location must be in: " + ", ".join(locations)
    if location:
        all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(location[:2])]
        return "all rooms at location " + location + ": " + ", ".join(all_rooms)
    else:
        return "all rooms: " + ", ".join(list(vpis_room.keys()))

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
        return "location must be in: " + ", ".join(locations)
    if not location or not date or not begin or not end:
        return "please provide location, date, begin and end"
    
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
        return "employee must be in: " + ", ".join(employees)
    
    return format_information(vpis_employee[employee])
