import ollama
import re

def getModelContextSize(modelName: str) -> int:
    """Retrieves the context size (num_ctx or context_length) for a given Ollama model."""
    defaultSize = 4096
    try:
        modelInfo = ollama.show(modelName).modelinfo
        # Try parsing 'num_ctx' from 'parameters' string
        if 'parameters' in modelInfo:
            params = modelInfo['parameters']
            match = re.search(r'num_ctx\s+(\d+)', params)
            if match:
                return int(match.group(1))
            for line in params.splitlines():
                parts = line.strip().split()
                if len(parts) == 2 and parts[0] == 'num_ctx':
                    try:
                        return int(parts[1])
                    except ValueError:
                        continue
        # Check for '.context_length' key
        for key, value in modelInfo.items():
            if key.endswith('.context_length'):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    continue
        # Fallback to 'context_length'
        if 'context_length' in modelInfo:
            try:
                return int(modelInfo['context_length'])
            except (ValueError, TypeError):
                pass
        return defaultSize
    except Exception:
        return defaultSize

def getAvailableModels() -> list[str]:
    ''' Gets the list of available model names from the Ollama API '''
    try:
        return [model.model for model in ollama.list().models]
    except Exception as e:
        raise Exception(f"Error getting available models (Make sure Ollama is running): {str(e)}")