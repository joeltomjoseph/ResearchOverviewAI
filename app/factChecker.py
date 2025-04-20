import ollama
import json
import time
from typing import Dict, List, Any
import sqlite3
from promptOptimizer import createTaskSpecificPrompts
from modelUtils import getModelContextSize

class FactChecker:
    """Checks research papers for factual accuracy and flags potential issues"""
    
    def __init__(self, modelName: str = "llama3.1:8b", maxRetries: int = 3):
        """Initialize the fact checker with a specific model"""
        self.modelName = modelName
        self.maxRetries = maxRetries
        self.context_size = getModelContextSize(self.modelName)
    
    def _resilientModelCall(self, prompt: str, systemMessage: str, formatSpec: Dict) -> Dict:
        """Make a resilient call to the Ollama model with retries"""
        retries = 0
        lastError = None
        
        while retries < self.maxRetries:
            try:
                response = ollama.generate(
                    model=self.modelName,
                    format=formatSpec,
                    options={"num_ctx": self.context_size, "temperature": 0.1},
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
        factCheckPrompts = createTaskSpecificPrompts(text, "factChecking", context_size=self.context_size)
        
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
            "datasets", "metrics", 
            "methods", "applications", "limitations", "areasOfImprovement"
        ]
        
        for field in fieldsToVerify:
            if field not in metadata:
                continue
                
            fieldValue = metadata[field]
            # Ensure fieldValue is a list for verification, even if it's currently a string due to prior error
            if not isinstance(fieldValue, list):
                # Attempt to handle malformed strings (e.g., comma-separated chars)
                if isinstance(fieldValue, str) and ',' in fieldValue:
                    current_value_list = [item.strip() for item in fieldValue.split(',') if item.strip()]
                elif isinstance(fieldValue, str):  # Single string, wrap in list
                    current_value_list = [fieldValue]
                else:  # Unknown type, skip verification for this field
                    print(f"Warning: Skipping verification for field '{field}' due to unexpected type: {type(fieldValue)}")
                    continue
            else:
                current_value_list = fieldValue

            verification = self._verifyField(originalText, field, current_value_list)  # Pass the list
            # print(f"Verification output for {field}: {verification}")  # Keep commented out unless debugging

            if not verification.get("accurate", True):  # Default to accurate if key missing
                verificationResults["accurate"] = False
                correction = verification.get("suggestedCorrection")

                # Ensure correction is a list of strings before assigning
                if isinstance(correction, list) and all(isinstance(item, str) for item in correction):
                    verificationResults["corrections"][field] = correction
                elif isinstance(correction, str):
                    # Attempt to parse if it's a string representation of a list or comma-separated
                    try:
                        # Basic attempt to handle comma-separated strings if the LLM fails list format
                        parsed_correction = [item.strip() for item in correction.split(',') if item.strip()]
                        if parsed_correction:  # Only assign if parsing yields something
                            verificationResults["corrections"][field] = parsed_correction
                            print(f"Warning: Parsed suggestedCorrection string for {field} into list.")
                        else:
                            print(f"Warning: Could not parse suggestedCorrection string for {field}: {correction}. Keeping original.")
                    except Exception as e:
                        print(f"Warning: Error parsing suggestedCorrection string for {field}: {correction}. Error: {e}. Keeping original.")
                else:
                    print(f"Warning: Unexpected type or format for suggestedCorrection for {field}: {type(correction)}. Keeping original.")

                verificationResults["verificationNotes"][field] = verification.get("note", "Correction applied.")
        
        return verificationResults
    
    def _verifyField(self, text: str, fieldName: str, fieldValue: List[str]) -> Dict:
        """
        Verify a single metadata field (as a list) against the original paper
        
        Args:
            text: The original paper text
            fieldName: The name of the field to verify
            fieldValue: The value of the field (as a list of strings) to verify
            
        Returns:
            Dictionary with verification results for this field
        """
        # Convert field value list to string for prompt
        fieldText = ", ".join(fieldValue)  # Join list items with ", "
        
        # Check if the field value is accurate
        try:
            result = self._resilientModelCall(
                prompt=f"""
                Original paper excerpt: 
                
                {text}...
                
                The following {fieldName} were extracted from this paper:
                
                {fieldText}
                
                Verify if this list of {fieldName} is accurate based on the original paper.
                Focus on factual accuracy, not stylistic differences. Ensure each item in the list is a complete word or phrase.
                
                Return an object with 'accurate' (boolean), 'note' (string explanation), and 'suggestedCorrection' (a JSON list of strings representing the corrected list of {fieldName}).
                If the list is accurate, return 'accurate': true and the original list in 'suggestedCorrection'.
                If inaccurate, return 'accurate': false, an explanation in 'note', and the corrected list of strings in 'suggestedCorrection'.
                Example of corrected list format: ["item 1", "item 2", "corrected item 3"]
                """,
                systemMessage="You are a fact-checking assistant verifying metadata extracted from research papers. Ensure corrections are provided as a JSON list of strings.",
                formatSpec={
                    "type": "object", 
                    "properties": {
                        "accurate": {"type": "boolean"},
                        "note": {"type": "string"},
                        "suggestedCorrection": {  # Expect a list of strings
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["accurate", "note", "suggestedCorrection"]
                }
            )
            
            return result
        except Exception as e:
            print(f"Field verification failed for {fieldName}: {str(e)}")
            # Return original value as correction in case of error, marked as accurate to avoid incorrect changes
            return {"accurate": True, "note": f"Verification failed due to technical error: {str(e)}", "suggestedCorrection": fieldValue}
    
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