# ResearchOverviewAI :monocle_face:
> Developed for Queen's University Belfast's QLab Datathon
>> I'm still working on the name :sweat: ^^

A tool to automate research paper processing in order to generate standardised *metadata* by prompting an LLM to generate a structured output.
- Can enable researchers to quickly search through their papers and find **relevant information**.
- Can enable researchers to quickly find papers that are **similar to their own work**.
- Can help students **find key topics** in each paper
- Can help people find **areas of improvement** that can be *capitalized on* :moneybag::moneybag::moneybag:

## Features
- **Upload** PDFs to process
- [**arXiv**](https://arxiv.org) paper scraping for infinite profit
- Ollama-powered metadata generation with a consistent structured output
- Hybrid storage (SQLite + ChromaDB Vector Storage)
- Semantic search capabilities via ChromaDB
- Easily view all stored papers
- Manual metadata editing

## How this hits the Criteria
1. **Value Creation for AI/Human Collaboration**
    - *Structured Metadata* enables LLMs to understand research contexts, experimental results, and practical applications in a more efficient manner
    - *Semantic Search* allows for quick and efficient retrieval of relevant papers
2. **Dataset Growth**
    - *Metadata Generation* can be done in the background, allowing for quick retrieval of information
    - *Many papers can be queued* for processing
3. **Cost to Run**
    - *All components of the system* are free to use and locally hosted
    - *Makes use of free APIs* for paper scraping (arXiv)
4. **Reusability of Code**
    - Function to extract text from PDFs
    - Function to get all locally available models from Ollama
5. **Evaluating Accuracy**
    - Currently, the system is not set up to evaluate accuracy however, if arXiv is used, certain fields are copied over rather than generated (Title, Authors, Link)
    - Additionally, User's can manually edit the metadata generated
    - *Future work* (and something I tried to implement) would be an additional toggle to enable an additional accuracy check using a model like `bespoke-minicheck` [more here!](https://ollama.com/blog/reduce-hallucinations-with-bespoke-minicheck)
6. **Code Quality**
    - All functions are *documented using docstrings* and make use of *type hints in declarations*
    - *Code is modular* and can be easily extended

## Installation
1. Install [Ollama](https://ollama.com) desktop and leave it running
2. Install Ollama Models:
    ```bash
    ollama pull deepseek-r1:7b
    ollama pull nomic-embed-text:latest
    ```
    > Note: `nomic-embed-text:latest` is used for embedding

    > Note: If you have a beefy GPU, please try using more demanding models such as `deepseek-r1:14b` or `deepseek-r1:32b`
3. Create a virtual environment:
    > Note: This is optional but recommended

    > MacOS/Linux:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```
    > Windows:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
4. Install app requirements:
    ```bash
    pip install -r requirements.txt
    ```
5. Run the app in a terminal (or the VSC one):
    > Note: Make sure you are in the same directory as the project

    ```bash
    streamlit run app/app.py
    ```

## Acknowledgements
- [Ollama](https://ollama.com) - providing the models and the hosting stuff
- [arXiv](https://arxiv.org) - Thank you to arXiv for use of its open access interoperability. And for the papers.
- [ChromaDB](https://chromadb.com) - for the vector storage and search capabilities
- [Streamlit](https://streamlit.io) - for the amazing UI framework
- [SQLite](https://sqlite.org) - my king