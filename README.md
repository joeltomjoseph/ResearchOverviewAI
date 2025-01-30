# ResearchOverviewAI :monocle_face:
> Developed for Queen's University Belfast's QLab Datathon
>> I'm still working on the name :sweat: ^^

A tool to automate research paper processing in order to generate standardised *metadata*.
- Can enable researchers to quickly search through their papers and find **relevant information**.
- Can enable researchers to quickly find papers that are **similar to their own work**.
- Can help students **find key topics** in each paper
- Can help people find **areas of improvement** that can be *capitalized on* :moneybag::moneybag::moneybag:

## Features
- **Upload** PDFs to process
- [**arXiv**](https://arxiv.org) paper scraping for infinite profit
- Ollama-powered metadata generation
- Hybrid storage (SQLite + ChromaDB Vector Storage)
- Semantic search capabilities via ChromaDB

## Installation
1. Install [Ollama](https://ollama.com) desktop and leave it running
2. Install Ollama Models:
    ```bash
    ollama pull deepseek-r1:7b
    ollama pull nomic-embed-text:latest
    ```
    > Note: `nomic-embed-text:latest` is used for embedding
    > If you have a beefy GPU, please try using more demanding models such as `deepseek-r1:14b` or `deepseek-r1:32b`
3. Create a virtual environment:
    > Note: This is optional but recommended

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```
4. Install app requirements:
    ```bash
    pip install -r requirements.txt
    ```
5. Run the app in a terminal (or the VSC one):
    > Note: Make sure you are in the same directory as the project

    ```bash
    streamlit run .app/app.py
    ```

## Acknowledgements
- [Ollama](https://ollama.com) - providing the models and the hosting stuff
- [arXiv](https://arxiv.org) - Thank you to arXiv for use of its open access interoperability. And for the papers.
- [ChromaDB](https://chromadb.com) - for the vector storage and search capabilities
- [Streamlit](https://streamlit.io) - for the amazing UI framework
- [SQLite](https://sqlite.org) - my king