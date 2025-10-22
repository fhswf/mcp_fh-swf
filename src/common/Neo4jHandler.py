from neo4j import GraphDatabase
import pandas as pd
import math
from src.common.neo4j_help_function import normalize_name

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_document_node(self, tx, doc_title):
        tx.run(
            """
            MERGE (d:Document {title: $doc_title})
            """,
            doc_title=doc_title
        )

    def create_segment_node(self, tx, title, content, embedding):
        tx.run(
            """
            MERGE (s:Segment {title: $title})
            SET s.content = $content, s.embedding = $embedding
            """,
            title=title,
            content=content,
            embedding=embedding
        )


    def link_segment_to_document(self, tx, doc_title, seg_title):
        tx.run(
            """
            MATCH (d:Document {title: $doc_title})
            MATCH (s:Segment {title: $seg_title})
            MERGE (d)-[:HAS_SEGMENT]->(s)
            """,
            doc_title=doc_title,
            seg_title=seg_title
        )
    
    # Studiengang erstellen
    def create_study_program_node(self, tx, program_name):
        tx.run(
            """
            MERGE (sp:StudyProgram {name: $program_name})
            """,
            program_name=program_name
        )
    
    # Fachbereich erstellen
    def create_department_node(self, tx, department_name):
        tx.run(
            """
            MERGE (d:Department {name: $department_name})
            """,
            department_name=department_name
        )

    # Einem Fachbereich einen Studiengang hinzufuegen
    def link_study_program_to_department(self, tx, program_name, department_name):
        tx.run(
            """
            MATCH (sp:StudyProgram {name: $program_name})
            MATCH (d:Department {name: $department_name})
            MERGE (d)-[:OFFERS]->(sp)
            """,
            program_name=program_name,
            department_name=department_name
        )
    
    # Dokument einem Studiengang zuordnen
    def link_document_to_study_program(self, tx, doc_title, program_name):
        tx.run(
            """
            MATCH (d:Document {title: $doc_title})
            MATCH (sp:StudyProgram {name: $program_name})
            MERGE (d)-[:RELATED_TO]->(sp)
            """,
            doc_title=doc_title,
            program_name=program_name
        )
    
    # Standort erstellen
    def create_location_node(self, tx, location_name):
        tx.run(
            """
            MERGE (loc:Location {name: $location_name})
            """,
            location_name=location_name
        )

    # Standort mit einem Fachbereich erweitern
    def link_location_to_department(self, tx, location_name, department_name):
        tx.run(
            """
            MATCH (loc:Location {name: $location_name})
            MATCH (d:Department {name: $department_name})
            MERGE (loc)-[:HOSTS]->(d)
            """,
            location_name=location_name,
            department_name=department_name
        )

    # Person erstellen und einem Standort zuordnen
    def create_person(self, tx, person_data):
        tx.run(
            """
            MERGE (loc:Location {name: $location})
            MERGE (p:Person {name: $name})
            SET p.phone = $phone,
                p.email = $email,
                p.homepage = $homepage,
                p.address = $address
            MERGE (p)-[:LOCATED_AT]->(loc)
            """,
            name=person_data['Name'],
            phone=person_data['Telefon'],
            email=person_data['E-Mail'],
            homepage=person_data['Homepage'],
            address=person_data['Adresse'],
            location=person_data['Standort']
        )

    # Alle Daten loeschen
    def delete_all_data(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def save_segments(self, segments, doc_title):
        with self.driver.session() as session:
            session.execute_write(self.create_document_node, doc_title)

            for seg in segments:
                session.execute_write(
                    self.create_segment_node,
                    seg['title'],
                    seg['content'],
                    seg['embedding']
                )

                # Segment mit Dokumentknoten verknuepfen
                session.execute_write(
                    self.link_segment_to_document,
                    doc_title,
                    seg['title']
                )

    # Standorte mit jeweiligen Studiengaengen speichern
    def save_locations(self, locations):
        with self.driver.session() as session:
            for location, department in locations.items():
                session.execute_write(self.create_location_node, location)
                for depart in department:
                    session.execute_write(self.create_department_node, depart)
                    session.execute_write(self.link_location_to_department, location, depart)
            
    # Module der Studiengaenge speichern
    def save_study_programs(self, study_programs):
        with self.driver.session() as session:
            for department, study_program in study_programs.items():
                for program in study_program:
                    session.execute_write(self.create_study_program_node, program)
                    session.execute_write(self.link_study_program_to_department, program, department)

    def update_studyprogram_info(self, info_dict):
        """
        Aktualisiert fuer jeden Studiengang in info_dict die Properties text, location und link.
        
        """
        cypher = """
        MATCH (sp:StudyProgram {name: $study_program_name})
        SET sp.text = $text,
            sp.location = $location,
            sp.link = $link
        """
        with self.driver.session() as session:
            for study_program_name, data in info_dict.items():
                session.run(
                    cypher,
                    study_program_name=study_program_name,
                    text=data.get("text"),
                    location=data.get("location"),
                    link=data.get("link")
                )

    # Dokumentknoten fuer Studiengang erstellen und speichern
    def save_document_node_for_study_program(self, study_programs):
        with self.driver.session() as session:
            for _, study_program in study_programs.items():
                for program in study_program:
                    doc_title = "Pr�fungsordnung " + program
                    doc_title_modul = "Modulhandbuch " + program
                    session.execute_write(self.create_document_node, doc_title)
                    session.execute_write(self.create_document_node, doc_title_modul)
                    session.execute_write(self.link_document_to_study_program, 
                                        doc_title, 
                                        program)
                    session.execute_write(self.link_document_to_study_program, 
                                        doc_title_modul, 
                                        program)
                    
    # Personen aus einer CSV-Datei laden und speichern              
    def import_persons_from_csv(self, csv_file_path):
        df = pd.read_csv(csv_file_path)
        with self.driver.session() as session:
            for _, person_data in df.iterrows():
                location = person_data['Standort']
                
                # Falls location kein String ist ueberspringen
                if isinstance(location, float) and math.isnan(location):
                    continue  
                session.execute_write(self.create_person, person_data)

    # Modulknoten erstellen 
    def create_module_node(self, tx, module_name, properties=None):
        properties = properties or {}
        cypher = """
        MERGE (m:Modul {name: $module_name})
        SET m += $properties
        """
        tx.run(cypher, module_name=module_name, properties=properties)

    # Modul erstellen und Lehrperson mit diesem verbinden, Modul mit Modulhandbuch verbinden
    def save_modules_for_handbook(self, study_program, moduls):
        """
        
        """
        doc_title_modul = "Modulhandbuch " + study_program
        with self.driver.session() as session:
            for modul_name, properties in moduls.items():
                
                lecturers = properties.get('Modulbeauftragte*r und hauptamtlich Lehrende', "").replace("/", ",").split(",")
                # Modul erstellen
                modul_name = doc_title_modul + ": " + modul_name
                session.execute_write(self.create_module_node, modul_name, properties)
                # Modul mit Modulhandbuch verbinden
                session.execute_write(self.link_module_to_handbook, doc_title_modul, modul_name)
                if lecturers != [''] and lecturers != ['-']:
                    # Lehrpersonen mit Modul verbinden
                    session.execute_write(self.link_module_to_persons, modul_name, lecturers)

    # Modulhandbuch mit den jeweiligen Modulen erweitern
    def link_module_to_handbook(self, tx, handbook_title, module_name):
        tx.run(
            """
            MATCH (mh:Document {title: $handbook_title})
            MATCH (m:Modul {name: $module_name})
            MERGE (mh)-[:CONTAINS_MODULE]->(m)
            """,
            handbook_title=handbook_title,
            module_name=module_name
        )

    # Module mit jeweiliger Lehrperson verbinden
    def link_module_to_persons(self, tx, module_name, lecturer_names):
        for raw_name in lecturer_names:
            clean_name = normalize_name(raw_name)

            cypher_find = """
            MATCH (p:Person)
            WHERE toLower(p.name) CONTAINS toLower($clean_name)
            RETURN p LIMIT 1
            """
            result = tx.run(cypher_find, clean_name=clean_name)
            record = result.single()

            # Person wurde gefunden
            if record:
                person_node = record["p"]
                # Modul mit Person verbinden
                cypher_link = """
                MATCH (m:Modul {name: $module_name})
                MATCH (p:Person {name: $person_name})
                MERGE (m)-[:HAS_LECTURER]->(p)
                """
                tx.run(cypher_link, module_name=module_name, person_name=person_node["name"])
            else:
                # Person neu anlegen
                cypher_create = """
                MERGE (p:Person {name: $person_name})
                """
                tx.run(cypher_create, person_name=raw_name)

                # neu angelegte Person mit Modul verbinden
                cypher_link_new = """
                MATCH (m:Modul {name: $module_name})
                MATCH (p:Person {name: $person_name})
                MERGE (m)-[:HAS_LECTURER]->(p)
                """
                tx.run(cypher_link_new, module_name=module_name, person_name=raw_name)
            

    def create_vector_index(self, label="Segment", property="embedding", index_name="textsegment_embedding", dimensions=384, similarity_function="cosine"):
        """
        Legt einen Vektorindex auf dem angegebenen Label und Property an.
        """
        cypher = f"""
        CREATE VECTOR INDEX {index_name}
        FOR (n:{label}) ON (n.{property})
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {dimensions},
                `vector.similarity_function`: '{similarity_function}'
            }}
        }}
        """
        with self.driver.session() as session:
            session.run(cypher)
    
    def vector_similarity_search(self, query_vector, index_name="textsegment_embedding", top_k=10):
        """
        Führt eine Vektor-Ähnlichkeitssuche durch und gibt die ähnlichsten Knoten zuruck.
        """
        if query_vector is None or not isinstance(query_vector, list):
            raise ValueError("query_vector muss eine nicht-leere Liste von Zahlen sein.")

        # Ähnlichkeitssuche über den Vektorindex
        cypher = f"""
        CALL db.index.vector.queryNodes('{index_name}', {top_k}, $query_vector)
        YIELD node, score
        RETURN node, score
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            results = session.run(cypher, query_vector=query_vector)
            return [(record["node"], record["score"]) for record in results]
        
        
    def hybrid_enhanced_search(self, query_vector, top_k=10):
        # Ähnlichkeitssuche über den Vektorindex
        # Ermittlung der benachbarten Knoten
        # Ähnlichkeitssuche über die benachbarten Knoten
        # Ermittlung des zugehörigen Studiengangs
        cypher = """
        CALL db.index.vector.queryNodes('textsegment_embedding', $top_k, $query_vector) YIELD node AS segment, score AS segment_score
        MATCH (document)-[:HAS_SEGMENT]->(segment)
        MATCH (document)-[:HAS_SEGMENT]->(otherSegment)
        WHERE otherSegment <> segment
        WITH segment, segment_score, document, otherSegment,
            vector.similarity.cosine($query_vector, otherSegment.embedding) AS otherSegmentScore
        ORDER BY otherSegmentScore DESC
        WITH segment, segment_score, document,
            collect({title: otherSegment.title, text: otherSegment.content, score: otherSegmentScore})[0..10] AS topOtherSegments
        OPTIONAL MATCH (document)-[:RELATED_TO]->(studyProgram)
        RETURN segment.title AS segment_title,
            segment.content AS segment_text,
            segment_score,
            topOtherSegments,
            document.title AS document_title,
            studyProgram.name AS study_program
        ORDER BY segment_score DESC
        LIMIT $top_k
        """
        with self.driver.session() as session:
            results = session.run(cypher, query_vector=query_vector, top_k=top_k)
            return [record.data() for record in results]
    
    # Informationen zu einem Studiengang suchen, anhand dem Namen und Standort
    def find_studyprogram_segments_similarity(self, study_program_name, location_name, query_vector, top_k=5):
        cypher = """
        MATCH (loc:Location {name: $location_name})-[:HOSTS]->(dep:Department)
        MATCH (dep)-[:OFFERS]->(sp:StudyProgram {name: $study_program_name})
        MATCH (doc:Document)-[:RELATED_TO]->(sp)
        WHERE doc.title CONTAINS 'Pr�fungsordnung'

        MATCH (doc)-[:HAS_SEGMENT]->(segment)
        WITH segment, vector.similarity.cosine($query_vector, segment.embedding) AS similarity, doc, sp, loc, dep
        RETURN sp.name AS study_program,
            loc.name AS location,
            dep.name AS department,
            doc.title AS document_title,
            segment.title AS segment_title,
            segment.content AS segment_text,
            similarity
        ORDER BY similarity DESC
        LIMIT $top_k
        """
        with self.driver.session() as session:
            results = session.run(
                cypher,
                study_program_name=study_program_name,
                location_name=location_name,
                query_vector=query_vector,
                top_k=top_k
            )
            return [record.data() for record in results]
    
    # Rahmenprüfungsordnung zu einer Anfrage suchen 
    def find_rpo_segments_similarity(self, query_vector, top_k=5):
        cypher = """
        MATCH (doc:Document {title: "Rahmenpr�fungsordnung"})-[:HAS_SEGMENT]->(segment)
        WITH segment, vector.similarity.cosine($query_vector, segment.embedding) AS similarity, doc
        RETURN doc.title AS document_title,
            segment.title AS segment_title,
            segment.content AS segment_text,
            similarity
        ORDER BY similarity DESC
        LIMIT $top_k
        """
        with self.driver.session() as session:
            results = session.run(
                cypher,
                query_vector=query_vector,
                top_k=top_k
            )
            return [record.data() for record in results]
    
    # Suchen aller Fachbereiche an einem Standort
    def find_departments_by_location(self, location_name):
        cypher = """
        MATCH (loc:Location {name: $location_name})-[:HOSTS]->(dep:Department)
        RETURN dep.name AS department_name
        ORDER BY dep.name
        """
        with self.driver.session() as session:
            results = session.run(cypher, location_name=location_name)
            return [record["department_name"] for record in results]
    
    # Suchen aller Studiengaenge anhand eines Fachbereichs
    def find_studyprograms_by_department(self, department_name):
        cypher = """
        MATCH (dep:Department {name: $department_name})-[:OFFERS]->(sp:StudyProgram)
        RETURN sp.name AS study_program_name
        ORDER BY sp.name
        """
        with self.driver.session() as session:
            results = session.run(cypher, department_name=department_name)
            return [record["study_program_name"] for record in results]
    
    # Suchen eines Standorts anhand des Studienganges
    def find_location_by_studyprogram(self, study_program_name):
        cypher = """
        MATCH (loc:Location)-[:HOSTS]->(dep:Department)-[:OFFERS]->(sp:StudyProgram {name: $study_program_name})
        RETURN loc.name AS location_name
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(cypher, study_program_name=study_program_name).single()
            if result:
                return result["location_name"]
            else:
                return None

    # Suchen nach Knoten anhand des labels
    def find_all_node_names_by_label(self, label):
        cypher = f"""
        MATCH (n:{label})
        RETURN n.name AS name
        ORDER BY name
        """
        with self.driver.session() as session:
            results = session.run(cypher)
            return [record["name"] for record in results]

    # Alle Standorte im Graph ausgeben
    def find_all_locations(self):
        return self.find_all_node_names_by_label("Location")

    # Alle Fachbereiche im Graph ausgeben
    def find_all_departments(self):
        return self.find_all_node_names_by_label("Department")

    # Alle Studiengaenge im Graph ausgeben
    def find_all_studyprograms(self):
        return self.find_all_node_names_by_label("StudyProgram")
    
    # Alle Personen im Graph ausgeben
    def find_all_persons(self):
        return self.find_all_node_names_by_label("Person")
    
    # Informationen zu einem Modul in einem Studiengang suchen
    def find_modul_info_by_studyprogram(self, study_program_name, modul_name):

        doc_title_modul = "Modulhandbuch " + study_program_name
        modul_name = doc_title_modul + ": " + modul_name

        cypher = """
        MATCH (sp:StudyProgram {name: $study_program_name})
        MATCH (doc:Document)-[:RELATED_TO]->(sp)
        WHERE doc.title CONTAINS 'Modulhandbuch'
        MATCH (doc)-[:CONTAINS_MODULE]->(modul:Modul {name: $modul_name})
        RETURN modul
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(
                cypher, 
                study_program_name=study_program_name,
                modul_name=modul_name
            ).single()
            if result:
                return result.data()
            else:
                return None
    
    # Alle Module eines Studiengangs suchen
    def find_all_modules_by_studyprogram(self, study_program_name):
        cypher = """
        MATCH (sp:StudyProgram {name: $study_program_name})
        MATCH (doc:Document)-[:RELATED_TO]->(sp)
        WHERE doc.title CONTAINS 'Modulhandbuch'
        MATCH (doc)-[:CONTAINS_MODULE]->(modul:Modul)
        WITH modul, split(modul.name, ":") AS parts
        WITH modul, trim(parts[1]) AS modul_name_clean
        RETURN modul_name_clean AS modul_name
        ORDER BY modul_name_clean
        """
        with self.driver.session() as session:
            results = session.run(cypher, study_program_name=study_program_name)
            return [record.data()['modul_name'] for record in results]
        
    # Person anhand des Namens suchen    
    def find_person_by_name(self, person_name):
        cypher = """
        MATCH (p:Person {name: $person_name})
        RETURN p
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(cypher, person_name=person_name).single()
            if result:
                return dict(result["p"])
            else:
                return None
    
    # Module suchen, in denen eine Person als Lehrperson eingetragen ist
    def find_modules_and_studyprograms_by_person(self, person_name):
        cypher = """
        MATCH (modul:Modul)-[:HAS_LECTURER]->(p:Person {name: $person_name})
        MATCH (doc:Document)-[:CONTAINS_MODULE]->(modul)
        MATCH (doc)-[:RELATED_TO]->(sp:StudyProgram)
        RETURN modul.name AS modul_name, sp.name AS study_program
        ORDER BY modul_name
        """
        with self.driver.session() as session:
            results = session.run(cypher, person_name=person_name)
            return [record.data() for record in results]

    # Informationen zu einem Studiengang anhand des Namens suchen
    def get_studyprogram_info(self, study_program_name):
        cypher = """
        MATCH (sp:StudyProgram {name: $study_program_name})
        RETURN sp
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(cypher, study_program_name=study_program_name).single()
            if result:
                return dict(result["sp"])
            else:
                return None


