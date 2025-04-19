import streamlit as st
import arxiv
import os
import time
import datetime
import pandas as pd
from database import initDatabases, storePaper, semanticSearch, getPapersByIds, getAllPapers, getPaperById, getPaperByTitle
from extractText import extractText, chunkDocument
from processPaper import generateMetadata, getAvailableModels
from miscFunctions import paperInfoCard, removeAllPapersDialog
from taxonomyProcessor import TaxonomyProcessor
from factChecker import FactChecker
from applicationAnalyzer import ApplicationAnalyzer
from reportGenerator import ReportGenerator
import random

# Initialize processors
taxonomyProcessor = TaxonomyProcessor()
factChecker = FactChecker()
applicationAnalyzer = ApplicationAnalyzer()
reportGenerator = ReportGenerator()

@st.fragment()
def uploadPapers():
    ''' Upload papers page that allows users to upload PDF papers for processing '''
    st.header("Upload Papers")
    st.warning("Please remain on this page until the processing is complete to avoid errors!")
    
    with st.expander("Advanced Processing Options", expanded=False):
        generateTaxonomy = st.checkbox("Generate taxonomy classification", value=True)
        checkFacts = st.checkbox("Perform fact checking", value=False)
        analyzeApplications = st.checkbox("Analyze industry & academic applications", value=True)
    
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
                
                # Fact checking if enabled
                if checkFacts:
                    st.write("Performing fact checking...")
                    verification = factChecker.verifyMetadata(text, metadata)
                    
                    if not verification["accurate"]:
                        st.warning("Found inaccuracies in the metadata. Applying corrections...")
                        for field, correction in verification["corrections"].items():
                            if field in metadata and correction:
                                metadata[field] = correction
                
                st.write("Storing the paper in the database...")
                paperId = storePaper(metadata, document)
                st.success(f"**Paper *({uploadedFile.name})* processed successfully!**")
                
                # Additional processing if enabled
                if generateTaxonomy:
                    with st.spinner("Generating taxonomy classification..."):
                        taxonomyData = taxonomyProcessor.extractTaxonomy(text)
                        taxonomyProcessor.storeTaxonomy(paperId, taxonomyData)
                        st.success("Taxonomy classification generated")
                
                if checkFacts:
                    with st.spinner("Performing detailed fact checking..."):
                        factResults = factChecker.checkFacts(text)
                        factChecker.storeFactCheckResults(paperId, factResults)
                        if factResults["total_issues"] > 0:
                            st.warning(f"Found {factResults['total_issues']} potential factual issues")
                        else:
                            st.success("No significant factual issues detected")
                
                if analyzeApplications:
                    with st.spinner("Analyzing potential applications..."):
                        industryResults = applicationAnalyzer.analyzeIndustryApplications(text)
                        academicResults = applicationAnalyzer.analyzeAcademicApplications(text)
                        applicationAnalyzer.storeApplicationAnalysis(
                            paperId, industryResults, academicResults)
                        st.success("Application analysis complete")
                
                st.json(metadata, expanded=False) # Display the metadata generated
                os.remove(tempPath) # Remove the temporary file
                st.divider()

