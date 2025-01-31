import sqlite3
import chromadb
import uuid
import json

import chromadb.utils.embedding_functions.ollama_embedding_function as ollama_ef
from langchain_core.documents import Document

def initDatabases():
    ''' Initialize the SQLite db for storing metadata and papers '''
    conn = sqlite3.connect("data/metadata.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS metadata
                 (id TEXT PRIMARY KEY,
                  title TEXT,
                  summary TEXT,
                  authors TEXT,
                  link TEXT,
                  datasets TEXT,
                  metrics TEXT,
                  methods TEXT,
                  applications TEXT,
                  limitations TEXT,
                  areasOfImprovement TEXT)''')
    conn.commit()
    conn.close()

ollamaEF = ollama_ef.OllamaEmbeddingFunction( # Custom embedding function that uses Ollama
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text:latest",
)
chromaClient = chromadb.PersistentClient("./data/chroma")
collection = chromaClient.get_or_create_collection("papers", embedding_function=ollamaEF)

def storePaper(metadata: dict, documents: list[Document]):
    ''' Stores the metadata in the SQLite and embeds documents (chunked parts of a paper) into ChromaDB '''
    paperId = str(uuid.uuid4())
    
    # SQLite to store the metadata of paper
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute('''INSERT INTO metadata VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
        paperId,
        metadata.get('title', ''),
        metadata.get('summary', ''),
        json.dumps(metadata.get('authors', [])),
        metadata.get('link', ''),
        json.dumps(metadata.get('datasets', {})),
        json.dumps(metadata.get('metrics', {})),
        json.dumps(metadata.get('methods', {})),
        json.dumps(metadata.get('applications', [])),
        json.dumps(metadata.get('limitations', [])),
        json.dumps(metadata.get('areasOfImprovement', []))
    ))
    conn.commit()
    conn.close()
    
    # ChromaDB to store the embeddings of the paper text
    documentMetadata = [doc.metadata for doc in documents]
    for i in range(len(documentMetadata)):
        documentMetadata[i]['paperId'] = paperId # Add the paper ID to the metadata

    collection.add(
        ids=[f"{paperId}_{i}" for i in range(len(documents))],
        documents=[doc.page_content for doc in documents], # These docs will be embedded with the Embedding Function specified in the collection
        metadatas=documentMetadata,
    )

def semanticSearch(query: str, nResults: int = 5) -> list[str]:
    ''' Searches for papers similar to the given query and returns their IDs '''
    try:
        results = collection.query(
            query_texts=query,
            n_results=nResults
        )
        return [metad['paperId'] for metad in results['metadatas'][0]]
    except Exception as e:
        raise Exception(f"Search failed: {str(e)}")

def getPapersByIds(paperIds: list[str]) -> list[dict]:
    ''' Gets the papers with the given IDs from the SQLite database '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    placeholders = ','.join(['?']*len(paperIds))
    c.execute(f"SELECT * FROM metadata WHERE id IN ({placeholders})", paperIds)

    papers = []
    for row in c.fetchall():
        papers.append({
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "authors": json.loads(row[3]),
            "link": row[4],
            "datasets": json.loads(row[5]),
            "metrics": json.loads(row[6]),
            "methods": json.loads(row[7]),
            "applications": json.loads(row[8]),
            "limitations": json.loads(row[9]),
            "areasOfImprovement": json.loads(row[10])
        })
    return papers

def getAllPapers() -> list[dict]:
    ''' Gets all papers stored in the SQLite database '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute("SELECT * FROM metadata")

    papers = []
    for row in c.fetchall():
        papers.append({
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "authors": json.loads(row[3]),
            "link": row[4],
            "datasets": json.loads(row[5]),
            "metrics": json.loads(row[6]),
            "methods": json.loads(row[7]),
            "applications": json.loads(row[8]),
            "limitations": json.loads(row[9]),
            "areasOfImprovement": json.loads(row[10])
        })
    return papers

def removePaper(paperId: str):
    ''' Removes a given paper from the SQLite and ChromaDB databases '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute("DELETE FROM metadata WHERE id=?", (paperId,))
    conn.commit()
    conn.close()

    collection.delete(where={"paperId": paperId}) # Remove all documents associated with the paper

def removeAllPapers():
    ''' Removes all papers from the SQLite and ChromaDB databases '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute("DELETE FROM metadata")
    conn.commit()
    conn.close()

    chromaClient.delete_collection("papers") # Remove the entire collection
    chromaClient.get_or_create_collection("papers", embedding_function=ollamaEF) # Recreate the collection

def updatePaper(paperId: str, metadata: dict):
    ''' Updates the metadata of specfic paper in the SQLite database '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute('''UPDATE metadata SET title=?, summary=?, authors=?, link=?, datasets=?, metrics=?, methods=?, applications=?, limitations=?, areasOfImprovement=? WHERE id=?''', (
        metadata.get('title', ''),
        metadata.get('summary', ''),
        json.dumps(metadata.get('authors', [])),
        metadata.get('link', ''),
        json.dumps(metadata.get('datasets', {})),
        json.dumps(metadata.get('metrics', {})),
        json.dumps(metadata.get('methods', {})),
        json.dumps(metadata.get('applications', [])),
        json.dumps(metadata.get('limitations', [])),
        json.dumps(metadata.get('areasOfImprovement', [])),
        paperId
    ))
    conn.commit()
    conn.close()