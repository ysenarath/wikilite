from typing import List

from pyvis.network import Network
from sqlalchemy import func, select, text
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


def get_unique_predicates(db: WikiLite):
    with Session(db.engine) as session:
        query = select(func.distinct(Triplet.predicate)).order_by(Triplet.predicate)
        return [predicate[0] for predicate in session.execute(query).fetchall()]


def get_relationships_with_depth(
    db: WikiLite, word_id: int, depth: int = 1, selected_predicates: List[str] = None
):
    with Session(db.engine) as session:
        # CTE query to recursively get relationships up to specified depth
        # Build predicate filter condition
        predicate_filter = ""
        params = {"word_id": word_id, "depth": depth}

        if selected_predicates:
            predicate_list = ",".join([f"'{p}'" for p in selected_predicates])
            predicate_filter = f"AND t.predicate IN ({predicate_list})"

        cte_query = text(f"""
            WITH RECURSIVE relationship_tree AS (
                -- Base case: direct relationships
                SELECT t.*, 1 as level
                FROM triplet t
                WHERE (t.subject_id = :word_id OR t.object_id = :word_id)
                {predicate_filter}
                
                UNION ALL
                
                -- Recursive case: relationships of connected words
                SELECT t.*, rt.level + 1
                FROM triplet t
                JOIN relationship_tree rt ON 
                    (t.subject_id = rt.object_id OR t.subject_id = rt.subject_id OR
                     t.object_id = rt.object_id OR t.object_id = rt.subject_id)
                WHERE rt.level < :depth
                {predicate_filter}
            )
            SELECT DISTINCT id, subject_id, predicate, object_id
            FROM relationship_tree
            ORDER BY id;
        """)

        result = session.execute(cte_query, {"word_id": word_id, "depth": depth})

        # Convert results to Triplet objects
        relationships = []
        for row in result:
            triplet = session.get(Triplet, row.id)
            if triplet:
                relationships.append(triplet)

        return relationships


def create_network_graph(relationships: List[Triplet]):
    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black")

    # Configure physics for stability
    net.force_atlas_2based(
        gravity=-50,
        central_gravity=0.01,
        spring_length=100,
        spring_strength=0.08,
        damping=0.4,
        overlap=0,
    )

    # Add nodes and edges
    for rel in relationships:
        # Add nodes with fixed positions
        net.add_node(
            rel.subject_id,
            label=rel.subject.word,
            physics=False,  # Disable physics for nodes
            size=20,  # Larger nodes for better visibility
        )
        net.add_node(rel.object_id, label=rel.object.word, physics=False, size=20)
        # Add edge with custom settings
        net.add_edge(
            rel.subject_id,
            rel.object_id,
            label=rel.predicate,
            length=200,  # Fixed edge length
        )

    # Additional stabilization settings
    net.set_options("""
        const options = {
            "physics": {
                "enabled": true,
                "stabilization": {
                    "enabled": true,
                    "iterations": 100,
                    "updateInterval": 50,
                    "fit": true
                },
                "minVelocity": 0.75,
                "solver": "forceAtlas2Based"
            }
        }
    """)

    return net.generate_html()


def show_network_view(db: WikiLite, search_term: str):
    col1, col2 = st.columns([1, 2])

    with col1:
        # Depth selector for network view
        depth = st.selectbox(
            "Relationship Depth",
            options=[1, 2, 3],
            help="Number of hops to explore in the relationship network"
        )

    with col2:
        # Get all unique predicates
        predicates = get_unique_predicates(db)
        # Multi-select for relationship types
        selected_predicates = st.multiselect(
            "Filter by Relationship Types",
            options=predicates,
            default=predicates[:5] if predicates else None,  # Default to first 5 types
            help="Select which types of relationships to show in the network",
        )

    if search_term:
        with st.spinner("Searching..."):
            with Session(db.engine) as session:
                query = select(Word).where(func.lower(Word.word) == search_term.lower())
                word = session.scalars(query).first()

            if word:
                # Get relationships with selected predicates
                relationships = get_relationships_with_depth(
                    db, word.id, depth, selected_predicates
                )

                if relationships:
                    # Create and display network graph
                    html = create_network_graph(relationships)
                    components.html(html, height=600)

                    # Display relationship count and filter info
                    st.write(
                        f"Found {len(relationships)} relationships at depth {depth}"
                        + (
                            f" (filtered by {len(selected_predicates)} relationship types)"
                            if selected_predicates
                            else ""
                        )
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


if __name__ == "__main__":
    app()
