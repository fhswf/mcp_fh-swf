# FH-SWF MCP Server

Ein Model Context Protocol (MCP) Server für die Fachhochschule Südwestfalen, entwickelt mit FastMCP, der zentrale Hochschulinformationen über eine einheitliche Tool-Schnittstelle bereitstellt.

## Schnelleinstieg

### Voraussetzungen
- Python 3.8+
- Neo4j Datenbank
- Dependencies aus `requirements.txt`

### Installation
```bash
pip install -r requirements.txt
```

### Konfiguration
`.env` Datei erstellen:
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
CALENDLY_API_TOKEN=your_token  # optional für die Verwendung von Calendly
```

### Server starten
```bash
python main.py
```

## Verfügbare Tools

Die Implementierung enthält Tools zum Zugriff auf Informationen aus den folgenden Bereichen:

| Tool | Beschreibung |
|------|-------------|
| **Studiengänge** | Informationen zu Studienprogrammen und Prüfungsordnungen |
| **VPIS** | Vorlesungsverzeichnis: Kurse, Räume, Dozenten, Termine |
| **Mensa** | Speiseplan der Mensa an 4 Standorten (Iserlohn, Hagen, Meschede, Soest) |
| **Bibliothek** | Bibliotheksinformationen und -ressourcen |
| **FAQ** | Häufig gestellte Fragen der FH-SWF |
| **News & Events** | Nachrichten und Veranstaltungen |
| **Calendly** | Verfügbare Termine für Besprechungen |
| **Portale** | Informationen zu den Login Portalen |

## Projektstruktur

```
ProjektKI/
├── main.py                          # Haupteinstiegspunkt - startet den MCP Server
├── requirements.txt                 # Python Abhängigkeiten
├── Dockerfile                       # Docker-Konfiguration für Container-Deployment
├── k8s/
│   └── secret.yaml                  # Kubernetes Secrets
├──src/                                 # Hauptquellcode
│   ├── __init__.py                      # MCP Server Initialisierung
│   ├── bib_mcp.py                       # Bibliotheks-Tools
│   ├── calendly_mcp.py                  # Calendly Integrations-Tools
│   ├── faq_mcp.py                       # FAQ-Tools
│   ├── graphdata_mcp.py                 # Studiengänge-Tools (Neo4j)
│   ├── mensa.py                         # Mensa-Speiseplan-Tool
│   ├── news_events_mcp.py               # News & Events-Tools
│   ├── portale_mcp.py                   # Loginportale-Tools
│   ├── vpis_mcp.py                      # VPIS-Tools
│   └── common/                          # Gemeinsame Utilities
│       ├── Neo4jHandler.py              # Neo4j Datenbank-Operationen
│       ├── neo4j_help_function.py       # Neo4j Hilfsfunktionen
│       ├── study_programs.py            # Studienganginformationen
│       ├── calendly.py                  # Calendly API
│       └── vpis.py                      # VPIS Daten abrufen
├──data_preprocessing/                  # Datenverarbeitungs-Scripts
    └── scripts/
        ├── graphdatenbank.ipynb         # Notebook zum Aufbau der Neo4j Datenbank
        ├── employee_information.py      # Script zur Verarbeitung von Mitarbeiterdaten
        ├── vpis.ipynb                   # Notebook zum Auslesen von VPIS-Daten
        ├── PDF_Preprocess.ipynb         # Notebook zum Vorverarbeiten der Modulhandbücher
        ├── TableExtraction.ipynb        # Notebook zur Extraktion von Modulinformationen aus den vorverarbeiteten Modulhandbüchern
```

## Entwicklung

### Neues Tool hinzufügen
1. `src/new_tool_mcp.py` erstellen
3. Funktionen mit `@mcp.tool()` dekorieren
4. In `main.py` importieren

### Datenverarbeitung
- `data_preprocessing/scripts/graphdatenbank.ipynb` - Notebook zum Einfügen der Informationen in die Datenbank
- `data_preprocessing/scripts/employee_information.py` - Sammlung von Mitarbeiterdaten
- `data_preprocessing/scripts/vpis.ipynb` - Notebook zum Auslesen von Informationen aus dem VPIS
- `data_preprocessing/scripts/PDF_Preprocess.ipynb` - Notebook zum Auschneiden der Modulhandbücher
- `data_preprocessing/scripts/TableExtraction.ipynb ` - Notebook zum Auslesen der Modulhandbücher mit Docling
---

