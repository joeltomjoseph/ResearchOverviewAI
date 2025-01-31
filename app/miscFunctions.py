import streamlit as st

from database import removePaper, removeAllPapers, updatePaper

@st.dialog("Delete Paper")
def removePaperDialog(paperId: str):
    ''' Dialog to confirm the deletion of a single paper from the database '''
    st.warning("This action is irreversible!")
    st.write("Are you sure you want to delete this paper?")

    col1, col2 = st.columns(2, vertical_alignment="center")

    if col1.button("Yes", use_container_width=True):
        removePaper(paperId)
        st.rerun()
        st.success("Paper deleted successfully!")
    elif col2.button("No", use_container_width=True):
        st.rerun()

@st.dialog("Delete All Papers")
def removeAllPapersDialog():
    ''' Dialog to confirm the deletion of all papers from the database '''
    st.warning("This action is irreversible!")
    st.write("Are you sure you want to delete all papers?")

    col1, col2 = st.columns(2)

    if col1.button("Yes", use_container_width=True):
        removeAllPapers()
        st.success("All papers deleted successfully!")
        st.rerun()
    elif col2.button("No", use_container_width=True):
        st.rerun()

@st.dialog("Edit Paper", width="large")
def editPaperDialog():
    ''' Dialog to edit the details of a paper in the database '''
    if st.session_state.get("show_edit_dialog"):
        with st.form(key="edit_paper_form"):
            paper = st.session_state.editing_paper # Get the paper metadata from the session state
            st.subheader("Edit Paper Details")
            
            # Form fields
            new_title = st.text_input("Title", value=paper["title"])
            new_summary = st.text_area("Summary", value=paper["summary"], height=150)
            new_authors = st.text_input("Authors (comma-separated)", value=", ".join(paper["authors"]))
            new_link = st.text_input("Link", value=paper["link"])
            new_datasets = st.text_input("Datasets (comma-separated)", value=", ".join(paper["datasets"]))
            new_metrics = st.text_input("Metrics (comma-separated)", value=", ".join(paper["metrics"]))
            new_methods = st.text_input("Methods (comma-separated)", value=", ".join(paper["methods"]))
            new_applications = st.text_input("Applications (comma-separated)", value=", ".join(paper["applications"])) # TODO: This and below should have a different seperator
            new_limitations = st.text_input("Limitations (comma-separated)", value=", ".join(paper["limitations"]))
            new_areasOfImprovement = st.text_input("Areas of Improvement (comma-separated)", value=", ".join(paper["areasOfImprovement"]))

            # Form actions
            col1, col2, col3 = st.columns([0.4, 0.2, 0.4])
            with col1:
                if st.form_submit_button("Save Changes", use_container_width=True):
                    # Update paper data
                    updated_paper = {
                        "id": paper["id"],
                        "title": new_title,
                        "summary": new_summary,
                        "authors": [a.strip() for a in new_authors.split(",")],
                        "link": new_link,
                        "datasets": [d.strip() for d in new_datasets.split(",")],
                        "metrics": [m.strip() for m in new_metrics.split(",")],
                        "methods": [m.strip() for m in new_methods.split(",")],
                        "applications": [a.strip() for a in new_applications.split(",")],
                        "limitations": [l.strip() for l in new_limitations.split(",")],
                        "areasOfImprovement": [a.strip() for a in new_areasOfImprovement.split(",")]
                    }

                    # Update database
                    updatePaper(paper["id"], updated_paper)
                    st.session_state.show_edit_dialog = False
                    st.rerun()
                    st.success("Paper updated successfully!")
                    
            with col3:
                if st.form_submit_button("Cancel", use_container_width=True):
                    st.session_state.show_edit_dialog = False
                    st.rerun()

def paperInfoCard(paper: dict):
    ''' Helper function to display a card that contains all paper details and also allows Updating and Deletion '''
    with st.expander(f"**{paper['title']}**"):
            col1, col2 = st.columns(2, vertical_alignment="center")
            if col1.button("Update Paper Details", key=paper["id"]+"update", use_container_width=True):
                st.session_state.editing_paper = paper
                st.session_state.show_edit_dialog = True

                editPaperDialog()
            if col2.button("Delete Paper from Database", key=paper["id"]+"delete", use_container_width=True):
                removePaperDialog(paper["id"])

            st.subheader(f"**{paper["title"]}**")
            st.caption(f"**Authors**: {', '.join(paper['authors'])}")
            st.write(paper["summary"])
            st.write(f"**Link**: [{paper['link']}]({paper['link']})")
            
            # Display other metadata TODO: Make more readable with numbered lists
            # st.write(f"**Datasets**:  \n{['  \n' + str(i+1) + s for i, s in enumerate(paper['datasets'])]}")
            st.write(f"**Datasets**:  \n{', '.join(paper['datasets'])}")
            st.write(f"**Metrics**:  \n{', '.join(paper['metrics'])}")
            st.write(f"**Methods**:  \n{', '.join(paper['methods'])}")
            st.write(f"**Applications**:  \n{', '.join(paper['applications'])}")
            st.write(f"**Limitations**:  \n{', '.join(paper['limitations'])}")
            st.write(f"**Areas of Improvement**:  \n{', '.join(paper['areasOfImprovement'])}")