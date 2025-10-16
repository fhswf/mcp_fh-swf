import re

# Funktion zur Entfernung akademischer Titel
def normalize_name(name: str) -> str:
    # akademische Titel entfernen
    
    name = name.replace("Dr.-", "Dr. ")

    cleaned = re.sub(r"\bProf\.?\b", "", name)
    cleaned = re.sub(r"\bDr\.?\b(?!-)", "", cleaned)         
    cleaned = re.sub(r"\bDr-Ing\.?\b", "", cleaned)
    cleaned = re.sub(r"\brer\.?\s*nat\.?\b", "", cleaned)
    cleaned = re.sub(r"\bRA\b", "", cleaned)
    cleaned = re.sub(r"\bRechtsanwalt\b", "", cleaned)


    # Leerzeichen entfernen
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned