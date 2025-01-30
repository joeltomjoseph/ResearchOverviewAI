import fitz
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def extractText(pdfPath: str) -> str:
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
    
def chunkDocument(filePath: str) -> list[Document]:
    ''' Chunks the document into smaller parts for processing. This fixes semantic
    search issues with large documents that were embedded as a whole '''
    try:
        loader = PyPDFLoader(filePath)
        document = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

        chunked_documents = text_splitter.split_documents(document)
        return chunked_documents
    except Exception as e:
        raise Exception(f"Failed to chunk document: {str(e)}")