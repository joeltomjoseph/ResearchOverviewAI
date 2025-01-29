import ollama
import pydantic
import json

# Epic Ollama moment - The docstring is actually included when the class is serialized to JSON, so it provides extra context for mr LLM
class Metadata(pydantic.BaseModel):
    ''' Pydantic model for the metadata to be generated by the Ollama API
    https://ollama.com/blog/structured-outputs 
    
    Args:
        title: str - Title of the paper
        summary: str - Summary of the paper
        # authors: list[str] - Authors of the paper
        datasets: list[str] - Datasets used in the paper to achieve results
        metrics: list[str] - Metrics used to evaluate results
        methods: list[str] - Methods used to achieve results
        applications: list[str] - Realworld applications of the paper and why it can be useful
        limitations: list[str] - Limitations of the paper that need to be addressed
        areasOfImprovement: list[str] - At least 3 specific areas of improvement that could lead to innovation and how it can be achieved'''
    title: str
    summary: str
    # authors: list[str]
    datasets: list[str]
    metrics: list[str]
    methods: list[str]
    applications: list[str]
    limitations: list[str]
    areasOfImprovement: list[str]

def getAvailableModels() -> list:
    ''' Gets the list of available model names from the Ollama API '''
    try:
        return [model.model for model in ollama.list().models]
    except:
        return ["llama3.1:8b"]  # Fallback TODO: change to error?

def generateMetadata(text: str, modelName: str) -> dict:
    ''' Generates metadata from the given text using the specified model and returns it as a dictionary (JSON)'''
    try:
        response = ollama.generate(
            model = modelName,
            format=Metadata.model_json_schema(), # Format the response as a JSON schema from the Metadata model
            options={"num_ctx": 4096, "temperature": 0}, # Increase the context size and lower temp
            system="You are a research assistant that has been tasked with generating structured metadata for a research paper.",
            prompt=f"""
                PROMPT: Generate metadata for the following research paper in JSON format. 
                Use exact extracts/sections/titles/names where possible. 
                Validate the output for accuracy and completeness.

                CONTENT: {text}..."""
        )
        return json.loads(response.response)
    except Exception as e:
        return {"error": f"Metadata generation failed: {str(e)}"}

def generateEmbedding(text: str, modelName: str) -> list[list[float]]:
    ''' Generates a vector embedding for the given text using the specified model '''
    try:
        response = ollama.embed(model=modelName, input=text)
        return response.embeddings
    except Exception as e:
        raise Exception(f"Embedding generation failed: {str(e)}")

if __name__ == "__main__": # Test the functions
    import arxiv
    import extractText

    print("Available Models: ", getAvailableModels(), "\n") # Find all available models

    client = arxiv.Client() # Create client
    search = arxiv.Search(id_list=["2310.11453"], max_results=1) # Search for the BitNet paper to test
    paper = client.results(search).__next__() # Get the paper

    path = paper.download_pdf("data/papers") # Download the paper
    text = extractText.extractText(path) # Extract text from the paper

    # print(text)
    print(generateMetadata(text, "deepseek-r1:7b"))
    # print(generateEmbedding(text, "nomic-embed-text:latest"))