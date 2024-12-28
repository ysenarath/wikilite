from collections import deque
from typing import List

from pyvis.network import Network
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import streamlit as st
import streamlit.components.v1 as components

from wikilite.base import WikiLite
from wikilite.models import Example, Triplet, Word


# Initialize WikiLite database
@st.cache_resource
def init_db():
    return WikiLite("wiktextract-en-v1")


# Search words in database
def search_words(db: WikiLite, search_term, limit=50):
    with Session(db.engine) as session:
        # Use func.lower() for case-insensitive search
        query = (
            select(Word)
            .where(func.lower(Word.word).like(f"%{search_term.lower()}%"))
            .limit(limit)
        )
        return session.scalars(query).all()


# Get word examples
def get_examples(db: WikiLite, word_id):
    with Session(db.engine) as session:
        query = select(Example).where(Example.word_id == word_id)
        return session.scalars(query).all()


# Get semantic relationships
def get_relationships(db: WikiLite, word_id):
    with Session(db.engine) as session:
        # Get relationships where word is subject
        subject_query = select(Triplet).where(Triplet.subject_id == word_id)
        subject_relations = session.scalars(subject_query).all()

        # Get relationships where word is object
        object_query = select(Triplet).where(Triplet.object_id == word_id)
        object_relations = session.scalars(object_query).all()

        return subject_relations, object_relations


def get_relationships_with_depth(db: WikiLite, word_id: int, depth: int = 1):
    relationships = []
    visited = set()
    queue = deque([(word_id, depth)])

    with Session(db.engine) as session:
        while queue:
            current_word_id, current_depth = queue.popleft()
            if current_word_id in visited or current_depth == 0:
                continue
            visited.add(current_word_id)

            # Get relationships where word is subject
            subject_query = select(Triplet).where(Triplet.subject_id == current_word_id)
            subject_relations = session.scalars(subject_query).all()
            relationships.extend(subject_relations)

            # Get relationships where word is object
            object_query = select(Triplet).where(Triplet.object_id == current_word_id)
            object_relations = session.scalars(object_query).all()
            relationships.extend(object_relations)

            # Add connected words to the queue with decremented depth
            for rel in subject_relations:
                queue.append((rel.object_id, current_depth - 1))
            for rel in object_relations:
                queue.append((rel.subject_id, current_depth - 1))

    return relationships


def create_network_graph(relationships: List[Triplet]):
    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black")
    # Add nodes and edges
    for rel in relationships:
        # Add nodes
        net.add_node(rel.subject_id, label=rel.subject.word)
        net.add_node(rel.object_id, label=rel.object.word)
        # Add edge
        net.add_edge(rel.subject_id, rel.object_id, label=rel.predicate)
    # Generate the HTML
    net.toggle_physics(True)
    return net.generate_html()


def show_network_view(db: WikiLite, search_term: str):
    # Depth selector for network view
    depth = st.slider("Relationship Depth", min_value=1, max_value=3, value=1)

    if search_term:
        with st.spinner("Searching..."):
            with Session(db.engine) as session:
                query = select(Word).where(func.lower(Word.word) == search_term.lower())
                word = session.scalars(query).first()

            if word:
                # Get relationships
                relationships = get_relationships_with_depth(db, word.id, depth)

                if relationships:
                    # Create and display network graph
                    html = create_network_graph(relationships)
                    components.html(html, height=600)

                    # Display relationship count
                    st.write(
                        f"Found {len(relationships)} relationships at depth {depth}"
                    )
                else:
                    st.write("No relationships found for this word.")
            else:
                st.write("Word not found. Please try another word.")


def show_explorer_view(db: WikiLite, search_term):
    if search_term:
        # Show loading spinner during search
        with st.spinner("Searching..."):
            words = search_words(db, search_term)

        if words:
            # Display result count
            st.write(
                f"Found {len(words)} results{' (showing first 50)' if len(words) >= 50 else ''}"
            )

            # Display results
            for word in words:
                with st.expander(f"{word.word} - {word.definition[:100]}..."):
                    st.write("**Definition:**")
                    st.write(word.definition)

                    # Display examples
                    examples = get_examples(db, word.id)
                    if examples:
                        st.write("**Examples:**")
                        for example in examples:
                            st.write(f"- {example.example}")

                    # Display relationships
                    subject_relations, object_relations = get_relationships(db, word.id)

                    if subject_relations or object_relations:
                        st.write("**Semantic Relationships:**")

                        if subject_relations:
                            st.write("As subject:")
                            for rel in subject_relations:
                                st.write(
                                    f"- {word.word} {rel.predicate} {rel.object.word}"
                                )

                        if object_relations:
                            st.write("As object:")
                            for rel in object_relations:
                                st.write(
                                    f"- {rel.subject.word} {rel.predicate} {word.word}"
                                )
        else:
            st.write("No results found.")
    else:
        st.write("Enter a word to search the WikiLite database.")


def app():
    # Page configuration
    st.set_page_config(page_title="WikiLite Explorer", page_icon="📚", layout="wide")

    # Custom CSS
    st.markdown(
        """
        <style>
        .stExpander {
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Page title with emoji
    st.title("📚 WikiLite Explorer")
    st.markdown("*A lightweight dictionary explorer with semantic relationships*")

    # Initialize database
    db = init_db()

    # Search box with placeholder
    search_term = st.text_input(
        "Search for a word",
        placeholder="Type a word (e.g., 'apple', 'run', 'happy')",
        key="search_input",
    )

    # Create tabs
    tab1, tab2 = st.tabs(["Explorer", "Network Visualization"])

    with tab1:
        show_explorer_view(db, search_term)
    with tab2:
        show_network_view(db, search_term)


app()
