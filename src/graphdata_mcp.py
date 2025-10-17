#from common.Neo4jHandler import Neo4jHandler

#from mcp.server.fastmcp import FastMCP

from typing import List, Dict

from datetime import datetime

import os

from sentence_transformers import SentenceTransformer

from dotenv import load_dotenv


from fhswf_mcp import mcp, neo_handler

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

current_dir = os.path.dirname(os.path.abspath(__file__))

project_root = os.path.abspath(os.path.join(current_dir, '..'))

#mcp = FastMCP("FH SWF MCP")

env_path = os.path.join(project_root, '.env')




@mcp.tool()
def find_location_by_studyprogram(studyprogram: str) -> str:
    """ find location by studyprogram name
    Args:
        studyprogram: studyprogram name
    """
    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "studyprogram must be in: " + ", ".join(all_studyprograms)

    location = neo_handler.find_location_by_studyprogram(studyprogram)

    return studyprogram + " is located in location " + location

@mcp.tool()
def find_studyprograms_by_department(department: str) -> str:
    """ find studyprogram by department name
    Args:
        department: department name
    """
    all_departments = neo_handler.find_all_departments()
    
    if not department in all_departments:
        return "department must be in: " + ", ".join(all_departments)

    studyprograms = neo_handler.find_studyprograms_by_department(department)

    return department + " offers " + ", ".join(studyprograms)

@mcp.tool()
def find_departments_by_location(location: str) -> str:
    """ find departmens by location name
    Args:
        location: location name
    """
    all_locations = neo_handler.find_all_locations()
    
    if not location in all_locations:
        return "location must be in: " + ", ".join(all_locations)

    departments = neo_handler.find_studyprograms_by_department(location)

    return location + " hosts departmens " + ", ".join(departments)
    
@mcp.tool()
def find_information_for_studyprogram(studyprogram: str, location: str, query: str) -> str:
    """ find information for studyprogram
    information about:
    - general studyprogram information
    - examination forms
    - thesis, certificate

    Args:
        studyprogram: studyprogram name
        location: location name
        query: query for search
    """
    all_locations = neo_handler.find_all_locations()
    
    if not location in all_locations:
        return "location must be in: " + ", ".join(all_locations)
    
    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "studyprogram must be in: " + ", ".join(all_studyprograms)
    
    query_vector = model.encode(query).tolist()

    result = neo_handler.find_studyprogram_segments_similarity(studyprogram, location, query_vector)

    answer = ""
    for res in result:
        answer += res['segment_text'] + "\n"

    result = neo_handler.find_rpo_segments_similarity(query_vector)

    answer += "\n\n\nRahmenprüfungsordnung: \n"
    for res in result:
        answer += res['segment_text'] + "\n"

    return answer

@mcp.tool()
def get_information_for_modul(studyprogram: str, modul: str) -> str:
    """ get information for a modul
    Args:
        studyprogram: studyprogram name
        modul: modul name
    """

    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "studyprogram must be in: " + ", ".join(all_studyprograms)
    
    all_modules = neo_handler.find_all_modules_by_studyprogram(studyprogram)

    if not modul in all_modules:
        return "modul must be in: " + ", ".join(all_modules)

    result = neo_handler.find_modul_info_by_studyprogram(studyprogram, modul)

    answer = modul
    for key, value in result["modul"].items():
        answer += "\n" + key + ": " + str(value)
    
    return answer

@mcp.tool()
def get_person_information(name: str) -> str:
    """ receive information about a person who works at FH SWF
    returns:
    - Workadress
    - phone number
    - mail adress
    - homepage

    Args:
        name: name of the person
    """

    all_persons = neo_handler.find_all_persons()

    if not name in all_persons:
        return "name must be in: " + ", ".join(all_persons)
    
    result = neo_handler.find_person_by_name(name)

    answer = "name: " + result["name"]

    for key, value in result.items():
        if key != 'name':
            answer += "\n" + key + ": " + value

    return answer

@mcp.tool()
def find_modules_and_studyprograms_by_person(name: str) -> str:
    """ receive information about which modules in which study program are held by the person
    returns a listing :
    - modul name
    - studyprogram

    Args:
        name: name of the person
    """
    all_persons = neo_handler.find_all_persons()

    if not name in all_persons:
        return "name must be in: " + ", ".join(all_persons)
    
    result = neo_handler.find_modules_and_studyprograms_by_person(name)

    answer = "----------\n"
    for res in result:
        for key, value in res.items():
            answer += key + ": " + value + "\n"
        answer += "----------\n"

    return answer

@mcp.tool()
def get_general_studyprogram_information(studyprogram: str):
    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "studyprogram must be in: " + ", ".join(all_studyprograms)
    
    result = neo_handler.get_studyprogram_info(studyprogram)
    print(result)
    if result:
        answer = result["name"] + "\n"
        for key, value in result.items():
            if key != "name":
                answer += key + ": " + value + "\n"
        return answer
    else:
        return "no information for studyprogram"