@st.fragment()
def scrapePapers():
    ''' Scrape papers page that allows users to scrape papers from arXiv '''
    st.header("arXiv Paper Scraper")
    st.write("Enter a search keyword or select a taxonomy category to fetch papers from arXiv.")
    st.write("The papers will be processed and stored in the database for later viewing.")
    st.warning("Please remain on this page until the processing is complete to avoid errors!")
    
    # Initialize session state variables if they don't exist
    if "is_scraping" not in st.session_state:
        st.session_state.is_scraping = False
    if "stop_scraping" not in st.session_state:
        st.session_state.stop_scraping = False

    with st.expander("Advanced Processing Options", expanded=False):
        generateTaxonomy = st.checkbox("Generate taxonomy classification", value=True)
        checkFacts = st.checkbox("Perform fact checking", value=False)
        analyzeApplications = st.checkbox("Analyze industry & academic applications", value=True)
    
    # Add scrape mode selection
    scrapeMode = st.radio(
        "Scrape Mode:",
        ["Search by Keyword", "Popular Papers by ArXiv Taxonomy", "Continuous Scholar Tracking"],
        horizontal=True
    )
    
    # Conditional inputs based on selected mode
    if scrapeMode == "Search by Keyword":
        keyword = st.text_input("Search keyword:", placeholder="optimization of transformer models...")
        searchMode = "search"
        maxResults = st.number_input("Max results:", 1, 50, 5)
        continuousScraping = False
        
    elif scrapeMode == "Popular Papers by ArXiv Taxonomy":
        st.info("This mode fetches popular papers based on predefined taxonomy categories.")
        # Get popular taxonomy categories
        ARXIV_CATEGORIES = {
            "Physics": "physics",
            "Astrophysics": "astro-ph",
            "Condensed Matter": "cond-mat",
            "General Relativity": "gr-qc",
            "High Energy Physics - Experiment": "hep-ex",
            "High Energy Physics - Lattice": "hep-lat", 
            "High Energy Physics - Theory": "hep-th",
            "High Energy Physics - Phenomenology": "hep-ph",
            "Mathematical Physics": "math-ph",
            "Nonlinear Sciences": "nlin",
            "Nuclear Experiment": "nucl-ex",
            "Nuclear Theory": "nucl-th",
            "Quantum Physics": "quant-ph",
            "Mathematics": "math",
            "Computer Science": "cs",
            "Quantitative Biology": "q-bio",
            "Quantitative Finance": "q-fin",
            "Statistics": "stat",
            "Electrical Engineering": "eess",
            "Economics": "econ"
        }
        popularTaxonomies = list(ARXIV_CATEGORIES.keys())
        
        keyword = st.selectbox(
            "Select research field:",
            options=popularTaxonomies
        )
        searchMode = "category"
        maxResults = st.number_input("Max results:", 1, 50, 5)
        continuousScraping = False
        
    else:  # Continuous Scholar Tracking
        st.info("This mode continuously fetches papers from trending fields on Google Scholar until stopped.")
        maxResults = st.number_input("Papers per field:", 1, 10, 3)
        continuousScraping = True
        searchMode = "continuous"
        
        # Show both Start and Stop buttons side by side
        # col1, col2 = st.columns(2)
        
        # with col1:
        if not st.session_state.is_scraping and st.button("Start Continuous Scraping", use_container_width=True, key="start_continuous"):
            st.session_state.is_scraping = True
            st.session_state.stop_scraping = False
            st.rerun()
        
        # with col2:
        #     if st.session_state.is_scraping and st.button("Stop Scraping", type="primary", use_container_width=True, key="stop_continuous"):
        #         print("Stopping scraping...")
        #         st.session_state.stop_scraping = True
        #         st.session_state.is_scraping = False
        #         st.rerun()
        
        # Show scraping status
        if st.session_state.is_scraping:
            st.success("Scraping is running... Click Stop to end.")
        
        if st.session_state.is_scraping:
            with st.status("Fetching papers...", expanded=True) as status:
                client = arxiv.Client()
                
                while not st.session_state.stop_scraping:
                    try:
                        # Fetch trending fields from Google Scholar
                        topFields = taxonomyProcessor.fetchTopFieldsFromScholar(10)
                        # Randomly shuffle the order of fields before processing to make things interesting
                        random.shuffle(topFields)
                        
                        for field in topFields:
                            if st.session_state.stop_scraping:
                                break
                                
                            st.write(f"**Processing field: {field}**")
                            
                            try:
                                # Search by field with sorted by relevance
                                search = arxiv.Search(
                                    query=f"{field}",
                                    max_results=maxResults,
                                    sort_by=arxiv.SortCriterion.Relevance
                                )
                                
                                processPapers(client.results(search), generateTaxonomy, checkFacts, analyzeApplications)
                            except Exception as e:
                                # st.error(f"Error processing field {field}: {str(e)}")
                                continue  # Continue with next field even if one fails
                            
                    except Exception as e:
                        st.error(f"Error during scraping: {str(e)}")
                        time.sleep(5)  # Wait 5 seconds before retrying
                
                st.session_state.is_scraping = False
                status.update(label="Scraping stopped", state="complete")
                st.rerun()
    
    # Move the one-time scraping button outside the mode conditions
    if not continuousScraping and st.button("Start Scraping", use_container_width=True, key="start_button"):
        with st.status("Fetching papers...", expanded=True) as status:
            client = arxiv.Client()
            
            if searchMode == "search":
                search = arxiv.Search(keyword, max_results=maxResults)
            else:
                # print(keyword)
                print(f"Searching by category: {ARXIV_CATEGORIES[keyword]}")
                search = arxiv.Search(
                    query=f"{keyword}+OR+{ARXIV_CATEGORIES[keyword]}",
                    max_results=maxResults,
                    sort_by=arxiv.SortCriterion.Relevance
                )
            processPapers(client.results(search), generateTaxonomy, checkFacts, analyzeApplications)
            status.update(label="Scraping completed", state="complete")

