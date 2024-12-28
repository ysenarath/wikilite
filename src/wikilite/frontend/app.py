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


def show_network_view(db: WikiLite, search_term: str, depth: int, selected_predicates: List[str]):
    if search_term:
        st.markdown("""
            <div style='background-color: #1e293b; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                <h3 style='margin: 0; font-size: 1.2rem; color: #e2e8f0;'>Network Visualization</h3>
                <p style='margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #94a3b8;'>
                    Explore word relationships at depth {depth}
                </p>
            </div>
        """.format(depth=depth), unsafe_allow_html=True)
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
            # Create metrics row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("""
                    <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; text-align: center;'>
                        <h3 style='color: #e2e8f0; margin: 0; font-size: 2rem;'>{count}</h3>
                        <p style='color: #94a3b8; margin: 0.5rem 0 0 0;'>Results Found</p>
                    </div>
                """.format(count=len(words)), unsafe_allow_html=True)
            
            with col2:
                example_count = sum(1 for word in words for _ in get_examples(db, word.id))
                st.markdown("""
                    <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; text-align: center;'>
                        <h3 style='color: #e2e8f0; margin: 0; font-size: 2rem;'>{count}</h3>
                        <p style='color: #94a3b8; margin: 0.5rem 0 0 0;'>Total Examples</p>
                    </div>
                """.format(count=example_count), unsafe_allow_html=True)
            
            with col3:
                relation_count = sum(len(get_relationships(db, word.id)[0]) + len(get_relationships(db, word.id)[1]) for word in words)
                st.markdown("""
                    <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; text-align: center;'>
                        <h3 style='color: #e2e8f0; margin: 0; font-size: 2rem;'>{count}</h3>
                        <p style='color: #94a3b8; margin: 0.5rem 0 0 0;'>Total Relationships</p>
                    </div>
                """.format(count=relation_count), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Display results in a grid
            for i in range(0, len(words), 2):
                col1, col2 = st.columns(2)
                
                # First column
                with col1:
                    if i < len(words):
                        word = words[i]
                        with st.container():
                            st.markdown(f"""
                                <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem;'>
                                    <h3 style='color: #e2e8f0; margin: 0 0 1rem 0; font-size: 1.3rem;'>{word.word}</h3>
                                    <div style='color: #94a3b8; margin-bottom: 1rem;'>{word.definition[:200]}...</div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            with st.expander("Show Details"):
                                st.markdown("""
                                    <div style='background-color: #1e293b; padding: 1rem; border-radius: 8px;'>
                                """, unsafe_allow_html=True)
                                
                                st.markdown("<p style='color: #e2e8f0; font-weight: 600;'>Definition:</p>", unsafe_allow_html=True)
                                st.markdown(f"<p style='color: #94a3b8;'>{word.definition}</p>", unsafe_allow_html=True)

                                examples = get_examples(db, word.id)
                                if examples:
                                    st.markdown("<p style='color: #e2e8f0; font-weight: 600; margin-top: 1rem;'>Examples:</p>", unsafe_allow_html=True)
                                    for example in examples:
                                        st.markdown(f"<p style='color: #94a3b8; margin-left: 1rem;'>• {example.example}</p>", unsafe_allow_html=True)

                                subject_relations, object_relations = get_relationships(db, word.id)
                                if subject_relations or object_relations:
                                    st.markdown("<p style='color: #e2e8f0; font-weight: 600; margin-top: 1rem;'>Semantic Relationships:</p>", unsafe_allow_html=True)
                                    
                                    if subject_relations:
                                        st.markdown("<p style='color: #94a3b8; margin-left: 1rem;'>As subject:</p>", unsafe_allow_html=True)
                                        for rel in subject_relations:
                                            st.markdown(f"<p style='color: #94a3b8; margin-left: 2rem;'>• {word.word} {rel.predicate} {rel.object.word}</p>", unsafe_allow_html=True)
                                    
                                    if object_relations:
                                        st.markdown("<p style='color: #94a3b8; margin-left: 1rem;'>As object:</p>", unsafe_allow_html=True)
                                        for rel in object_relations:
                                            st.markdown(f"<p style='color: #94a3b8; margin-left: 2rem;'>• {rel.subject.word} {rel.predicate} {word.word}</p>", unsafe_allow_html=True)
                                
                                st.markdown("</div>", unsafe_allow_html=True)

                # Second column
                with col2:
                    if i + 1 < len(words):
                        word = words[i + 1]
                        with st.container():
                            st.markdown(f"""
                                <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem;'>
                                    <h3 style='color: #e2e8f0; margin: 0 0 1rem 0; font-size: 1.3rem;'>{word.word}</h3>
                                    <div style='color: #94a3b8; margin-bottom: 1rem;'>{word.definition[:200]}...</div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            with st.expander("Show Details"):
                                st.markdown("""
                                    <div style='background-color: #1e293b; padding: 1rem; border-radius: 8px;'>
                                """, unsafe_allow_html=True)
                                
                                st.markdown("<p style='color: #e2e8f0; font-weight: 600;'>Definition:</p>", unsafe_allow_html=True)
                                st.markdown(f"<p style='color: #94a3b8;'>{word.definition}</p>", unsafe_allow_html=True)

                                examples = get_examples(db, word.id)
                                if examples:
                                    st.markdown("<p style='color: #e2e8f0; font-weight: 600; margin-top: 1rem;'>Examples:</p>", unsafe_allow_html=True)
                                    for example in examples:
                                        st.markdown(f"<p style='color: #94a3b8; margin-left: 1rem;'>• {example.example}</p>", unsafe_allow_html=True)

                                subject_relations, object_relations = get_relationships(db, word.id)
                                if subject_relations or object_relations:
                                    st.markdown("<p style='color: #e2e8f0; font-weight: 600; margin-top: 1rem;'>Semantic Relationships:</p>", unsafe_allow_html=True)
                                    
                                    if subject_relations:
                                        st.markdown("<p style='color: #94a3b8; margin-left: 1rem;'>As subject:</p>", unsafe_allow_html=True)
                                        for rel in subject_relations:
                                            st.markdown(f"<p style='color: #94a3b8; margin-left: 2rem;'>• {word.word} {rel.predicate} {rel.object.word}</p>", unsafe_allow_html=True)
                                    
                                    if object_relations:
                                        st.markdown("<p style='color: #94a3b8; margin-left: 1rem;'>As object:</p>", unsafe_allow_html=True)
                                        for rel in object_relations:
                                            st.markdown(f"<p style='color: #94a3b8; margin-left: 2rem;'>• {rel.subject.word} {rel.predicate} {word.word}</p>", unsafe_allow_html=True)
                                
                                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.write("No results found.")
    else:
        st.write("Enter a word to search the WikiLite database.")


def app():
    # Page configuration
    st.set_page_config(
        page_title="WikiLite Explorer",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for dashboard layout
    st.markdown(
        """
        <style>
        /* Main layout and typography */
        .stApp {
            background-color: #0f172a !important;
            font-family: 'Inter', sans-serif;
        }
        
        .main .block-container {
            padding-top: 2rem !important;
            max-width: 1400px;
        }

        [data-testid="stSidebar"] {
            background-color: #1e293b !important;
            border-right: 1px solid #334155;
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdown"] {
            color: #e2e8f0 !important;
        }
        
        h1 {
            color: #e2e8f0 !important;
            font-size: 2.5rem !important;
            margin-bottom: 1rem !important;
            font-weight: 700 !important;
        }
        
        /* Search box styling */
        .stTextInput input {
            border: 2px solid #e5e7eb !important;
            border-radius: 8px !important;
            padding: 0.75rem 1rem !important;
            font-size: 1.1rem !important;
            transition: all 0.2s ease;
        }
        
        .stTextInput input:focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            margin-bottom: 1rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 45px !important;
            padding: 0 20px !important;
            border-radius: 8px !important;
            background-color: #f3f4f6 !important;
            color: #4b5563 !important;
            font-weight: 500 !important;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #3b82f6 !important;
            color: white !important;
        }
        
        /* Expander styling */
        .stExpander {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            transition: all 0.2s ease;
        }
        
        .stExpander:hover {
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transform: translateY(-1px);
        }
        
        /* Select box styling */
        .stSelectbox [data-baseweb="select"] {
            border-radius: 8px !important;
        }
        
        /* Multiselect styling */
        .stMultiSelect [data-baseweb="select"] {
            border-radius: 8px !important;
        }
        
        /* Network view container */
        iframe {
            border: 1px solid #e5e7eb !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        /* Definition and examples styling */
        .stMarkdown p {
            line-height: 1.6 !important;
            margin-bottom: 0.75rem !important;
        }
        
        .stMarkdown strong {
            color: #1e3a8a !important;
            font-weight: 600 !important;
        }
        
        /* Spinner styling */
        .stSpinner > div {
            border-color: #3b82f6 !important;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Initialize database
    db = init_db()

    # Sidebar
    with st.sidebar:
        st.markdown("""
            <div style='text-align: center; padding: 1rem; margin-bottom: 2rem;'>
                <h1 style='font-size: 1.5rem; color: #e2e8f0; margin: 0;'>📚 WikiLite</h1>
                <p style='color: #94a3b8; margin: 0.5rem 0 0 0;'>Dictionary Explorer</p>
            </div>
        """, unsafe_allow_html=True)

        # Search box with placeholder
        search_term = st.text_input(
            "Search for a word",
            placeholder="Type a word (e.g., 'apple', 'run', 'happy')",
            key="search_input",
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Network Settings")
        
        # Depth selector for network view
        depth = st.select_slider(
            "Relationship Depth",
            options=[1, 2, 3],
            value=1,
            help="Number of hops to explore"
        )

        # Get all unique predicates
        predicates = get_unique_predicates(db)
        # Multi-select for relationship types
        selected_predicates = st.multiselect(
            "Relationship Types",
            options=predicates,
            default=predicates[:5] if predicates else None,
            help="Filter relationships",
        )

    # Main content area
    if not search_term:
        st.markdown("""
            <div style='text-align: center; padding: 4rem 2rem; background-color: #1e293b; border-radius: 8px; margin: 2rem 0;'>
                <h1 style='color: #e2e8f0; font-size: 2.5rem; margin-bottom: 1rem;'>Welcome to WikiLite Explorer</h1>
                <p style='color: #94a3b8; font-size: 1.2rem; max-width: 600px; margin: 0 auto;'>
                    Start by searching for a word in the sidebar to explore its meanings, examples, and relationships.
                </p>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Create tabs
        tab1, tab2 = st.tabs(["Explorer", "Network Visualization"])

        with tab1:
            show_explorer_view(db, search_term)
        with tab2:
            show_network_view(db, search_term, depth, selected_predicates)


if __name__ == "__main__":
    app()
