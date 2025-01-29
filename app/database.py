import sqlite3
import chromadb
import uuid
import json

def initDatabases():
    ''' Initialize the SQLite db for storing metadata and papers '''
    conn = sqlite3.connect("data/metadata.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS metadata
                 (id TEXT PRIMARY KEY,
                  title TEXT,
                  summary TEXT,
                  datasets TEXT,
                  metrics TEXT,
                  methods TEXT,
                  applications TEXT,
                  limitations TEXT,
                  areasOfImprovement TEXT)''')
    conn.commit()
    conn.close()

chromaClient = chromadb.Client()
collection = chromaClient.create_collection(name="papers", get_or_create=True)

def storePaper(metadata: dict, embedding: list[list[float]]):
    ''' Stores the metadata and embedding of a paper in the SQLite and ChromaDB databases '''
    paperId = str(uuid.uuid4())
    
    # SQLite to store the metadata of paper
    conn = sqlite3.connect('metadata.db')
    c = conn.cursor()
    c.execute('''INSERT INTO metadata VALUES (?,?,?,?,?,?,?,?)''', (
        paperId,
        metadata.get('title', ''),
        # json.dumps(metadata.get('authors', [])),
        metadata.get('summary', ''),
        json.dumps(metadata.get('datasets', {})),
        json.dumps(metadata.get('metrics', {})),
        json.dumps(metadata.get('methods', {})),
        json.dumps(metadata.get('applications', [])),
        json.dumps(metadata.get('limitations', []))
    ))
    conn.commit()
    conn.close()
    
    # ChromaDB to store the embeddings of the paper text
    collection.add(
        ids=paperId,
        embeddings=embedding,
        # documents=metadata.get('summary', '')
    )

def semanticSearch(query: str, nResults: int = 5) -> list[str]:
    ''' Searches for papers similar to the given query and returns their IDs '''
    try:
        results = collection.query(
            query_texts=[query],
            n_results=nResults
        )
        return results['ids']
    except Exception as e:
        raise Exception(f"Search failed: {str(e)}")

def getPapersByIds(paperIds: list[int]) -> list[dict]:
    conn = sqlite3.connect('metadata.db')
    c = conn.cursor()
    placeholders = ','.join(['?']*len(paperIds))
    c.execute(f"SELECT * FROM metadata WHERE id IN ({placeholders})", paperIds)

    papers = []
    for row in c.fetchall():
        papers.append({
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "datasets": json.loads(row[3]),
            "metrics": json.loads(row[4]),
            "methods": json.loads(row[5]),
            "applications": json.loads(row[6]),
            "limitations": json.loads(row[7]),
        })
    return papers