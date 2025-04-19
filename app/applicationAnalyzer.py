import ollama
import json
import time
import re  # Import regex
from typing import Dict, List
import sqlite3
from promptOptimizer import createTaskSpecificPrompts

class ApplicationAnalyzer:
    """Analyzes research papers for their practical applications in industry and academia"""
    
    def __init__(self, modelName: str = "llama3:8b", maxRetries: int = 3):
        """Initialize the application analyzer with a specific model"""
        self.modelName = modelName
        self.maxRetries = maxRetries
        # Initialize context size based on the initial model
        self.context_size = self._get_model_context_size(self.modelName) 
        
    def _get_model_context_size(self, model_name_to_check: str) -> int:
        """Retrieves the context size (num_ctx or context_length) for a given Ollama model."""
        default_size = 4096  # Default if lookup fails
        try:
            model_info = ollama.show(model_name_to_check).modelinfo
            # print(f"Model info for '{model_name_to_check}': {model_info}")
            
            # 1. Try parsing 'num_ctx' from 'parameters' string (common format)
            if 'parameters' in model_info:
                params_str = model_info['parameters']
                match = re.search(r'num_ctx\s+(\d+)', params_str)
                if match:
                    print(f"Found num_ctx in parameters: {int(match.group(1))}")
                    return int(match.group(1))
                else:
                    # Fallback parsing if regex fails
                    for line in params_str.splitlines():
                        parts = line.strip().split()
                        if len(parts) == 2 and parts[0] == 'num_ctx':
                            try:
                                print(f"Found num_ctx in parameters (split): {int(parts[1])}")
                                return int(parts[1])
                            except ValueError:
                                continue 
            
            # Check for a key ending with '.context_length'
            for key, value in model_info.items():
                if key.endswith('.context_length'):
                    try:
                        print(f"Found context length in details key '{key}': {int(value)}")
                        return int(value)
                    except (ValueError, TypeError):
                        continue # Skip if value is not a valid integer
            # Fallback: Check for a simple 'context_length' key
            if 'context_length' in model_info:
                    try:
                        print(f"Found context_length in details: {int(model_info['context_length'])}")
                        return int(model_info['context_length'])
                    except (ValueError, TypeError):
                        pass

            print(f"Warning: Could not automatically determine context length for model '{model_name_to_check}'. Using default: {default_size}")
            return default_size
            
        except Exception as e:
            print(f"Error fetching model info for '{model_name_to_check}': {e}. Using default context size: {default_size}") 
            return default_size

    def update_model(self, new_model_name: str):
        """Updates the model used by the analyzer and its context size."""
        if new_model_name != self.modelName:
            print(f"ApplicationAnalyzer updating model to: {new_model_name}")
            self.modelName = new_model_name
            self.context_size = self._get_model_context_size(self.modelName)
            print(f"ApplicationAnalyzer context size updated to: {self.context_size}")

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
        return {}  # Return empty dict for failed calls
    
    def _getDefaultApplications(self) -> Dict:
        """Return default application analysis when analysis fails"""
        return {
            "industryApplications": [],
            "academicApplications": [],
            "overallCommercialValue": "Analysis failed due to technical error.",
            "interdisciplinaryPotential": "Analysis failed due to technical error."
        }
        
    def analyzeIndustryApplications(self, text: str) -> List[Dict]:
        """
        Analyze potential industry applications
        
        Args:
            text: The paper text to analyze
            
        Returns:
            List of industry applications with metadata
        """
        # Create prompts using the fetched context size
        applicationPrompts = createTaskSpecificPrompts(text, "industryApplications", context_size=self.context_size)
        
        allApplications = []
        for promptData in applicationPrompts:
            try:
                result = self._resilientModelCall(
                    prompt=promptData["promptText"],
                    systemMessage="You are a business analyst evaluating commercial applications of academic research.",
                    formatSpec={
                        "type": "object",
                        "properties": {
                            "applications": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "industryName": {"type": "string"},
                                        "potentialApplications": {"type": "array", "items": {"type": "string"}},
                                        "implementationChallenges": {"type": "array", "items": {"type": "string"}},
                                        "commercialPotential": {"type": "string", "enum": ["low", "medium", "high"]},
                                        "timeToMarket": {"type": "string", "enum": ["short_term", "medium_term", "long_term"]}
                                    },
                                    "required": ["industryName", "potentialApplications", "implementationChallenges", "commercialPotential", "timeToMarket"]
                                }
                            }
                        },
                        "required": ["applications"]
                    }
                )
                
                if "applications" in result:
                    allApplications.extend(result["applications"])
                
            except Exception as e:
                print(f"Industry application analysis failed: {str(e)}")
                continue
        
        # Remove duplicates and consolidate
        uniqueApplications = {}
        for app in allApplications:
            industryName = app["industryName"]
            if industryName not in uniqueApplications:
                uniqueApplications[industryName] = app
            else:
                # Merge applications and challenges
                existing = uniqueApplications[industryName]
                existing["potentialApplications"].extend(app.get("potentialApplications", []))
                if "implementationChallenges" in app:
                    existing.setdefault("implementationChallenges", []).extend(app["implementationChallenges"])
                
                # Take the more optimistic assessment
                potentialMap = {"low": 1, "medium": 2, "high": 3}
                if potentialMap.get(app["commercialPotential"], 0) > potentialMap.get(existing["commercialPotential"], 0):
                    existing["commercialPotential"] = app["commercialPotential"]
        
        return list(uniqueApplications.values())
    
    def analyzeAcademicApplications(self, text: str) -> List[Dict]:
        """
        Analyze potential academic applications
        
        Args:
            text: The paper text to analyze
            
        Returns:
            List of academic field applications with metadata
        """
        # Create prompts using the fetched context size
        applicationPrompts = createTaskSpecificPrompts(text, "academicApplications", context_size=self.context_size)
        
        allApplications = []
        for promptData in applicationPrompts:
            try:
                result = self._resilientModelCall(
                    prompt=promptData["promptText"],
                    systemMessage="You are a research coordinator evaluating academic applications and potential research directions.",
                    formatSpec={
                        "type": "object",
                        "properties": {
                            "applications": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "fieldName": {"type": "string"},
                                        "potentialApplications": {"type": "array", "items": {"type": "string"}},
                                        "researchQuestions": {"type": "array", "items": {"type": "string"}},
                                        "potentialImpact": {"type": "string", "enum": ["low", "medium", "high"]},
                                        "suggestedMethodology": {"type": "string"}
                                    },
                                    "required": ["fieldName", "potentialApplications", "researchQuestions", "potentialImpact", "suggestedMethodology"]
                                }
                            }
                        },
                        "required": ["applications"]
                    }
                )
                
                if "applications" in result:
                    allApplications.extend(result["applications"])
                
            except Exception as e:
                print(f"Academic application analysis failed: {str(e)}")
                continue
        
        # Remove duplicates and consolidate
        uniqueApplications = {}
        for app in allApplications:
            fieldName = app["fieldName"]
            if fieldName not in uniqueApplications:
                uniqueApplications[fieldName] = app
            else:
                # Merge applications and research questions
                existing = uniqueApplications[fieldName]
                existing["potentialApplications"].extend(app.get("potentialApplications", []))
                existing["researchQuestions"].extend(app.get("researchQuestions", []))
                
                # Take the more optimistic impact assessment
                impactMap = {"low": 1, "medium": 2, "high": 3}
                if impactMap.get(app.get("potentialImpact"), 0) > impactMap.get(existing.get("potentialImpact"), 0):
                    existing["potentialImpact"] = app["potentialImpact"]
        
        return list(uniqueApplications.values())
    
    def storeApplicationAnalysis(self, paperId: str, industryResults: List[Dict], academicResults: List[Dict]):
        """
        Store application analysis results in the database
        
        Args:
            paperId: ID of the paper
            industryResults: Industry application analysis results
            academicResults: Academic application analysis results
        """
        # Generate overall assessments
        overallCommercial = self._assessOverallCommercialValue(industryResults)
        interdisciplinary = self._assessInterdisciplinaryPotential(academicResults)
        
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Create application analysis table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS application_analysis
                    (paper_id TEXT PRIMARY KEY,
                     industry_applications TEXT,
                     academic_applications TEXT,
                     overall_commercial_value TEXT,
                     interdisciplinary_potential TEXT,
                     FOREIGN KEY (paper_id) REFERENCES metadata(id))''')
        
        # Store the analysis results
        c.execute('''INSERT OR REPLACE INTO application_analysis VALUES (?,?,?,?,?)''', (
            paperId,
            json.dumps(industryResults),
            json.dumps(academicResults),
            overallCommercial,
            interdisciplinary
        ))
        
        conn.commit()
        conn.close()
    
    def _assessOverallCommercialValue(self, industryResults: List[Dict]) -> str:
        """Generate an overall assessment of commercial value"""
        if not industryResults:
            return "No significant commercial applications identified."
        
        highPotential = sum(1 for app in industryResults if app.get("commercialPotential") == "high")
        mediumPotential = sum(1 for app in industryResults if app.get("commercialPotential") == "medium")
        
        if highPotential > 1:
            return f"High commercial potential with {highPotential} promising industry applications identified."
        elif highPotential == 1:
            return "Good commercial potential with one highly promising industry application."
        elif mediumPotential > 0:
            return "Moderate commercial potential with some promising applications."
        else:
            return "Limited immediate commercial potential, but may have long-term applications."
    
    def _assessInterdisciplinaryPotential(self, academicResults: List[Dict]) -> str:
        """Generate an assessment of interdisciplinary research potential"""
        if not academicResults:
            return "No significant interdisciplinary applications identified."
        
        highImpact = sum(1 for app in academicResults if app.get("potentialImpact") == "high")
        numFields = len(academicResults)
        
        if numFields > 3 and highImpact > 1:
            return f"Strong interdisciplinary potential across {numFields} fields with {highImpact} high-impact applications."
        elif numFields > 3:
            return f"Good interdisciplinary potential with applications in {numFields} different fields."
        elif highImpact > 0:
            return "Focused impact in specific fields with high potential for advancement."
        else:
            return "Limited interdisciplinary potential, primarily applicable within its main field."
    
    def getApplicationAnalysisForPaper(self, paperId: str) -> Dict:
        """
        Retrieve application analysis for a specific paper
        
        Args:
            paperId: ID of the paper
            
        Returns:
            Dictionary with application analysis or None if not found
        """
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM application_analysis WHERE paper_id=?", (paperId,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "paperId": row[0],
                "industryApplications": json.loads(row[1]),
                "academicApplications": json.loads(row[2]),
                "overallCommercialValue": row[3],
                "interdisciplinaryPotential": row[4]
            }
        return None