import ollama
import json
import httpx
import time
from typing import Dict, List
import sqlite3
from bs4 import BeautifulSoup
from collections import Counter
import streamlit as st
from promptOptimizer import createTaskSpecificPrompts

class TaxonomyProcessor:
    """Process and organize papers into taxonomic categories"""
    
    def __init__(self, modelName: str = "nomic-embed-text:latest", maxRetries: int = 3):
        """Initialize the taxonomy processor with a specific model"""
        self.modelName = modelName
        self.maxRetries = maxRetries
        self.taxonomyCache = {}
        
    def _resilientModelCall(self, prompt: str, systemMessage: str, formatSpec: Dict) -> Dict:
        """Make a resilient call to the Ollama model with retries"""
        retries = 0
        lastError = None
        
        while retries < self.maxRetries:
            try:
                response = ollama.generate(
                    model=self.modelName,
                    format=formatSpec,
                    options={"num_ctx": 4096, "temperature": 0},
                    system=systemMessage,
                    prompt=prompt
                )
                return json.loads(response.response)
            except Exception as e:
                lastError = e
                retries += 1
                if retries < self.maxRetries:
                    time.sleep(1)  # Wait before retrying
                
        print(f"Model call failed after {self.maxRetries} attempts: {str(lastError)}")
        return self._getDefaultTaxonomy()
    
    def _getDefaultTaxonomy(self) -> Dict:
        """Return a default taxonomy structure when extraction fails"""
        return {
            "primaryField": "Uncategorized",
            "secondaryFields": [],
            "subfields": [],
            "keywords": [],
            "taxonomyPath": "uncategorized",
            "relatedFields": []
        }
        
    def extractTaxonomy(self, text: str) -> Dict:
        """Extract taxonomic information from a paper's text"""
        try:
            # Break the text into manageable chunks for taxonomy extraction
            taxonomyPrompts = createTaskSpecificPrompts(text, "taxonomy")
            taxonomyResults = []
            
            for promptData in taxonomyPrompts[:2]:  # Use only first two chunks for efficiency
                result = self._resilientModelCall(
                    prompt=promptData["promptText"],
                    systemMessage="You are a research assistant tasked with classifying academic papers into research fields and subfields.",
                    formatSpec={
                        "type": "object",
                        "properties": {
                            "primaryField": {"type": "string"},
                            "secondaryFields": {"type": "array", "items": {"type": "string"}},
                            "subfields": {"type": "array", "items": {"type": "string"}},
                            "keywords": {"type": "array", "items": {"type": "string"}},
                            "taxonomyPath": {"type": "string"},
                            "relatedFields": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["primaryField", "secondaryFields", "subfields", "keywords"]
                    }
                )
                taxonomyResults.append(result)
            
            # Merge taxonomy results from different chunks
            return self._consolidateTaxonomyResults(taxonomyResults)
            
        except Exception as e:
            print(f"Taxonomy extraction failed: {str(e)}")
            return self._getDefaultTaxonomy()
    
    def _consolidateTaxonomyResults(self, results: List[Dict]) -> Dict:
        """Consolidate taxonomy results from multiple chunks"""
        if not results:
            return self._getDefaultTaxonomy()
            
        # For primary field, take the most frequent one
        allPrimary = [r.get("primaryField", "Uncategorized") for r in results]
        primaryCounter = Counter(allPrimary)
        primaryField = primaryCounter.most_common(1)[0][0]
        
        # Merge secondary fields, subfields, keywords, and related fields
        secondaryFields = []
        subfields = []
        keywords = []
        relatedFields = []
        
        for r in results:
            secondaryFields.extend(r.get("secondaryFields", []))
            subfields.extend(r.get("subfields", []))
            keywords.extend(r.get("keywords", []))
            relatedFields.extend(r.get("relatedFields", []))
            
        # Remove duplicates while preserving order
        secondaryFields = list(dict.fromkeys(secondaryFields))
        subfields = list(dict.fromkeys(subfields))
        keywords = list(dict.fromkeys(keywords))
        relatedFields = list(dict.fromkeys(relatedFields))
        
        # Generate taxonomy path
        if len(subfields) > 0:
            taxonomyPath = f"{primaryField}/{subfields[0]}"
        else:
            taxonomyPath = primaryField
            
        return {
            "primaryField": primaryField,
            "secondaryFields": secondaryFields[:3],  # Limit to top 3
            "subfields": subfields[:5],  # Limit to top 5
            "keywords": keywords[:10],  # Limit to top 10
            "taxonomyPath": taxonomyPath,
            "relatedFields": relatedFields[:4]  # Limit to top 4
        }
    
    def storeTaxonomy(self, paperId: str, taxonomyData: Dict):
        """Store taxonomy information in the database"""
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Check if taxonomy table exists, create if not
        c.execute('''CREATE TABLE IF NOT EXISTS taxonomy
                    (paper_id TEXT PRIMARY KEY,
                     primary_field TEXT,
                     secondary_fields TEXT,
                     subfields TEXT,
                     keywords TEXT,
                     taxonomy_path TEXT,
                     related_fields TEXT,
                     FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
        
        # Store the taxonomy data
        c.execute('''INSERT OR REPLACE INTO taxonomy VALUES (?,?,?,?,?,?,?)''', (
            paperId,
            taxonomyData.get('primaryField', 'Uncategorized'),
            json.dumps(taxonomyData.get('secondaryFields', [])),
            json.dumps(taxonomyData.get('subfields', [])),
            json.dumps(taxonomyData.get('keywords', [])),
            taxonomyData.get('taxonomyPath', 'uncategorized'),
            json.dumps(taxonomyData.get('relatedFields', []))
        ))
        
        conn.commit()
        conn.close()
    
    def getTaxonomyForPaper(self, paperId: str) -> Dict:
        """Retrieve taxonomy information for a specific paper"""
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM taxonomy WHERE paper_id=?", (paperId,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "paperId": row[0],
                "primaryField": row[1],
                "secondaryFields": json.loads(row[2]),
                "subfields": json.loads(row[3]),
                "keywords": json.loads(row[4]),
                "taxonomyPath": row[5],
                "relatedFields": json.loads(row[6])
            }
        return None
    
    def getAllTaxonomies(self) -> List[Dict]:
        """Get all taxonomy entries from the database"""
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Check if taxonomy table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='taxonomy'")
        if not c.fetchone():
            conn.close()
            return []
        
        c.execute("SELECT * FROM taxonomy")
        rows = c.fetchall()
        conn.close()
        
        taxonomies = []
        for row in rows:
            taxonomies.append({
                "paperId": row[0],
                "primaryField": row[1],
                "secondaryFields": json.loads(row[2]),
                "subfields": json.loads(row[3]),
                "keywords": json.loads(row[4]),
                "taxonomyPath": row[5],
                "relatedFields": json.loads(row[6])
            })
        return taxonomies
    
    def getFieldStatistics(self) -> Dict:
        """Generate statistics about fields represented in the database"""
        taxonomies = self.getAllTaxonomies()
        
        # Count primary fields
        primaryFields = Counter([t["primaryField"] for t in taxonomies])
        
        # Count all fields (primary + secondary)
        allFields = Counter([t["primaryField"] for t in taxonomies])
        for t in taxonomies:
            for field in t["secondaryFields"]:
                allFields[field] += 1
        
        # Count subfields
        subfields = Counter()
        for t in taxonomies:
            for subfield in t["subfields"]:
                subfields[subfield] += 1
        
        # Count keywords
        keywords = Counter()
        for t in taxonomies:
            for keyword in t["keywords"]:
                keywords[keyword] += 1
        
        return {
            "primaryFields": dict(primaryFields.most_common()),
            "allFields": dict(allFields.most_common()),
            "subfields": dict(subfields.most_common(20)),
            "keywords": dict(keywords.most_common(30))
        }
    
    @st.cache_data(ttl=86400)  # Cache for a day
    def fetchTopFieldsFromScholar(_self, numFields: int = 10) -> List[str]:
        """Fetch top research fields from Google Scholar Metrics"""
        try:
            # URL for Google Scholar Metrics
            url = "https://scholar.google.com/citations?view_op=top_venues&hl=en"
            
            # Set headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            # Send request with timeout
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"Failed to fetch data: {response.status_code}")
                return []
                
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract field names from the categories section
            fields = []
            categoryElements = soup.select("td.gsc_mvt_t")
            # print(categoryElements)
            
            for element in categoryElements[:numFields]:
                fieldName = element.text.strip()
                # fieldUrl = "https://scholar.google.com" + element['href']
                
                fields.append(fieldName)
                
            return fields
            
        except Exception as e:
            print(f"Error fetching Scholar data: {str(e)}")
            return []
    
    def getPapersByField(self, field: str) -> List[Dict]:
        """Get all papers in a specific field from the database"""
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Get paper IDs with matching primary field or secondary fields
        c.execute("SELECT paper_id FROM taxonomy WHERE primary_field=?", (field,))
        primaryMatches = [row[0] for row in c.fetchall()]
        
        # For secondary fields, we need to do a JSON search
        c.execute("SELECT paper_id, secondary_fields FROM taxonomy")
        secondaryMatches = []
        for row in c.fetchall():
            secondaryFields = json.loads(row[1])
            if field in secondaryFields:
                secondaryMatches.append(row[0])
                
        # Combine and deduplicate paper IDs
        paperIds = list(set(primaryMatches + secondaryMatches))
        
        # Get full paper details
        papers = []
        for paperId in paperIds:
            # Get paper metadata
            c.execute("SELECT * FROM metadata WHERE id=?", (paperId,))
            metadataRow = c.fetchone()
            
            if metadataRow:
                # Get taxonomy data
                c.execute("SELECT * FROM taxonomy WHERE paper_id=?", (paperId,))
                taxonomyRow = c.fetchone()
                
                # Combine metadata and taxonomy
                paper = {
                    "id": metadataRow[0],
                    "title": metadataRow[1],
                    "summary": metadataRow[2],
                    "authors": json.loads(metadataRow[3]),
                    "link": metadataRow[4],
                    "datasets": json.loads(metadataRow[5]),
                    "metrics": json.loads(metadataRow[6]),
                    "methods": json.loads(metadataRow[7]),
                    "applications": json.loads(metadataRow[8]),
                    "limitations": json.loads(metadataRow[9]),
                    "areasOfImprovement": json.loads(metadataRow[10])
                }
                
                if taxonomyRow:
                    paper["taxonomy"] = {
                        "primaryField": taxonomyRow[1],
                        "secondaryFields": json.loads(taxonomyRow[2]),
                        "subfields": json.loads(taxonomyRow[3]),
                        "keywords": json.loads(taxonomyRow[4]),
                        "taxonomyPath": taxonomyRow[5],
                        "relatedFields": json.loads(taxonomyRow[6]),
                    }
                
                papers.append(paper)
                
        conn.close()
        return papers
    
    def findEmergingResearchAreas(self) -> List[Dict]:
        """Identify potentially emerging research areas from the paper collection"""
        taxonomies = self.getAllTaxonomies()
        
        # For this simple implementation, we'll consider fields with fewer papers but
        # more connections to other fields as potentially emerging
        fieldCounts = Counter()
        fieldConnections = Counter()
        
        for t in taxonomies:
            fieldCounts[t["primaryField"]] += 1
            
            # Count connections between fields
            for secondary in t["secondaryFields"]:
                fieldConnections[t["primaryField"]] += 1
                fieldConnections[secondary] += 1
        
        # Find fields with high connection-to-paper ratio
        emergingAreas = []
        for field, count in fieldCounts.items():
            if count > 0:
                connectionRatio = fieldConnections.get(field, 0) / count
                if connectionRatio > 1.5:  # Threshold can be adjusted
                    emergingAreas.append({
                        "field": field,
                        "paperCount": count,
                        "connectionCount": fieldConnections.get(field, 0),
                        "connectionRatio": connectionRatio
                    })
        
        # Sort by connection ratio
        emergingAreas.sort(key=lambda x: x["connectionRatio"], reverse=True)
        return emergingAreas[:10]  # Return top 10

if __name__ == "__main__":
    processor = TaxonomyProcessor()
    print(processor.fetchTopFieldsFromScholar())