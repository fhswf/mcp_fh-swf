"""
MCP-Tools für Prüfungsordnungen (Lesezugriff für LLM)

Folgt dem Muster aus src/graphdata_mcp.py
"""

from typing import List, Dict, Optional
from . import mcp, neo_handler
from .common.po_repository import PORepository

# Repository initialisieren
po_repo = PORepository(neo_handler.driver)


@mcp.tool()
async def get_pruefungsordnungen() -> List[Dict]:
    """
    Alle verfügbaren Prüfungsordnungen auflisten.

    Returns:
        Liste von Prüfungsordnungen mit Metadaten
    """
    pos = await po_repo.get_all_pos()
    return pos


@mcp.tool()
async def get_module_einer_po(studiengang: str, semester: Optional[int] = None) -> List[Dict]:
    """
    Module einer Prüfungsordnung abrufen, optional nach Semester filtern.

    Args:
        studiengang: Name des Studiengangs
        semester: Semester-Nr (optional, z.B. 1, 2, 3)

    Returns:
        Liste von Modulen mit ECTS, Prüfungsform, Dozent
    """
    # Finde PO-ID für Studiengang (nimm die neueste)
    all_pos = await po_repo.get_all_pos()
    matching_po = None
    for po in all_pos:
        if po.get("studiengang", "").lower() == studiengang.lower():
            matching_po = po
            break

    if not matching_po:
        return []

    po_id = matching_po.get("id")
    modules = await po_repo.get_modules_by_po(po_id, semester)
    return modules


@mcp.tool()
async def get_ects_uebersicht(studiengang: str) -> List[Dict]:
    """
    ECTS-Punkte pro Modul und Semester einer Prüfungsordnung.

    Args:
        studiengang: Name des Studiengangs

    Returns:
        Liste von Modulen mit ECTS und Semester
    """
    modules = await get_module_einer_po(studiengang)

    # Formatiere Ausgabe für ECTS-Übersicht
    ects_overview = []
    for modul in modules:
        ects_overview.append({
            "modul": modul.get("name", "N/A"),
            "kuerzel": modul.get("kuerzel", "N/A"),
            "semester": modul.get("semester", "N/A"),
            "ects": modul.get("ects", 0),
            "workload_h": modul.get("workload_h", 0),
        })

    return ects_overview


@mcp.tool()
async def get_pruefungsformen(studiengang: str, modul: Optional[str] = None) -> List[Dict]:
    """
    Prüfungsformen eines Studiengangs, optional nach Modul filtern.

    Args:
        studiengang: Name des Studiengangs
        modul: Modulname oder -kürzel (optional)

    Returns:
        Liste von Modulen mit Prüfungsformen
    """
    modules = await get_module_einer_po(studiengang)

    # Filtern nach Modul (falls angegeben)
    if modul:
        modules = [
            m for m in modules
            if modul.lower() in m.get("name", "").lower()
            or modul.lower() in m.get("kuerzel", "").lower()
        ]

    # Formatiere Ausgabe für Prüfungsformen
    pruefungsformen = []
    for m in modules:
        pruefungsformen.append({
            "modul": m.get("name", "N/A"),
            "kuerzel": m.get("kuerzel", "N/A"),
            "pruefungsform": m.get("pruefungsform", "N/A"),
            "dauer_min": m.get("dauer_min", "N/A"),
        })

    return pruefungsformen


@mcp.tool()
async def suche_nach_modul(suchbegriff: str) -> List[Dict]:
    """
    Modulsuche über alle Prüfungsordnungen hinweg.

    Args:
        suchbegriff: Suchbegriff (Modulname oder Kürzel)

    Returns:
        Liste von Modulen mit Studiengang und Version
    """
    modules = await po_repo.search_modules(suchbegriff)
    return modules


@mcp.tool()
async def get_dozenten_po(studiengang: str) -> List[Dict]:
    """
    Verantwortliche Dozenten einer Prüfungsordnung.

    Args:
        studiengang: Name des Studiengangs

    Returns:
        Liste von Dozenten mit ihren Modulen
    """
    modules = await get_module_einer_po(studiengang)

    # Gruppiere nach Dozenten
    dozenten_map = {}
    for modul in modules:
        dozent = modul.get("dozent")
        if dozent and dozent != "N/A":
            if dozent not in dozenten_map:
                dozenten_map[dozent] = []
            dozenten_map[dozent].append({
                "modul": modul.get("name"),
                "kuerzel": modul.get("kuerzel"),
                "semester": modul.get("semester"),
            })

    # Formatiere Ausgabe
    dozenten_liste = []
    for dozent, module in dozenten_map.items():
        dozenten_liste.append({
            "dozent": dozent,
            "module": module,
            "anzahl_module": len(module),
        })

    return dozenten_liste