def processPapers(papers, generateTaxonomy, checkFacts, analyzeApplications):
    """Helper function to process a batch of papers"""
    for paper in papers:
        print(f"Processing paper: {paper.title}")
        # If the paper is already in the database, skip it
        if getPaperByTitle(paper.title):
            st.warning(f"Paper *({paper.title})* already exists in the database. Skipping...")
            continue
        path = paper.download_pdf("data/papers")  # Download the paper
        text = extractText(path)
        st.write(f"Processing **{paper.title}**...")
        st.write(f"Generating metadata with **{selectedGenModel}**...")
        metadata = generateMetadata(text, selectedGenModel)
        
        # Fact checking if enabled
        if checkFacts or True: # TODO: Remove True?
            st.write("Performing fact checking...")
            verification = factChecker.verifyMetadata(text, metadata)
            
            if not verification["accurate"]:
                st.warning("Found inaccuracies in the metadata. Applying corrections...")
                for field, correction in verification["corrections"].items():
                    if field in metadata and correction:
                        metadata[field] = correction
        
        st.write("Chunking the document into smaller parts...")
        documents = chunkDocument(path)  # Chunk the document into smaller parts which replaces the above embedding
        metadata["title"] = paper.title  # Overwrite the generated title with the real title
        metadata["authors"] = [a.name for a in paper.authors]  # TODO: Need to find a way to make this consistent between scraped and uploaded papers
        metadata["link"] = "https://arxiv.org/abs/" + paper.get_short_id()
        st.write(f"Storing in the database...")
        paperId = storePaper(metadata, documents)
        
        # Additional processing if enabled
        if generateTaxonomy:
            with st.spinner("Generating taxonomy classification..."):
                taxonomyData = taxonomyProcessor.extractTaxonomy(text)
                taxonomyProcessor.storeTaxonomy(paperId, taxonomyData)
                st.success("Taxonomy classification generated")
        
        if checkFacts:
            with st.spinner("Performing detailed fact checking..."):
                factResults = factChecker.checkFacts(text)
                factChecker.storeFactCheckResults(paperId, factResults)
                if factResults["total_issues"] > 0:
                    st.warning(f"Found {factResults['total_issues']} potential factual issues")
                else:
                    st.success("No significant factual issues detected")
        
        if analyzeApplications:
            with st.spinner("Analyzing potential applications..."):
                industryResults = applicationAnalyzer.analyzeIndustryApplications(text)
                academicResults = applicationAnalyzer.analyzeAcademicApplications(text)
                applicationAnalyzer.storeApplicationAnalysis(
                    paperId, industryResults, academicResults)
                st.success("Application analysis complete")
                
        st.success(f"**Paper *({paper.title})* processed successfully!**")
        st.divider()

@st.fragment()
def viewAllPapers():
    ''' View all papers page that displays all papers stored in the database '''
    st.header("All Papers")
    col1, col2 = st.columns(2, vertical_alignment="center")
    if col1.button("Refresh Papers", use_container_width=True): st.rerun(scope="fragment")
    if col2.button("Clear Database", use_container_width=True): removeAllPapersDialog()
    papers = getAllPapers()
    
    for paper in papers:
        paperInfoCard(paper)

@st.fragment()
def searchPapers():
    ''' Search papers page that allows users to search for papers in the database '''
    st.header("Search Papers")
    searchQuery = st.text_input("Enter search query:", placeholder="machine learning...")
    if searchQuery:
        paperIds = semanticSearch(searchQuery)
        papers = getPapersByIds(paperIds)
        
        for paper in papers:
            paperInfoCard(paper)

