import streamlit as st
import arxiv

st.set_page_config(page_title="Research Paper Overview with AI", page_icon="🧐")
st.title("Research Paper Overview with AI")

# Sidebar Navigation
menu = st.sidebar.selectbox("Menu", ["Upload Papers", "Search Papers", "Scrape Papers"])

if menu == "Upload Papers":
    uploadedFile = st.file_uploader("Upload a PDF paper to Analyse", type="pdf")
    
    # TODO: Process the uploaded file

elif menu == "arXiv Scraper":
    st.header("arXiv Paper Scraper")
    keyword = st.text_input("Search keyword:")
    maxResults = st.number_input("Max results:", 1, 50, 5)
    
    if st.button("Fetch Papers"):
        pass
        # search = arxiv.Search(
        #     query=keyword,
        #     max_results=maxResults,
        #     sort_by=arxiv.SortCriterion.SubmittedDate
        # )
        
        # TODO: iterate over the results and do the magic

elif menu == "Search Papers":
    st.header("Search Papers")
    searchQuery = st.text_input("Enter search query:")

    # TODO: Search through vector db and return results from SQLite