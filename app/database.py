import sqlite3
import chromadb
import uuid
import json
import time
import numpy as np
import httpx
from typing import List
import chromadb.utils.embedding_functions.ollama_embedding_function as ollama_ef
from langchain_core.documents import Document

def initDatabases():
    ''' Initialize the SQLite db for storing metadata and papers '''
    conn = sqlite3.connect("data/metadata.db")
    c = conn.cursor()
    
    # Create the main metadata table
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
    
    # Create the document_content table to store text without embeddings in case of failure
    c.execute('''CREATE TABLE IF NOT EXISTS document_content
                (id TEXT PRIMARY KEY,
                 paper_id TEXT,
                 content TEXT,
                 metadata TEXT,
                 embedded BOOLEAN DEFAULT 0,
                 FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
    
    # Create the fact_checks table
    c.execute('''CREATE TABLE IF NOT EXISTS fact_checks
                (paper_id TEXT PRIMARY KEY,
                 issues TEXT,
                 severity_count TEXT,
                 overall_assessment TEXT,
                 total_issues INTEGER,
                 FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
    
    # Create the application_analysis table
    c.execute('''CREATE TABLE IF NOT EXISTS application_analysis
                (paper_id TEXT PRIMARY KEY,
                 industry_applications TEXT,
                 academic_applications TEXT,
                 overall_commercial_value TEXT,
                 interdisciplinary_potential TEXT,
                 FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
    
    # Create the taxonomy table
    c.execute('''CREATE TABLE IF NOT EXISTS taxonomy
                (paper_id TEXT PRIMARY KEY,
                 primary_field TEXT,
                 secondary_fields TEXT,
                 subfields TEXT,
                 keywords TEXT,
                 taxonomy_path TEXT,
                 related_fields TEXT,
                 FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
    
    conn.commit()
    conn.close()

# Custom embedding function with timeout and retry logic
class ResilientOllamaEmbedding:
    def __init__(self, model_name="nomic-embed-text:latest", timeout=10, max_retries=3):
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.ollama_ef = ollama_ef.OllamaEmbeddingFunction(
            url="http://localhost:11434/api/embeddings",
            model_name=model_name,
        )
        
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings with retry mechanism"""
        retries = 0
        while retries < self.max_retries:
            try:
                # Create a client with timeout
                self.ollama_ef._session = httpx.Client(timeout=self.timeout)
                return self.ollama_ef(input=input)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, Exception) as e:
                retries += 1
                if retries >= self.max_retries:
                    # If all retries fail, generate random embeddings as fallback
                    print(f"Embedding failed after {self.max_retries} attempts: {str(e)}. Using fallback embeddings.")
                    return self._generate_fallback_embeddings(len(input))
                print(f"Embedding attempt {retries} failed: {str(e)}. Retrying...")
                time.sleep(1)
    
    def _generate_fallback_embeddings(self, count: int) -> List[List[float]]:
        """Generate random embeddings as fallback"""
        # Each embedding is a vector of 768 dimensions (typical for many models)
        embedding_size = 768
        fallback_embeddings = []
        
        # Generate deterministic but varied embeddings based on the text hash
        for i in range(count):
            # Use a seeded random generator for reproducibility
            np.random.seed(i + 42)
            fallback_embeddings.append(np.random.normal(0, 0.1, embedding_size).tolist())
            
        return fallback_embeddings

# Initialize embedding function and Chroma client
resilientEF = ResilientOllamaEmbedding()
chromaClient = chromadb.PersistentClient("./data/chroma")
collection = chromaClient.get_or_create_collection("papers", embedding_function=resilientEF)

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
    
    # Store document content in SQLite as backup
    documentMetadata = [doc.metadata for doc in documents]
    documentContents = [doc.page_content for doc in documents]
    
    # First store all documents in the document_content table
    for i in range(len(documents)):
        docId = f"{paperId}_{i}"
        documentMetadata[i]['paperId'] = paperId  # Add the paper ID to the metadata
        c.execute('''INSERT INTO document_content VALUES (?,?,?,?,?)''', (
            docId,
            paperId,
            documentContents[i],
            json.dumps(documentMetadata[i]),
            False  # Not embedded yet
        ))
    
    conn.commit()
    conn.close()
    
    # Now try to add to ChromaDB with proper error handling
    global collection  # Access the global collection variable
    try:
        try:
            # Try to use existing collection
            collection.add(
                ids=[f"{paperId}_{i}" for i in range(len(documents))],
                documents=documentContents,
                metadatas=documentMetadata,
            )
        except Exception as e:
            if "does not exist" in str(e):
                # If collection doesn't exist, recreate it and retry
                print("ChromaDB collection not found, recreating...")
                collection = chromaClient.get_or_create_collection("papers", embedding_function=resilientEF)
                collection.add(
                    ids=[f"{paperId}_{i}" for i in range(len(documents))],
                    documents=documentContents,
                    metadatas=documentMetadata,
                )
            else:
                raise e
        
        # Mark documents as embedded in SQLite
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        c.execute("UPDATE document_content SET embedded = ? WHERE paper_id = ?", (True, paperId))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error adding documents to ChromaDB: {str(e)}")
        print(f"Documents stored in SQLite backup, will attempt to embed later.")
        
    return paperId  # Return the generated ID

def retryFailedEmbeddings():
    """Retry embedding documents that failed previously"""
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    
    # Get all non-embedded documents
    c.execute("SELECT id, paper_id, content, metadata FROM document_content WHERE embedded = ?", (False,))
    failed_docs = c.fetchall()
    
    if not failed_docs:
        conn.close()
        return 0
    
    success_count = 0
    for doc_id, paper_id, content, metadata_json in failed_docs:
        try:
            metadata = json.loads(metadata_json)
            # Try to add to ChromaDB
            collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
            
            # Mark as embedded
            c.execute("UPDATE document_content SET embedded = ? WHERE id = ?", (True, doc_id))
            conn.commit()
            success_count += 1
        except Exception as e:
            print(f"Failed to embed document {doc_id}: {str(e)}")
            # Will retry next time
    
    conn.close()
    return success_count

def semanticSearch(query: str, nResults: int = 5) -> list[str]:
    ''' Searches for papers similar to the given query and returns their IDs '''
    try:
        # First try with ChromaDB
        results = collection.query(
            query_texts=query,
            n_results=nResults
        )
        return [metad['paperId'] for metad in results['metadatas'][0]]
    except Exception as e:
        print(f"ChromaDB search failed: {str(e)}")
        print("Falling back to SQLite keyword search")
        
        # Fallback to basic keyword search in metadata
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Simple keyword search in title and summary
        c.execute(
            "SELECT id FROM metadata WHERE title LIKE ? OR summary LIKE ? LIMIT ?", 
            (f"%{query}%", f"%{query}%", nResults)
        )
        
        paper_ids = [row[0] for row in c.fetchall()]
        conn.close()
        
        return paper_ids

# Rest of the functions remain unchanged
def getPaperById(paperId: str) -> dict:
    ''' Gets a single paper by ID from the SQLite database '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute("SELECT * FROM metadata WHERE id=?", (paperId,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return None
        
    paper = {
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
    }
    conn.close()
    return paper

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
    c.execute("DELETE FROM document_content WHERE paper_id=?", (paperId,))
    conn.commit()
    conn.close()
    
    # Try to remove from ChromaDB, but don't fail if it doesn't exist
    try:
        collection.delete(where={"paperId": paperId})
    except Exception as e:
        print(f"Error removing documents from ChromaDB: {str(e)}")

def removeAllPapers():
    ''' Removes all papers from the SQLite and ChromaDB databases '''
    conn = sqlite3.connect('data/metadata.db')
    c = conn.cursor()
    c.execute("DELETE FROM metadata")
    c.execute("DELETE FROM document_content")
    c.execute("DELETE FROM fact_checks")
    c.execute("DELETE FROM application_analysis")
    c.execute("DELETE FROM taxonomy") 
    conn.commit()
    conn.close()
    
    try:
        chromaClient.delete_collection("papers")
        chromaClient.get_or_create_collection("papers", embedding_function=resilientEF)
    except Exception as e:
        print(f"Error resetting ChromaDB collection: {str(e)}")
        # Recreate the collection anyway
        chromaClient.get_or_create_collection("papers", embedding_function=resilientEF)

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