@st.fragment()
def viewTaxonomy():
    ''' View taxonomy classification of papers and research fields '''
    st.header("Research Field Taxonomy")
    
    # Get field statistics
    fieldStats = taxonomyProcessor.getFieldStatistics()
    
    if not fieldStats["primaryFields"]:
        st.warning("No taxonomy data available yet. Process some papers with taxonomy classification enabled.")
        return
    
    # Display top fields
    st.subheader("Top Research Fields")
    fieldDf = pd.DataFrame({
        "Field": list(fieldStats["primaryFields"].keys()),
        "Paper Count": list(fieldStats["primaryFields"].values())
    }).sort_values("Paper Count", ascending=False).head(10)
    
    st.bar_chart(fieldDf.set_index("Field"))
    
    # Display keywords word cloud
    st.subheader("Common Research Keywords")
    if fieldStats["keywords"]:
        keywordDf = pd.DataFrame({
            "Keyword": list(fieldStats["keywords"].keys()),
            "Frequency": list(fieldStats["keywords"].values())
        }).sort_values("Frequency", ascending=False).head(25)
        
        st.bar_chart(keywordDf.set_index("Keyword"))
    
    # Option to view papers by field
    st.subheader("View Papers by Field")
    selectedField = st.selectbox(
        "Select a research field",
        options=list(fieldStats["primaryFields"].keys())
    )
    
    if selectedField:
        papers = taxonomyProcessor.getPapersByField(selectedField)
        st.write(f"Found {len(papers)} papers in the '{selectedField}' field")
        
        for paper in papers:
            with st.expander(f"{paper['title']}", expanded=False):
                st.write(f"**Summary**: {paper['summary']}")
                st.write(f"**Authors**: {', '.join(paper['authors'])}")
                
                if "taxonomy" in paper:
                    taxonomy = paper["taxonomy"]
                    st.write("**Research Classification**:")
                    st.write(f"- Primary Field: {taxonomy['primaryField']}")
                    st.write(f"- Secondary Fields: {', '.join(taxonomy['secondaryFields'])}")
                    st.write(f"- Subfields: {', '.join(taxonomy['subfields'])}")
                    st.write(f"- Keywords: {', '.join(taxonomy['keywords'])}")

@st.fragment()
def viewApplications():
    ''' View industry and academic applications of research '''
    st.header("Research Applications")
    
    # Get all papers
    papers = getAllPapers()
    
    if not papers:
        st.warning("No papers available. Upload or scrape some papers first.")
        return
    
    # Select a paper to view its applications
    paperTitles = [paper["title"] for paper in papers]
    selectedTitle = st.selectbox("Select a paper to view its applications", paperTitles)
    
    if selectedTitle:
        # Find the selected paper
        selectedPaper = next((p for p in papers if p["title"] == selectedTitle), None)
        
        if selectedPaper:
            paperId = selectedPaper["id"]
            
            # Get application analysis
            appAnalysis = applicationAnalyzer.getApplicationAnalysisForPaper(paperId)
            
            if not appAnalysis:
                st.warning("No application analysis available for this paper. Process the paper with application analysis enabled.")
                # st.button("Analyze Applications Now", on_click=lambda: analyzePaperApplications(paperId, selectedPaper["title"]))
                return
            
            # Display commercial value assessment
            st.subheader("Commercial Value")
            st.write(appAnalysis["overallCommercialValue"])
            
            # Display interdisciplinary potential
            st.subheader("Interdisciplinary Potential")
            st.write(appAnalysis["interdisciplinaryPotential"])
            
            # Display industry applications
            st.subheader("Industry Applications")
            industryApps = appAnalysis["industryApplications"]
            
            if not industryApps:
                st.info("No specific industry applications identified.")
            else:
                for i, industry in enumerate(industryApps):
                    with st.expander(f"{i+1}. {industry['industryName']} (Potential: {industry['commercialPotential'].capitalize()})"):
                        st.write("**Potential Applications:**")
                        for app in industry["potentialApplications"]:
                            st.write(f"- {app}")
                        
                        if "implementation_challenges" in industry and industry["implementationChallenges"]:
                            st.write("**Implementation Challenges:**")
                            for challenge in industry["implementationChallenges"]:
                                st.write(f"- {challenge}")
                        
                        st.write(f"**Time to Market**: {industry.get('time_to_market', 'Unknown').replace('_', ' ').capitalize()}")
            
            # Display academic applications
            st.subheader("Academic Applications")
            academicApps = appAnalysis["academicApplications"]
            
            if not academicApps:
                st.info("No specific academic applications identified.")
            else:
                for i, field in enumerate(academicApps):
                    with st.expander(f"{i+1}. {field.get('fieldName')} (Impact: {field.get('potentialImpact', 'Unkown').capitalize()})"):
                        st.write("**Potential Applications:**")
                        for app in field["potentialApplications"]:
                            st.write(f"- {app}")
                        
                        st.write("**Research Questions:**")
                        for question in field["researchQuestions"]:
                            st.write(f"- {question}")

                        st.write(f"**Time to Market**: {field.get('time_to_market', 'Unknown').replace('_', ' ').capitalize()}")

