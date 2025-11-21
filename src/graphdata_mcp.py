import os
from sentence_transformers import SentenceTransformer

from . import mcp, neo_handler

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

current_dir = os.path.dirname(os.path.abspath(__file__))

project_root = os.path.abspath(os.path.join(current_dir, '..'))



@mcp.tool()
def find_location_by_studyprogram(studyprogram: str) -> str:
    """Finde den Standort anhand des Studiengangsnamens
    Args:
        studyprogram: Studiengangsname
    """
    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "please call the tool again, studyprogram must be in: " + ", ".join(all_studyprograms)

    location = neo_handler.find_location_by_studyprogram(studyprogram)

    return studyprogram + " befindet sich am Standort " + location

@mcp.tool()
def find_studyprograms_by_department(department: str) -> str:
    """Finde Studiengänge anhand des Fachbereichsnamens
    Args:
        department: Fachbereichsname
    """
    all_departments = neo_handler.find_all_departments()
    
    if not department in all_departments:
        return "please call the tool again, department must be in: " + ", ".join(all_departments)

    studyprograms = neo_handler.find_studyprograms_by_department(department)

    return department + " bietet " + ", ".join(studyprograms)

@mcp.tool()
def find_departments_by_location(location: str) -> str:
    """Finde Fachbereiche anhand des Standortnamens
    Args:
        location: Standortname
    """
    all_locations = neo_handler.find_all_locations()
    
    if not location in all_locations:
        return "please call the tool again, location must be in: " + ", ".join(all_locations)

    departments = neo_handler.find_departments_by_location(location)

@mcp.tool()
def find_information_for_studyprogram(studyprogram: str, query: str) -> str:
    """ find information for studyprogram
    information about:
    - general studyprogram information
    - examination forms
    - thesis, certificate

    Args:
        studyprogram: Studiengangsname
        location: Standortname
        query: Suchanfrage
    """
    
    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "please call the tool again, studyprogram must be in: " + ", ".join(all_studyprograms)
    
    query_vector = model.encode(query).tolist()

    result = neo_handler.find_studyprogram_segments_similarity(studyprogram, query_vector)

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
    """Finde Informationen für ein Modul
    Args:
        studyprogram: Studiengangsname
        modul: Modulname
    """

    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "please call the tool again, studyprogram must be in: " + ", ".join(all_studyprograms)
    
    all_modules = neo_handler.find_all_modules_by_studyprogram(studyprogram)

    if not modul in all_modules:
        return "please call the tool again, modul must be in: " + ", ".join(all_modules)

    result = neo_handler.find_modul_info_by_studyprogram(studyprogram, modul)

    answer = modul
    for key, value in result["modul"].items():
        answer += "\n" + key + ": " + str(value)
    
    return answer

@mcp.tool()
def get_person_information(name: str) -> str:
    """Finde Informationen über eine Person, die an der FH SWF arbeitet
    Gibt zurück:
    - Arbeitsadresse
    - Telefonnummer
    - E-Mail-Adresse
    - Homepage

    Args:
        name: Name der Person
    """

    all_persons = neo_handler.find_all_persons()

    if not name in all_persons:
        return "please call the tool again, name must be in: " + ", ".join(all_persons)
    
    result = neo_handler.find_person_by_name(name)

    answer = "name: " + result["name"]

    for key, value in result.items():
        if key != 'name':
            answer += "\n" + key + ": " + value

    return answer

@mcp.tool()
def find_modules_and_studyprograms_by_person(name: str) -> str:
    """Finde Informationen darüber, welche Module in welchem Studiengang von der Person gehalten werden
    Gibt eine Auflistung zurück:
    - Modulname
    - Studiengang

    Args:
        name: Name der Person
    """
    all_persons = neo_handler.find_all_persons()

    if not name in all_persons:
        return "please call the tool again, name must be in: " + ", ".join(all_persons)
    
    result = neo_handler.find_modules_and_studyprograms_by_person(name)

    answer = "----------\n"
    for res in result:
        for key, value in res.items():
            answer += key + ": " + value + "\n"
        answer += "----------\n"

    return answer

@mcp.tool()
def get_general_studyprogram_information(studyprogram: str):
    """Finde allgemeine Informationen für den Studiengang"""
    all_studyprograms = neo_handler.find_all_studyprograms()
    
    if not studyprogram in all_studyprograms:
        return "please call the tool again, studyprogram must be in: " + ", ".join(all_studyprograms)
    
    result = neo_handler.get_studyprogram_info(studyprogram)
    
    if result:
        answer = result["name"] + "\n"
        for key, value in result.items():
            if key != "name":
                answer += key + ": " + value + "\n"
        return answer
    else:
        return "Keine Informationen für den Studiengang"

