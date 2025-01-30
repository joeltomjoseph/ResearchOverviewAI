import streamlit as st
import arxiv
import os

from database import initDatabases, storePaper, semanticSearch, getPapersByIds, getAllPapers
from extractText import extractText, chunkDocument
from processPaper import generateMetadata, generateEmbedding, getAvailableModels
from miscFunctions import removePaperDialog, removeAllPapersDialog

@st.fragment()
def uploadPapers():
    ''' Upload papers page that allows users to upload PDF papers for processing '''
    st.header("Upload Papers")
    uploadedFiles = st.file_uploader("Upload one or more PDF papers to Analyse", type="pdf", accept_multiple_files=True)
    
    if uploadedFiles:
        with st.status("Processing paper(s)...", expanded=True):
            for uploadedFile in uploadedFiles:
                st.write("Copying the uploaded file to the server...")

                tempPath = f"./data/temp/{uploadedFile.name}"
                os.makedirs("./data/temp", exist_ok=True)
                with open(tempPath, "wb") as f:
                    f.write(uploadedFile.getbuffer()) # Copy the uploaded file to the folder
                
                st.write(f"Extracting text from *{uploadedFile.name}*...")
                text = extractText(tempPath)
                document = chunkDocument(tempPath) # Chunk the document into smaller parts
                
                st.write(f"Generating metadata with **{selectedGenModel}**...")
                metadata = generateMetadata(text, selectedGenModel)

                # st.write(f"Generating embedding with **{selectedEmbedModel}**...") # This is the old text only method
                # embedding = generateEmbedding(text, selectedEmbedModel)

                st.write("Storing the paper in the database...")
                # storePaper(metadata, embedding)
                storePaper(metadata, document)

                st.success(f"**Paper *({uploadedFile.name})* processed successfully!**")
                st.json(metadata, expanded=False) # Display the metadata generated

                os.remove(tempPath) # Remove the temporary file
                st.divider()

@st.fragment()
def scrapePapers():
    ''' Scrape papers page that allows users to scrape papers from arXiv '''
    st.header("arXiv Paper Scraper")
    st.write("Enter a search keyword and the maximum number of papers to fetch from arXiv")
    st.write("The papers will be processed and stored in the database for later viewing")
    keyword = st.text_input("Search keyword:")
    maxResults = st.number_input("Max results:", 1, 50, 5)
    
    if st.button("Fetch Papers"):
        with st.status("Fetching papers...", expanded=True):
            client = arxiv.Client() # Create client
            search = arxiv.Search(keyword, max_results=maxResults)
            papers = client.results(search)

            st.write("Processing papers...")
            for paper in papers:
                path = paper.download_pdf("data/papers") # Download the paper
                text = extractText(path)

                st.write(f"Processing **{paper.title}**...")
                st.write(f"Generating metadata with **{selectedGenModel}**...")
                metadata = generateMetadata(text, selectedGenModel)
                # st.write(f"Generating embedding with **{selectedEmbedModel}**...")
                # embedding = generateEmbedding(text, selectedEmbedModel)
                st.write("Chunking the document into smaller parts...")
                documents = chunkDocument(path) # Chunk the document into smaller parts which replaces the above embedding
                metadata["title"] = paper.title # Overwrite the generated title with the real title
                metadata["authors"] = [a.name for a in paper.authors] # TODO: Need to find a way to make this consistent between scraped and uploaded papers
                metadata["link"] = "https://arxiv.org/abs/" + paper.get_short_id()

                st.write(f"Storing in the database...")
                storePaper(metadata, documents)
                st.success(f"**Paper *({paper.title})* processed successfully!**")
                st.divider()

@st.fragment()
def viewAllPapers():
    ''' View all papers page that displays all papers stored in the database '''
    st.header("All Papers")
    col1, col2 = st.columns(2)

    if col1.button("Refresh Papers"): st.rerun(scope="fragment")
    if col2.button("Clear Database"): removeAllPapersDialog()

    papers = getAllPapers()
    
    for paper in papers:
        with st.expander(f"**{paper['title']}**"):
            if st.button("Delete Paper from Database", key=paper["id"]):
                removePaperDialog(paper["id"])

            st.write(paper)
            st.data_editor(paper)

@st.fragment()
def searchPapers():
    ''' Search papers page that allows users to search for papers in the database '''
    st.header("Search Papers")
    searchQuery = st.text_input("Enter search query:")

    if searchQuery:
        paperIds = semanticSearch(searchQuery)
        papers = getPapersByIds(paperIds)
        
        for paper in papers:
            st.subheader(paper["title"])
            st.write(paper)
            st.divider()

# Main App
st.set_page_config(page_title="Research Paper Overview with AI", page_icon="🧐")
st.title("Research Paper Overview with AI 🧐")

# Init Databases
initDatabases()

# Sidebar Navigation
menu = st.sidebar.selectbox("**Menu**", ["Upload Papers", "Scrape Papers", "View all Papers", "Search Papers"], index=0)

# Select LLM Model to use
selectedGenModel = st.sidebar.selectbox(
    "**Select LLM Model for generating metadata**",
    options = getAvailableModels(),
    index = 0
)

selectedEmbedModel = st.sidebar.selectbox(
    "**Select LLM Model for generating embeddings**\nRecommended: nomic-embed-text:latest",
    options = getAvailableModels(),
    index = 0
)

if menu == "Upload Papers":
    uploadPapers()

elif menu == "Scrape Papers":
    scrapePapers()

elif menu == "View all Papers":
    viewAllPapers()

elif menu == "Search Papers":
    searchPapers()