def analyzePaperApplications(paperId, title):
    '''Analyze applications for a paper on demand''' # TODO: Fix this
    st.info(f"Analyzing applications for '{title}'...")
    
    # Get paper text
    paper = getPaperById(paperId)
    if not paper:
        st.error("Paper not found")
        return
    
    # Get paper path
    paperFiles = [f for f in os.listdir("data/papers") if f.endswith(".pdf")]
    paperPath = None
    for fileName in paperFiles:
        # Simple heuristic to match paper
        if title.lower() in fileName.lower():
            paperPath = os.path.join("data/papers", fileName)
            break
    
    if not paperPath:
        st.error("Paper file not found")
        return
    
    # Extract text
    text = extractText(paperPath)
    
    # Analyze applications
    with st.spinner("Analyzing industry applications..."):
        industryResults = applicationAnalyzer.analyzeIndustryApplications(text)
    
    with st.spinner("Analyzing academic applications..."):
        academicResults = applicationAnalyzer.analyzeAcademicApplications(text)
    
    # Store results
    applicationAnalyzer.storeApplicationAnalysis(
        paperId, industryResults, academicResults)
    
    st.success("Analysis complete!")
    time.sleep(1)
    st.rerun()

@st.fragment()
def viewFactChecking():
    ''' View fact checking results for papers '''
    st.header("Fact Checking")
    
    # Get all papers
    papers = getAllPapers()
    
    if not papers:
        st.warning("No papers available. Upload or scrape some papers first.")
        return
    
    # Select a paper to view its fact check results
    paperTitles = [paper["title"] for paper in papers]
    selectedTitle = st.selectbox("Select a paper to view fact checking results", paperTitles)
    
    if selectedTitle:
        # Find the selected paper
        selectedPaper = next((p for p in papers if p["title"] == selectedTitle), None)
        
        if selectedPaper:
            paperId = selectedPaper["id"]
            
            # Get fact check results
            factResults = factChecker.getFactCheckForPaper(paperId)
            
            if not factResults:
                st.warning("No fact checking results available for this paper. Process the paper with fact checking enabled.")
                st.button("Check Facts Now", on_click=lambda: checkPaperFacts(paperId, selectedPaper["title"]))
                return
            
            # Display overall assessment
            st.subheader("Overall Assessment")
            
            severityCounts = factResults["severity_count"]
            totalIssues = factResults["total_issues"]
            
            if totalIssues == 0:
                st.success("No significant factual issues detected in this paper.")
            else:
                st.warning(f"Found {totalIssues} potential factual issues: {severityCounts['low']} low, {severityCounts['medium']} medium, and {severityCounts['high']} high severity.")
                st.write(factResults["overall_assessment"])
            
            # Display issues if any
            if totalIssues > 0:
                st.subheader("Detailed Issues")
                
                for i, issue in enumerate(factResults["issues"]):
                    with st.expander(f"Issue {i+1}: {issue['claim'][:100]}... (Severity: {issue['severity'].capitalize()})"):
                        st.write(f"**Claim**: {issue['claim']}")
                        st.write(f"**Problem**: {issue['problem']}")
                        st.write(f"**Explanation**: {issue['explanation']}")
                        
                        if "suggested_correction" in issue and issue["suggested_correction"]:
                            st.write(f"**Suggested Correction**: {issue['suggested_correction']}")

