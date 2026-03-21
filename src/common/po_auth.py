"""
Auth-Platzhalter für Prüfungsordnungs-API

HINWEIS: Dies ist ein Platzhalter für die spätere OAuth2/OIDC-Integration.
Aktuell gibt die Funktion einen Dummy-User zurück.
Später wird hier die echte Authentifizierung über Keycloak der FH-SWF implementiert.
"""

from typing import Dict


async def get_current_user() -> Dict[str, str]:
    """
    Auth-Platzhalter - gibt vorerst einen Dummy-User zurück.

    TODO: Echte OAuth2/OIDC Implementierung einfügen
    - Keycloak Integration der FH-SWF
    - Token Validierung
    - Rollen-Management (admin, editor, reader)

    Returns:
        Dict mit User-Informationen (sub, role, email)
    """
    # Dummy für Entwicklung - später durch echte Auth ersetzen
    return {
        "sub": "dev-user",
        "role": "admin",
        "email": "dev@fh-swf.de"
    }
