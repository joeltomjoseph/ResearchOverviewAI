import nltk
from nltk.tokenize import sent_tokenize
import textwrap
import streamlit as st
from typing import List, Dict

# Download NLTK data if not already downloaded
try:
    nltk.data.path.append('data/nltk_data')
    nltk.data.find('tokenizers/punkt', ['data/nltk_data'])
except LookupError:
    print("NLTK not found, Downloading NLTK data...")
    nltk.download('punkt')
    nltk.download('punkt_tab')
    

def breakPrompt(text: str, maxTokensPerChunk: int = 1000, overlapTokens: int = 100) -> List[str]:
    """
    Break a large text prompt into smaller chunks with some overlap
    
    Args:
        text: The input text to break into smaller prompts
        maxTokensPerChunk: Maximum number of tokens per chunk (approximate)
        overlapTokens: Number of tokens to overlap between chunks
        
    Returns:
        List of smaller text chunks
    """
    # Simple approximation: 1 token ≈ 4 characters in English
    maxChars = maxTokensPerChunk * 4
    overlapChars = overlapTokens * 4
    
    # For very short texts, don't chunk
    if len(text) <= maxChars:
        return [text]
        
    # Use TextWrapper for initial chunking by character count
    wrapper = textwrap.TextWrapper(width=maxChars, replace_whitespace=False)
    
    # Get initial chunks based on character count
    initialChunks = wrapper.wrap(text)
    
    # Refine chunks to try to break at sentence boundaries when possible
    chunks = []
    
    for i, chunk in enumerate(initialChunks):
        # If this is not the first chunk, add some overlap from the previous chunk
        if i > 0 and len(initialChunks[i-1]) > overlapChars:
            overlapText = initialChunks[i-1][-overlapChars:]
            chunk = overlapText + chunk
            
        # Try to break at sentence boundary if not the last chunk
        if i < len(initialChunks) - 1:
            sentences = sent_tokenize(chunk)
            
            # If we have multiple sentences, we can potentially break more cleanly
            if len(sentences) > 1:
                chunks.append(" ".join(sentences))
            else:
                chunks.append(chunk)
        else:
            # Last chunk can be added as is
            chunks.append(chunk)
    
    return chunks

def createTaskSpecificPrompts(text: str, taskType: str) -> List[Dict]:
    """
    Creates smaller, task-specific prompts from a larger text
    
    Args:
        text: The input text to analyze
        taskType: Type of analysis to perform ('industryApplications', 
                   'academicApplications', 'taxonomy', 'factChecking')
    
    Returns:
        List of dictionaries with prompt text and contextual information
    """
    baseChunks = breakPrompt(text, maxTokensPerChunk=2000)
    taskPrompts = []
    
    if taskType == "industryApplications":
        promptTemplate = (
            "Analyze this research paper excerpt for potential industrial applications:\n\n"
            "{chunk}\n\n"
            "Identify specific ways this research could be applied in industry, "
            "including potential products, services, or process improvements. "
            "Be specific about which industries would benefit most."
        )
    
    elif taskType == "academicApplications":
        promptTemplate = (
            "Analyze this research paper excerpt to identify how it could be applied to other academic fields:\n\n"
            "{chunk}\n\n"
            "Identify specific ways this research could advance other academic fields. "
            "For each field you identify, explain what specific aspects of the research are relevant "
            "and how they could lead to new research directions."
        )
    
    elif taskType == "taxonomy":
        promptTemplate = (
            "Analyze this research paper excerpt and categorize it within the academic landscape:\n\n"
            "{chunk}\n\n"
            "Identify the primary and secondary research fields this paper belongs to. "
            "Extract key terms, methodologies, and concepts that define its taxonomic position. "
            "If possible, place it within existing research taxonomies."
        )
        
    elif taskType == "factChecking":
        promptTemplate = (
            "Carefully analyze this research paper excerpt for factual accuracy:\n\n"
            "{chunk}\n\n"
            "Identify any claims that appear to be unsupported, exaggerated, contradictory to established knowledge, "
            "or potentially problematic. Focus on methodological claims, cited statistics, and conclusions drawn. "
            "For each potential issue, explain why it might be problematic."
        )
    
    else:
        raise ValueError(f"Unknown task type: {taskType}")
        
    # Create specific prompts for each chunk
    for i, chunk in enumerate(baseChunks):
        specificPrompt = {
            "chunkIndex": i,
            "totalChunks": len(baseChunks),
            "promptText": promptTemplate.format(chunk=chunk),
            "taskType": taskType
        }
        taskPrompts.append(specificPrompt)
        
    return taskPrompts

def executePromptPipeline(text: str, tasks: List[str], modelName: str) -> Dict:
    """
    Execute a series of prompts in a pipeline fashion
    
    Args:
        text: The input text to analyze
        tasks: List of task types to execute in sequence
        modelName: The LLM model to use for analysis
        
    Returns:
        Dictionary with results from each task
    """
    import ollama
    
    results = {}
    context = {"originalText": text}
    
    for task in tasks:
        taskPrompts = createTaskSpecificPrompts(text, task)
        taskResults = []
        
        for promptData in taskPrompts:
            try:
                response = ollama.generate(
                    model=modelName,
                    options={"num_ctx": 4096, "temperature": 0.1},
                    system=f"You are analyzing a research paper for {task}. Provide detailed and accurate analysis.",
                    prompt=promptData["promptText"] + "\n\nContext from previous analyses: " + str(context)
                )
                taskResults.append(response.response)
            except Exception as e:
                taskResults.append(f"Error processing chunk {promptData['chunkIndex']}: {str(e)}")
        
        # Combine results from this task
        combinedResult = "\n\n".join(taskResults)
        results[task] = combinedResult
        context[task] = combinedResult
    
    return results

@st.cache_data
def getCachedPromptChunks(text: str, taskType: str) -> List[Dict]:
    """Cached version of createTaskSpecificPrompts to avoid recalculation"""
    return createTaskSpecificPrompts(text, taskType)

if __name__ == '__main__':
    # Test the prompt optimizer
    testText = """
    This paper presents a novel approach to text generation using deep learning techniques. 
    We propose a new architecture that combines convolutional and recurrent neural networks to 
    generate coherent and contextually relevant text. Our model outperforms existing methods 
    on a variety of benchmark datasets, demonstrating the effectiveness of our approach. 
    We also introduce a new evaluation metric that captures the semantic coherence of generated text. 
    Experimental results show that our model achieves state-of-the-art performance on this metric.
    """
    
    breakChunks = breakPrompt(testText, maxTokensPerChunk=200)