import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import fitz 
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
import re



splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", "!", "?"]
)




PDF_FOLDER = "C:\\aaUniMaster\\Semester5\\Projekt\\Umsetzung\\pruefungsordnungen"

files = os.listdir(PDF_FOLDER + '/')
paths = [PDF_FOLDER + '\\' + f for f in files if f.lower().endswith(".pdf")]


content = []

#print(content[0])

# Lokaler, persistenter Client
client = chromadb.PersistentClient(path="chroma_db")
#client = chromadb.EphemeralClient()

# Embedding-Funktion definieren (Modell all-MiniLM-L6-v2)
embedder = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Collection mit eingebauter Embedding-Funktion erzeugen
collection = client.get_or_create_collection(
    name="pruefungsordnungen",
    embedding_function=embedder
)

def doc_to_db():
    for i, path in enumerate(paths):
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        text = re.sub(r'\n\s*\n+', '\n', text)
        chunks = splitter.split_text(text)
        for j, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                ids=["doc" + str(i) + "_" + str(j)]
            )


doc_to_db()

# Dokumente hinzufügen - Embeddings werden automatisch erstellt
#collection.add(
#    documents=[content[0], content[1], content[2]],
#    ids=["doc1", "doc2", "doc3"]
#)


# Suche mit Textquery - Chroma macht intern Embedding der Query
results = collection.query(
    query_texts=["Informatik", "Machine Learning"],
    n_results=1
)

print(results)
