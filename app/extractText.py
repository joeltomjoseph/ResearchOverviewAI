import fitz

def extractText(pdfPath):
    ''' Extracts text from a PDF file TODO: Maybe upgrade to read each page 
    separately as an image in order to gather context from graphs and images '''
    try:
        text = ""
        with fitz.open(pdfPath) as doc:
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        raise Exception(f"Failed to extract text: {str(e)}")