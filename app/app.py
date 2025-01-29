import streamlit as st
import arxiv
import os

from database import initDatabases, storePaper, semanticSearch, getPapersByIds
from extractText import extractText
from processPaper import generateMetadata, generateEmbedding, getAvailableModels

st.set_page_config(page_title="Research Paper Overview with AI", page_icon="🧐")
st.title("Research Paper Overview with AI")

# Init Databases
initDatabases()

# Sidebar Navigation
menu = st.sidebar.selectbox("**Menu**", ["Upload Papers", "Search Papers", "Scrape Papers"], index=0)

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
    uploadedFile = st.file_uploader("Upload a PDF paper to Analyse", type="pdf")
    
    if uploadedFile:
        with st.status("Processing paper...", expanded=True):
            st.write("Copying the uploaded file to the server...")

            tempPath = f"./data/temp/{uploadedFile.name}"
            os.makedirs("./data/temp", exist_ok=True)
            with open(tempPath, "wb") as f:
                f.write(uploadedFile.getbuffer()) # Copy the uploaded file to the folder
            
            st.write("Extracting text from the PDF...")
            text = extractText(tempPath)
            
            st.write(f"Generating metadata with **{selectedGenModel}**...")
            metadata = generateMetadata(text, selectedGenModel)

            st.write(f"Generating embedding with **{selectedEmbedModel}**...")
            embedding = generateEmbedding(text, selectedEmbedModel)

            st.write("Storing the paper in the database...")
            storePaper(metadata, embedding)

            st.success("**Paper processed successfully!**")
            st.write(metadata) # Display the metadata generated

            os.remove(tempPath) # Remove the temporary file

elif menu == "Scrape Papers":
    st.header("arXiv Paper Scraper")
    st.write("Enter a search keyword and the maximum number of papers to fetch from arXiv")
    st.write("The papers will be processed and stored in the database for later viewing")
    keyword = st.text_input("Search keyword:")
    maxResults = st.number_input("Max results:", 1, 50, 5)
    
    if st.button("Fetch Papers"):
        with st.status("Fetching papers...", expanded=True):
            client = arxiv.Client() # Create client
            search = arxiv.Search(keyword, max_results=maxResults, sort_by=arxiv.SortCriterion.SubmittedDate)
            papers = client.results(search)

            st.write("Processing papers...")
            for paper in papers:
                path = paper.download_pdf("data/papers") # Download the paper
                text = extractText(path)

                st.write(f"Processing **{paper.title}**...")
                st.write(f"Generating metadata with **{selectedGenModel}**...")
                metadata = generateMetadata(text, selectedGenModel)
                st.write(f"Generating embedding with **{selectedEmbedModel}**...")
                embedding = generateEmbedding(text, selectedEmbedModel)
                # metadata["authors"] = [a.name for a in paper.authors] TODO: Need to find a way to make this consistent between scraped and uploaded papers
                # metadata["published"] = str(paper.published)

                st.write(f"Storing in the database...")
                storePaper(metadata, embedding)
                st.divider()

elif menu == "Search Papers":
    st.header("Search Papers")
    searchQuery = st.text_input("Enter search query:")

    if searchQuery:
        paperIds = semanticSearch(searchQuery)
        papers = getPapersByIds(paperIds)
        
        for paper in papers:
            st.subheader(paper["title"])
            st.write(paper)
            st.divider()