def checkPaperFacts(paperId, title):
    '''Check facts for a paper on demand'''
    st.info(f"Checking facts for '{title}'...")
    
    # Get paper path
    paperFiles = [f for f in os.listdir("data/papers") if f.endswith(".pdf")]
    paperPath = None
    for fileName in paperFiles:
        # Simple heuristic to match paper
        if title.lower() in fileName.lower():
            paperPath = os.path.join("data/papers", fileName)
            break
    
    if not paperPath:
        st.error("Paper file not found")
        return
    
    # Extract text
    text = extractText(paperPath)
    
    # Check facts
    with st.spinner("Performing fact checking..."):
        factResults = factChecker.checkFacts(text)
        factChecker.storeFactCheckResults(paperId, factResults)
    
    st.success("Fact checking complete!")
    time.sleep(1)
    st.rerun()

@st.fragment()
def generateReports():
    ''' Generate summary reports and visualizations '''
    st.header("Research Overview Reports")
    
    tab1, tab2, tab3 = st.tabs(["Summary Report", "Field Reports", "Export Report"])
    
    with tab1:
        st.subheader("Research Summary")
        reportGenerator.renderSummaryPage()
    
    with tab2:
        st.subheader("Field Reports")
        
        # Get field statistics
        fieldStats = taxonomyProcessor.getFieldStatistics()
        
        if not fieldStats["primaryFields"]:
            st.warning("No taxonomy data available yet. Process some papers with taxonomy classification enabled.")
        else:
            # Select a field to view detailed report
            selectedField = st.selectbox(
                "Select a research field to view detailed report",
                options=list(fieldStats["primaryFields"].keys())
            )
            
            if selectedField:
                reportGenerator.renderFieldReportPage(selectedField)
    
    with tab3:
        st.subheader("Export HTML Report")
        st.write("Generate a comprehensive HTML report of all research fields and applications.")
        
        if st.button("Generate HTML Report"):
            with st.spinner("Generating report..."):
                htmlReport = reportGenerator.generateHtmlReport()
                
                # Save the HTML report to a file
                reportPath = f"reports/{datetime.date.today()}.html"
                with open(reportPath, "w", encoding="utf-8") as f:
                    f.write(htmlReport)
                
                st.success("Report generated successfully in `reports` folder!")
                
                # Provide a download button
                with open(reportPath, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="Download HTML Report",
                        data=f.read(),
                        file_name="research_overview_report.html",
                        mime="text/html"
                    )

# Main App
st.set_page_config(
    page_title="Research Paper Overview with AI",
    page_icon="🧐",
    layout="wide"
)

st.title("Research Paper Overview with AI 🧐")

# Init Databases
initDatabases()

# Sidebar Navigation
st.sidebar.title("Navigation")
menu = st.sidebar.radio(
    "**Menu**", 
    [
        "Upload Papers", 
        "Scrape Papers", 
        "View all Papers", 
        "Search Papers",
        "Research Taxonomy",
        "Applications",
        "Fact Checking",
        "Generate Reports"
    ],
    index=0
)

# Select LLM Model to use
try:
    availableModels = getAvailableModels()
    posOfEmdedModel = availableModels.index("nomic-embed-text:latest") # Find the index of the recommended model for embedding to preselect it
except:
    st.error("Error: Make sure Ollama is running and please install nomic-embed-text:latest")
    posOfEmdedModel = 0

selectedGenModel = st.sidebar.selectbox(
    "**Select LLM Model for generating metadata**",
    options = availableModels,
    index = 0
)

selectedEmbedModel = st.sidebar.selectbox(
    "**Select LLM Model for generating embeddings**\nRecommended: nomic-embed-text:latest",
    options = availableModels,
    index = posOfEmdedModel
)

# Set appropriate models for our processors
taxonomyProcessor.modelName = selectedGenModel
factChecker.modelName = selectedGenModel
# Update ApplicationAnalyzer with the selected model and its context size
applicationAnalyzer.update_model(selectedGenModel) 

# Display the selected page
if menu == "Upload Papers":
    uploadPapers()
elif menu == "Scrape Papers":
    scrapePapers()
elif menu == "View all Papers":
    viewAllPapers()
elif menu == "Search Papers":
    searchPapers()
elif menu == "Research Taxonomy":
    viewTaxonomy()
elif menu == "Applications":
    viewApplications()
elif menu == "Fact Checking":
    viewFactChecking()
elif menu == "Generate Reports":
    generateReports()