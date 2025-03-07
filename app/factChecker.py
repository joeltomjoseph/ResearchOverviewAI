import ollama
import json
import time
from typing import Dict, List, Any
import sqlite3
from promptOptimizer import createTaskSpecificPrompts

class FactChecker:
    """Checks research papers for factual accuracy and flags potential issues"""
    
    def __init__(self, modelName: str = "llama3:8b", maxRetries: int = 3):
        """Initialize the fact checker with a specific model"""
        self.modelName = modelName
        self.maxRetries = maxRetries
    
    def _resilientModelCall(self, prompt: str, systemMessage: str, formatSpec: Dict) -> Dict:
        """Make a resilient call to the Ollama model with retries"""
        retries = 0
        lastError = None
        
        while retries < self.maxRetries:
            try:
                response = ollama.generate(
                    model=self.modelName,
                    format=formatSpec,
                    options={"num_ctx": 4096, "temperature": 0.1},
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
        return self._getDefaultFactCheck()
    
    def _getDefaultFactCheck(self) -> Dict:
        """Return a default fact check structure when checking fails"""
        return {
            "issues": [],
            "overallAssessment": "Fact checking failed due to technical error.",
            "severityCount": {"low": 0, "medium": 0, "high": 0},
            "totalIssues": 0
        }
        
    def checkFacts(self, text: str) -> Dict:
        """
        Perform fact checking on the paper text
        
        Args:
            text: The full text of the paper to check
            
        Returns:
            Dictionary containing fact checking results
        """
        # Break the text into manageable chunks for fact checking
        factCheckPrompts = createTaskSpecificPrompts(text, "factChecking")
        
        # Check each chunk and collect results
        allResults = []
        for promptData in factCheckPrompts:
            result = self._resilientModelCall(
                prompt=promptData["promptText"],
                systemMessage="You are a critical research assistant tasked with identifying potential factual issues in academic papers.",
                formatSpec={
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "claim": {"type": "string"},
                                    "problem": {"type": "string"},
                                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                                    "explanation": {"type": "string"},
                                    "suggestedCorrection": {"type": "string"}
                                },
                                "required": ["claim", "problem", "severity", "explanation"]
                            }
                        },
                        "overallAssessment": {"type": "string"}
                    },
                    "required": ["issues", "overallAssessment"]
                }
            )
            if result["issues"]:
                allResults.append(result)
        
        # Merge and summarize all results
        return self._consolidateResults(allResults)
    
    def _consolidateResults(self, resultChunks: List[Dict]) -> Dict:
        """
        Consolidate fact checking results from multiple chunks
        
        Args:
            resultChunks: List of results from individual chunks
            
        Returns:
            Dictionary with consolidated fact checking results
        """
        allIssues = []
        for chunk in resultChunks:
            allIssues.extend(chunk.get("issues", []))
        
        # Remove duplicates (by comparing claims)
        uniqueIssues = []
        seenClaims = set()
        
        for issue in allIssues:
            claimSummary = issue["claim"][:100]  # Use first 100 chars as signature
            if claimSummary not in seenClaims:
                seenClaims.add(claimSummary)
                uniqueIssues.append(issue)
        
        # Count issues by severity
        severityCount = {"low": 0, "medium": 0, "high": 0}
        for issue in uniqueIssues:
            severity = issue.get("severity", "low")
            severityCount[severity] += 1
        
        # Generate overall assessment
        if not uniqueIssues:
            overall = "No significant factual issues detected."
        else:
            issueCount = len(uniqueIssues)
            highIssues = severityCount["high"]
            
            if highIssues > 0:
                overall = f"Found {issueCount} factual issues, including {highIssues} high-severity issues that may significantly impact the paper's credibility."
            else:
                overall = f"Found {issueCount} factual issues that may need addressing, but no critical flaws detected."
        
        return {
            "issues": uniqueIssues,
            "severityCount": severityCount,
            "overallAssessment": overall,
            "totalIssues": len(uniqueIssues)
        }
    
    def verifyMetadata(self, originalText: str, metadata: Dict) -> Dict:
        """
        Verify that generated metadata is accurate based on the original paper
        
        Args:
            originalText: The original paper text
            metadata: The metadata generated for the paper
            
        Returns:
            Dictionary with verification results and corrections
        """
        verificationResults = {
            "accurate": True,
            "corrections": {},
            "verificationNotes": {}
        }
        
        # Check each metadata field for accuracy
        fieldsToVerify = [
            "title", "summary", "datasets", "metrics", 
            "methods", "applications", "limitations", "areasOfImprovement"
        ]
        
        for field in fieldsToVerify:
            if field not in metadata:
                continue
                
            fieldValue = metadata[field]
            verification = self._verifyField(originalText, field, fieldValue)
            
            if not verification["accurate"]:
                verificationResults["accurate"] = False
                verificationResults["corrections"][field] = verification["suggestedCorrection"]
                verificationResults["verificationNotes"][field] = verification["note"]
        
        return verificationResults
    
    def _verifyField(self, text: str, fieldName: str, fieldValue: Any) -> Dict:
        """
        Verify a single metadata field against the original paper
        
        Args:
            text: The original paper text
            fieldName: The name of the field to verify
            fieldValue: The value of the field to verify
            
        Returns:
            Dictionary with verification results for this field
        """
        # Convert field value to string for prompt
        if isinstance(fieldValue, list):
            fieldText = ", ".join(str(item) for item in fieldValue)
        else:
            fieldText = str(fieldValue)
            
        # Check if the field value is accurate
        try:
            result = self._resilientModelCall(
                prompt=f"""
                Original paper excerpt: 
                
                {text[:3000]}...
                
                The following {fieldName} was extracted from this paper:
                
                {fieldText}
                
                Verify if this {fieldName} is accurate based on the original paper. 
                Focus on factual accuracy, not stylistic differences.
                
                Return only true if the {fieldName} is accurate, or false with a correction if it's inaccurate.
                """,
                systemMessage="You are a fact-checking assistant verifying metadata extracted from research papers.",
                formatSpec={
                    "type": "object", 
                    "properties": {
                        "accurate": {"type": "boolean"},
                        "note": {"type": "string"},
                        "suggestedCorrection": {"type": "string"}
                    },
                    "required": ["accurate", "note"]
                }
            )
            
            return result
        except Exception as e:
            print(f"Field verification failed for {fieldName}: {str(e)}")
            return {"accurate": True, "note": "Verification failed due to technical error."}
    
    def storeFactCheckResults(self, paperId: str, results: Dict):
        """
        Store fact checking results in the database
        
        Args:
            paperId: ID of the paper
            results: Fact checking results
        """
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Create fact checking table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS fact_checks
                    (paper_id TEXT PRIMARY KEY,
                     issues TEXT,
                     severity_count TEXT,
                     overall_assessment TEXT,
                     total_issues INTEGER,
                     FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
        
        # Store the fact checking results
        c.execute('''INSERT OR REPLACE INTO fact_checks VALUES (?,?,?,?,?)''', (
            paperId,
            json.dumps(results.get('issues', [])),
            json.dumps(results.get('severityCount', {"low": 0, "medium": 0, "high": 0})),
            results.get('overallAssessment', "No assessment available"),
            results.get('totalIssues', 0)
        ))
        
        conn.commit()
        conn.close()
    
    def getFactCheckForPaper(self, paperId: str) -> Dict:
        """
        Retrieve fact checking results for a specific paper
        
        Args:
            paperId: ID of the paper
            
        Returns:
            Dictionary with fact checking results or None if not found
        """
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM fact_checks WHERE paper_id=?", (paperId,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "paperId": row[0],
                "issues": json.loads(row[1]),
                "severityCount": json.loads(row[2]),
                "overallAssessment": row[3],
                "totalIssues": row[4]
            }
        return None