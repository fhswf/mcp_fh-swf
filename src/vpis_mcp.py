import pickle
from typing import List, Dict
from datetime import datetime
import os

from . import mcp

current_dir = os.path.dirname(os.path.abspath(__file__))

project_root = os.path.abspath(os.path.join(current_dir, '..'))

vpis_data_path = os.path.join(project_root, 'data', 'vpis')


# gespeicherte VPIS Daten auslesen
with open(os.path.join(vpis_data_path, "vpis_location.pkl"), "rb") as f:
    vpis_location = pickle.load(f)
with open(os.path.join(vpis_data_path, "vpis_employee.pkl"), "rb") as f:
    vpis_employee = pickle.load(f)
with open(os.path.join(vpis_data_path, "vpis_name.pkl"), "rb") as f:
    vpis_name = pickle.load(f)
with open(os.path.join(vpis_data_path, "vpis_room.pkl"), "rb") as f:
    vpis_room = pickle.load(f)



def format_information(modules: List[Dict[str, any]]) -> str:
    res = "-----------\n"
    for m in modules:
        res += f"""
Activity Name: {m.get('name', 'Unknown')}
Activity Type: {m.get('activity_type', 'Unknown')}
Room: {m.get('room', 'Unknown')}
"""     
        for e in m['employees']:
            res += "Employee: " + e + "\n"
        res += "Dates: \n"
        for d in m['dates']:
            res += f"Date: {d["date"]}, Start: {d["begin"]}, End: {d["end"]}\n"
        res += "\n-----------\n"
    
    return res

@mcp.tool()
def get_activity_information(modul: str):
    """Get Information about the activities of a modul
    Args:
        modul: modul name
    """
    modules = list(vpis_name.keys())
    if modul not in modules:
        return "modul must be in: " + ", ".join(modules)
    
    return format_information(vpis_name[modul])

@mcp.tool()
def get_room_activity_information(room: str):
    """Get Information about the activities in a room
    Args:
        room: room name
    """
    rooms = list(vpis_room.keys())
    if room not in rooms:
        return "room must be in: " + ", ".join(rooms)
    
    return format_information(vpis_room[room])

@mcp.tool()
def get_all_rooms(location: str=None):
    """Get Information about all rooms
    Args:
        location: select rooms from a location
    """
    locations = ["Iserlohn", "Hagen", "Soest", "Meschede"]
    if location and location not in locations:
        return "location must be in: " + ", ".join(locations)
    if location:
        all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(location[:2])]
        return "all rooms at location " + location + ": " + ", ".join(all_rooms)
    else:
        return "all rooms: " + ", ".join(list(vpis_room.keys()))

@mcp.tool()
def get_all_free_rooms(location: str, date: str, begin: str, end: str, building: str=None):
    """Get Information about all free rooms
    Args:
        location: select rooms from a location
        building: select rooms from a buildung at a location
        date: date in format %Y-%m-%d
        begin: begin time in format %H:%M
        end: end time in format %H:%M
    """
    locations = ["Iserlohn", "Hagen", "Soest", "Meschede"]
    if location and location not in locations:
        return "location must be in: " + ", ".join(locations)
    if location:

        if building:
            all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(location[:2] + "-" + building)]
        else:
            all_rooms = [room for room in list(vpis_room.keys()) if room.startswith(location[:2])]

        if date and begin and end:
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
                if counter == 0:
                    free_rooms.append(room)
                
                
            return "all free rooms at location " + location + " in buildung " + building + " at the " + date + " from " + str(begin) + " to " + str(end) + ": " + ", ".join(free_rooms)
        
        if building:
            return "all rooms at location " + location + " in buildung " + building + ": " + ", ".join(all_rooms)
        else:
            return "all rooms at location " + location + ": " + ", ".join(all_rooms)

#@mcp.tool()
def get_employee_activity_information(employee: str):
    """Get Information about the activities of a employee
    Args:
        employee: employee name
    """
    employees = list(vpis_employee.keys())
    if employee not in employees:
        return "employee must be in: " + ", ".join(employees)
    
    return format_information(vpis_employee[employee])



