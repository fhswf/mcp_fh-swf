"""
Neo4j Repository für Prüfungsordnungen

Datenmodell:
- Pruefungsordnung → ENTHAELT → Modul
- Modul → HAT_ECTS → ECTS
- Modul → HAT_PRUEFUNGSFORM → Pruefungsform
- Modul → BETREUT_VON → Dozent
- Pruefungsordnung → ERSETZT → Pruefungsordnung (Versionierung)
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date as date_type
from neo4j import GraphDatabase
from neo4j.time import Date, DateTime

logger = logging.getLogger(__name__)


def convert_neo4j_types(data):
    """Konvertiert Neo4j-Typen (Date, DateTime) zu Python-Typen - rekursiv."""
    if isinstance(data, dict):
        return {key: convert_neo4j_types(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_neo4j_types(item) for item in data]
    elif isinstance(data, DateTime):
        return datetime(
            data.year,
            data.month,
            data.day,
            data.hour,
            data.minute,
            data.second,
            data.nanosecond // 1000,
            tzinfo=data.tzinfo,
        )
    elif isinstance(data, Date):
        return date_type(data.year, data.month, data.day)
    else:
        return data


class PORepository:
    """Repository für Prüfungsordnungs-CRUD-Operationen in Neo4j"""

    def __init__(self, driver):
        """
        Args:
            driver: Neo4j Driver Instanz (aus bestehender Verbindung)
        """
        self.driver = driver

    async def create_pruefungsordnung(
        self,
        po_id: str,
        studiengang: str,
        version: str,
        gueltig_ab: str,
        s3_key: str,
        status: str = "processing",
    ) -> Dict:
        """
        Erstellt einen neuen Prüfungsordnung-Node.

        Args:
            po_id: Eindeutige ID
            studiengang: Name des Studiengangs
            version: Version (z.B. WS2024)
            gueltig_ab: Gültigkeitsdatum (ISO-Format)
            s3_key: S3-Key der PDF-Datei
            status: Status (processing, ready, error)

        Returns:
            Dictionary mit PO-Daten
        """
        cypher = """
        MERGE (po:Pruefungsordnung {id: $po_id})
        SET po.studiengang = $studiengang,
            po.version = $version,
            po.gueltig_ab = date($gueltig_ab),
            po.s3_key = $s3_key,
            po.status = $status,
            po.created_at = datetime($created_at),
            po.updated_at = datetime($updated_at)
        RETURN po
        """
        now = datetime.utcnow().isoformat()

        with self.driver.session() as session:
            result = session.run(
                cypher,
                po_id=po_id,
                studiengang=studiengang,
                version=version,
                gueltig_ab=gueltig_ab,
                s3_key=s3_key,
                status=status,
                created_at=now,
                updated_at=now,
            )
            record = result.single()
            if record:
                return dict(record["po"])
            return {}

    async def update_po_status(self, po_id: str, status: str) -> bool:
        """
        Aktualisiert den Status einer Prüfungsordnung.

        Args:
            po_id: PO-ID
            status: Neuer Status (processing, ready, error)

        Returns:
            True bei Erfolg
        """
        cypher = """
        MATCH (po:Pruefungsordnung {id: $po_id})
        SET po.status = $status,
            po.updated_at = datetime($updated_at)
        RETURN po
        """
        with self.driver.session() as session:
            result = session.run(
                cypher, po_id=po_id, status=status, updated_at=datetime.utcnow().isoformat()
            )
            return result.single() is not None

    async def create_modul(
        self,
        po_id: str,
        modul_id: str,
        name: str,
        kuerzel: str,
        semester: int,
        pflicht_oder_wahl: str = "Pflicht",
    ) -> Dict:
        """
        Erstellt Modul-Node und verknüpft ihn mit der PO.

        Args:
            po_id: PO-ID
            modul_id: Eindeutige Modul-ID
            name: Modulname
            kuerzel: Modulkürzel
            semester: Semester-Nr
            pflicht_oder_wahl: "Pflicht" oder "Wahl"

        Returns:
            Dictionary mit Modul-Daten
        """
        cypher = """
        MATCH (po:Pruefungsordnung {id: $po_id})
        MERGE (m:Modul {id: $modul_id})
        SET m.name = $name,
            m.kuerzel = $kuerzel,
            m.semester = $semester,
            m.pflicht_oder_wahl = $pflicht_oder_wahl
        MERGE (po)-[:ENTHAELT]->(m)
        RETURN m
        """
        with self.driver.session() as session:
            result = session.run(
                cypher,
                po_id=po_id,
                modul_id=modul_id,
                name=name,
                kuerzel=kuerzel,
                semester=semester,
                pflicht_oder_wahl=pflicht_oder_wahl,
            )
            record = result.single()
            if record:
                return dict(record["m"])
            return {}

    async def create_ects(self, modul_id: str, punkte: float, workload_h: int) -> Dict:
        """
        Erstellt ECTS-Node und verknüpft ihn mit Modul.

        Args:
            modul_id: Modul-ID
            punkte: ECTS-Punkte
            workload_h: Workload in Stunden

        Returns:
            Dictionary mit ECTS-Daten
        """
        cypher = """
        MATCH (m:Modul {id: $modul_id})
        MERGE (e:ECTS {modul_id: $modul_id})
        SET e.punkte = $punkte,
            e.workload_h = $workload_h
        MERGE (m)-[:HAT_ECTS]->(e)
        RETURN e
        """
        with self.driver.session() as session:
            result = session.run(
                cypher, modul_id=modul_id, punkte=punkte, workload_h=workload_h
            )
            record = result.single()
            if record:
                return dict(record["e"])
            return {}

    async def create_pruefungsform(
        self, modul_id: str, typ: str, dauer_min: Optional[int] = None, gewichtung: Optional[float] = None
    ) -> Dict:
        """
        Erstellt Prüfungsform-Node und verknüpft ihn mit Modul.

        Args:
            modul_id: Modul-ID
            typ: Prüfungsform (z.B. Klausur, Hausarbeit)
            dauer_min: Dauer in Minuten (optional)
            gewichtung: Gewichtung in % (optional)

        Returns:
            Dictionary mit Prüfungsform-Daten
        """
        cypher = """
        MATCH (m:Modul {id: $modul_id})
        MERGE (pf:Pruefungsform {modul_id: $modul_id, typ: $typ})
        SET pf.dauer_min = $dauer_min,
            pf.gewichtung = $gewichtung
        MERGE (m)-[:HAT_PRUEFUNGSFORM]->(pf)
        RETURN pf
        """
        with self.driver.session() as session:
            result = session.run(
                cypher,
                modul_id=modul_id,
                typ=typ,
                dauer_min=dauer_min,
                gewichtung=gewichtung,
            )
            record = result.single()
            if record:
                return dict(record["pf"])
            return {}

    async def create_dozent(
        self, name: str, email: Optional[str] = None, fachbereich: Optional[str] = None
    ) -> Dict:
        """
        Erstellt Dozenten-Node (idempotent).

        Args:
            name: Name des Dozenten
            email: E-Mail (optional)
            fachbereich: Fachbereich (optional)

        Returns:
            Dictionary mit Dozenten-Daten
        """
        cypher = """
        MERGE (d:Dozent {name: $name})
        SET d.email = $email,
            d.fachbereich = $fachbereich
        RETURN d
        """
        with self.driver.session() as session:
            result = session.run(
                cypher, name=name, email=email, fachbereich=fachbereich
            )
            record = result.single()
            if record:
                return dict(record["d"])
            return {}

    async def link_modul_to_dozent(self, modul_id: str, dozent_name: str) -> bool:
        """
        Verknüpft Modul mit Dozent.

        Args:
            modul_id: Modul-ID
            dozent_name: Name des Dozenten

        Returns:
            True bei Erfolg
        """
        cypher = """
        MATCH (m:Modul {id: $modul_id})
        MATCH (d:Dozent {name: $dozent_name})
        MERGE (m)-[:BETREUT_VON]->(d)
        RETURN m, d
        """
        with self.driver.session() as session:
            result = session.run(cypher, modul_id=modul_id, dozent_name=dozent_name)
            return result.single() is not None

    async def get_all_pos(self) -> List[Dict]:
        """
        Gibt alle Prüfungsordnungen zurück.

        Returns:
            Liste von PO-Dictionaries
        """
        cypher = """
        MATCH (po:Pruefungsordnung)
        RETURN po
        ORDER BY po.created_at DESC
        """
        with self.driver.session() as session:
            results = session.run(cypher)
            return [convert_neo4j_types(dict(record["po"])) for record in results]

    async def get_po_by_id(self, po_id: str) -> Optional[Dict]:
        """
        Gibt eine PO mit allen Modulen zurück.

        Args:
            po_id: PO-ID

        Returns:
            Dictionary mit PO und Modulen oder None
        """
        cypher = """
        MATCH (po:Pruefungsordnung {id: $po_id})
        OPTIONAL MATCH (po)-[:ENTHAELT]->(m:Modul)
        OPTIONAL MATCH (m)-[:HAT_ECTS]->(e:ECTS)
        OPTIONAL MATCH (m)-[:HAT_PRUEFUNGSFORM]->(pf:Pruefungsform)
        OPTIONAL MATCH (m)-[:BETREUT_VON]->(d:Dozent)
        RETURN po,
               collect(DISTINCT {
                   id: m.id,
                   name: m.name,
                   kuerzel: m.kuerzel,
                   semester: m.semester,
                   pflicht_oder_wahl: m.pflicht_oder_wahl,
                   ects: e.punkte,
                   workload_h: e.workload_h,
                   pruefungsform: pf.typ,
                   dauer_min: pf.dauer_min,
                   dozent: d.name
               }) AS module
        """
        with self.driver.session() as session:
            result = session.run(cypher, po_id=po_id)
            record = result.single()
            if record:
                po_data = dict(record["po"])
                po_data["module"] = [m for m in record["module"] if m.get("id")]
                return convert_neo4j_types(po_data)
            return None

    async def get_modules_by_po(self, po_id: str, semester: Optional[int] = None) -> List[Dict]:
        """
        Gibt alle Module einer PO zurück, optional nach Semester gefiltert.

        Args:
            po_id: PO-ID
            semester: Semester-Filter (optional)

        Returns:
            Liste von Modul-Dictionaries
        """
        if semester:
            cypher = """
            MATCH (po:Pruefungsordnung {id: $po_id})-[:ENTHAELT]->(m:Modul {semester: $semester})
            OPTIONAL MATCH (m)-[:HAT_ECTS]->(e:ECTS)
            OPTIONAL MATCH (m)-[:HAT_PRUEFUNGSFORM]->(pf:Pruefungsform)
            OPTIONAL MATCH (m)-[:BETREUT_VON]->(d:Dozent)
            RETURN m, e, pf, d
            ORDER BY m.semester, m.name
            """
            params = {"po_id": po_id, "semester": semester}
        else:
            cypher = """
            MATCH (po:Pruefungsordnung {id: $po_id})-[:ENTHAELT]->(m:Modul)
            OPTIONAL MATCH (m)-[:HAT_ECTS]->(e:ECTS)
            OPTIONAL MATCH (m)-[:HAT_PRUEFUNGSFORM]->(pf:Pruefungsform)
            OPTIONAL MATCH (m)-[:BETREUT_VON]->(d:Dozent)
            RETURN m, e, pf, d
            ORDER BY m.semester, m.name
            """
            params = {"po_id": po_id}

        with self.driver.session() as session:
            results = session.run(cypher, **params)
            modules = []
            for record in results:
                modul = dict(record["m"])
                if record["e"]:
                    modul["ects"] = record["e"]["punkte"]
                    modul["workload_h"] = record["e"]["workload_h"]
                if record["pf"]:
                    modul["pruefungsform"] = record["pf"]["typ"]
                    modul["dauer_min"] = record["pf"].get("dauer_min")
                if record["d"]:
                    modul["dozent"] = record["d"]["name"]
                modules.append(modul)
            return modules

    async def search_modules(self, suchbegriff: str) -> List[Dict]:
        """
        Sucht Module über alle POs hinweg.

        Args:
            suchbegriff: Suchbegriff (Name oder Kürzel)

        Returns:
            Liste von Modul-Dictionaries mit PO-Info
        """
        cypher = """
        MATCH (po:Pruefungsordnung)-[:ENTHAELT]->(m:Modul)
        WHERE toLower(m.name) CONTAINS toLower($suchbegriff)
           OR toLower(m.kuerzel) CONTAINS toLower($suchbegriff)
        OPTIONAL MATCH (m)-[:HAT_ECTS]->(e:ECTS)
        OPTIONAL MATCH (m)-[:BETREUT_VON]->(d:Dozent)
        RETURN m, po.studiengang AS studiengang, po.version AS version, e, d
        ORDER BY po.studiengang, m.name
        LIMIT 50
        """
        with self.driver.session() as session:
            results = session.run(cypher, suchbegriff=suchbegriff)
            modules = []
            for record in results:
                modul = dict(record["m"])
                modul["studiengang"] = record["studiengang"]
                modul["version"] = record["version"]
                if record["e"]:
                    modul["ects"] = record["e"]["punkte"]
                if record["d"]:
                    modul["dozent"] = record["d"]["name"]
                modules.append(modul)
            return modules

    async def delete_po(self, po_id: str) -> bool:
        """
        Löscht eine PO und alle zugehörigen Nodes und Relationen.

        Args:
            po_id: PO-ID

        Returns:
            True bei Erfolg
        """
        cypher = """
        MATCH (po:Pruefungsordnung {id: $po_id})
        OPTIONAL MATCH (po)-[:ENTHAELT]->(m:Modul)
        OPTIONAL MATCH (m)-[:HAT_ECTS]->(e:ECTS)
        OPTIONAL MATCH (m)-[:HAT_PRUEFUNGSFORM]->(pf:Pruefungsform)
        DETACH DELETE po, m, e, pf
        """
        with self.driver.session() as session:
            session.run(cypher, po_id=po_id)
            logger.info(f"PO {po_id} aus Neo4j gelöscht")
            return True

    async def update_po_metadata(
        self, po_id: str, studiengang: Optional[str] = None, version: Optional[str] = None
    ) -> bool:
        """
        Aktualisiert PO-Metadaten.

        Args:
            po_id: PO-ID
            studiengang: Neuer Studiengangsname (optional)
            version: Neue Version (optional)

        Returns:
            True bei Erfolg
        """
        updates = []
        params = {"po_id": po_id, "updated_at": datetime.utcnow().isoformat()}

        if studiengang:
            updates.append("po.studiengang = $studiengang")
            params["studiengang"] = studiengang

        if version:
            updates.append("po.version = $version")
            params["version"] = version

        if not updates:
            return False

        updates.append("po.updated_at = datetime($updated_at)")
        cypher = f"""
        MATCH (po:Pruefungsordnung {{id: $po_id}})
        SET {', '.join(updates)}
        RETURN po
        """

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return result.single() is not None
