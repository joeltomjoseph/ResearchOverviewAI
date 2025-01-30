import streamlit as st

from database import removePaper, removeAllPapers

@st.dialog("Delete Paper")
def removePaperDialog(paperId: str):
    ''' Dialog to confirm the deletion of a single paper from the database '''
    st.warning("This action is irreversible!")
    st.write("Are you sure you want to delete this paper?")

    col1, col2 = st.columns(2)

    if col1.button("Yes"):
        removePaper(paperId)
        st.success("Paper deleted successfully!")
        st.rerun()
    elif col2.button("No"):
        st.rerun()

@st.dialog("Delete All Papers")
def removeAllPapersDialog():
    ''' Dialog to confirm the deletion of all papers from the database '''
    st.warning("This action is irreversible!")
    st.write("Are you sure you want to delete all papers?")

    col1, col2 = st.columns(2)

    if col1.button("Yes"):
        removeAllPapers()
        st.success("All papers deleted successfully!")
        st.rerun()
    elif col2.button("No"):
        st.rerun()