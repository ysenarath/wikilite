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
def init_db() -> WikiLite:
    """Initialize and cache the WikiLite database connection"""
    try:
        return WikiLite("wiktextract-en-v1")
    except Exception as e:
        st.error(f"Failed to initialize database: {str(e)}")
        st.stop()


# Search words in database
def search_words(db: WikiLite, search_term: str, limit: int = 50) -> List[Word]:
    with Session(db.engine) as session:
        # Use func.lower() for case-insensitive search
        query = (
            select(Word)
            .where(func.lower(Word.word).like(f"%{search_term.lower()}%"))
            .limit(limit)
        )
        return session.scalars(query).all()


# Get word examples
def get_examples(db: WikiLite, word_id: int) -> List[Example]:
    with Session(db.engine) as session:
        query = select(Example).where(Example.word_id == word_id)
        return session.scalars(query).all()


# Get semantic relationships
def get_relationships(
    db: WikiLite, word_id: int
) -> tuple[List[Triplet], List[Triplet]]:
    with Session(db.engine) as session:
        # Get relationships where word is subject
        subject_query = select(Triplet).where(Triplet.subject_id == word_id)
        subject_relations = session.scalars(subject_query).all()

        # Get relationships where word is object
        object_query = select(Triplet).where(Triplet.object_id == word_id)
        object_relations = session.scalars(object_query).all()

        return subject_relations, object_relations


def get_unique_predicates(db: WikiLite) -> List[str]:
    with Session(db.engine) as session:
        query = select(func.distinct(Triplet.predicate)).order_by(Triplet.predicate)
        return [predicate[0] for predicate in session.execute(query).fetchall()]


def get_relationships_with_depth(
    db: WikiLite, word_id: int, depth: int = 1, selected_predicates: List[str] = None
) -> List[Triplet]:
    """Get word relationships up to a specified depth with optional predicate filtering"""
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


def create_network_graph(relationships: List[Triplet]) -> str:
    """Create an interactive network visualization of word relationships

    Args:
        relationships: List of Triplet objects representing word relationships

    Returns:
        str: HTML string containing the network visualization
    """
    if not relationships:
        return ""

    try:
        net = Network(
            height="600px", width="100%", bgcolor="#1e293b", font_color="#e2e8f0"
        )

        # Configure physics for better visualization
        net.force_atlas_2based(
            gravity=-100,  # Stronger repulsion
            central_gravity=0.02,  # Slightly stronger center pull
            spring_length=150,  # Longer edges
            spring_strength=0.1,  # Stronger spring force
            damping=0.5,  # More damping for stability
            overlap=0.1,  # Allow slight overlap
        )

        # Track added nodes to avoid duplicates
        added_nodes = set()

        # Add nodes and edges
        for rel in relationships:
            # Add subject node if not already added
            if rel.subject_id not in added_nodes:
                net.add_node(
                    rel.subject_id,
                    label=rel.subject.word,
                    title=f"Word: {rel.subject.word}",  # Tooltip
                    color="#3b82f6",  # Blue nodes
                    size=25,  # Larger nodes
                    font={"size": 16},  # Larger font
                )
                added_nodes.add(rel.subject_id)

            # Add object node if not already added
            if rel.object_id not in added_nodes:
                net.add_node(
                    rel.object_id,
                    label=rel.object.word,
                    title=f"Word: {rel.object.word}",
                    color="#3b82f6",
                    size=25,
                    font={"size": 16},
                )
                added_nodes.add(rel.object_id)

            # Add edge with custom settings
            net.add_edge(
                rel.subject_id,
                rel.object_id,
                label=rel.predicate,
                title=f"Relationship: {rel.predicate}",  # Tooltip
                color="#64748b",  # Gray edges
                width=2,  # Thicker edges
                font={"size": 14, "color": "#94a3b8"},  # Edge label styling
                smooth={"type": "curvedCW", "roundness": 0.2},  # Curved edges
            )

        # Enhanced physics and interaction settings
        net.set_options("""
            const options = {
                "physics": {
                    "enabled": true,
                    "stabilization": {
                        "enabled": true,
                        "iterations": 200,
                        "updateInterval": 25,
                        "fit": true
                    },
                    "minVelocity": 0.5,
                    "solver": "forceAtlas2Based",
                    "timestep": 0.5
                },
                "interaction": {
                    "hover": true,
                    "tooltipDelay": 200,
                    "hideEdgesOnDrag": true,
                    "navigationButtons": true,
                    "keyboard": true
                },
                "edges": {
                    "smooth": {
                        "type": "curvedCW",
                        "roundness": 0.2
                    },
                    "font": {
                        "size": 14,
                        "strokeWidth": 2,
                        "align": "middle"
                    }
                },
                "nodes": {
                    "shape": "dot",
                    "scaling": {
                        "min": 20,
                        "max": 30
                    },
                    "shadow": true
                }
            }
        """)

        return net.generate_html()
    except Exception as e:
        st.error(f"Error creating network graph: {str(e)}")
        return ""


def show_network_view(
    db: WikiLite, search_term: str, depth: int, selected_predicates: List[str]
) -> None:
    """Display an interactive network visualization of word relationships"""
    if not search_term:
        return

    try:
        st.markdown(
            """
            <div style='background-color: #1e293b; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                <h3 style='margin: 0; font-size: 1.2rem; color: #e2e8f0;'>Network Visualization</h3>
                <p style='margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #94a3b8;'>
                    Explore word relationships at depth {depth}
                </p>
            </div>
        """.format(depth=depth),
            unsafe_allow_html=True,
        )

        with st.spinner("Searching..."):
            with Session(db.engine) as session:
                query = select(Word).where(func.lower(Word.word) == search_term.lower())
                word = session.scalars(query).first()

                if not word:
                    st.info("Word not found. Please try another word.")
                    return

                # Get relationships with selected predicates
                relationships = get_relationships_with_depth(
                    db, word.id, depth, selected_predicates
                )

                if not relationships:
                    st.info("No relationships found for this word.")
                    return

                # Create and display network graph
                html = create_network_graph(relationships)
                if html:
                    components.html(html, height=600)

                    # Display relationship count and filter info
                    st.success(
                        f"Found {len(relationships)} relationships at depth {depth}"
                        + (
                            f" (filtered by {len(selected_predicates)} relationship types)"
                            if selected_predicates
                            else ""
                        )
                    )
    except Exception as e:
        st.error(f"An error occurred while creating the visualization: {str(e)}")


def display_word_details(db: WikiLite, word: Word):
    """Helper function to display word details consistently"""
    with st.container():
        st.markdown(
            f"""
            <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem;'>
                <h3 style='color: #e2e8f0; margin: 0 0 1rem 0; font-size: 1.3rem;'>{word.word}</h3>
                <div style='color: #94a3b8; margin-bottom: 1rem;'>{word.definition[:200]}...</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        with st.expander("Show Details"):
            st.markdown(
                """
                <div style='background-color: #1e293b; padding: 1rem; border-radius: 8px;'>
            """,
                unsafe_allow_html=True,
            )

            st.markdown(
                "<p style='color: #e2e8f0; font-weight: 600;'>Definition:</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='color: #94a3b8;'>{word.definition}</p>",
                unsafe_allow_html=True,
            )

            try:
                examples = get_examples(db, word.id)
                if examples:
                    st.markdown(
                        "<p style='color: #e2e8f0; font-weight: 600; margin-top: 1rem;'>Examples:</p>",
                        unsafe_allow_html=True,
                    )
                    for example in examples:
                        st.markdown(
                            f"<p style='color: #94a3b8; margin-left: 1rem;'>• {example.example}</p>",
                            unsafe_allow_html=True,
                        )

                subject_relations, object_relations = get_relationships(db, word.id)
                if subject_relations or object_relations:
                    st.markdown(
                        "<p style='color: #e2e8f0; font-weight: 600; margin-top: 1rem;'>Semantic Relationships:</p>",
                        unsafe_allow_html=True,
                    )

                    if subject_relations:
                        st.markdown(
                            "<p style='color: #94a3b8; margin-left: 1rem;'>As subject:</p>",
                            unsafe_allow_html=True,
                        )
                        for rel in subject_relations:
                            st.markdown(
                                f"<p style='color: #94a3b8; margin-left: 2rem;'>• {word.word} {rel.predicate} {rel.object.word}</p>",
                                unsafe_allow_html=True,
                            )

                    if object_relations:
                        st.markdown(
                            "<p style='color: #94a3b8; margin-left: 1rem;'>As object:</p>",
                            unsafe_allow_html=True,
                        )
                        for rel in object_relations:
                            st.markdown(
                                f"<p style='color: #94a3b8; margin-left: 2rem;'>• {rel.subject.word} {rel.predicate} {word.word}</p>",
                                unsafe_allow_html=True,
                            )
            except Exception as e:
                st.error(f"Error loading details: {str(e)}")

            st.markdown("</div>", unsafe_allow_html=True)


def get_word_metrics(db: WikiLite, words: List[Word]) -> tuple[int, int, int]:
    """Calculate metrics for a list of words efficiently"""
    try:
        with Session(db.engine) as session:
            # Get example counts
            example_count = (
                session.query(func.count(Example.id))
                .filter(Example.word_id.in_([w.id for w in words]))
                .scalar()
                or 0
            )

            # Get relationship counts
            relation_count = (
                session.query(func.count(Triplet.id))
                .filter(
                    (Triplet.subject_id.in_([w.id for w in words]))
                    | (Triplet.object_id.in_([w.id for w in words]))
                )
                .scalar()
                or 0
            )

            return len(words), example_count, relation_count
    except Exception as e:
        st.error(f"Error calculating metrics: {str(e)}")
        return 0, 0, 0


def show_explorer_view(db: WikiLite, search_term: str):
    if not search_term:
        return

    try:
        # Show loading spinner during search
        with st.spinner("Searching..."):
            words = search_words(db, search_term)

        if words:
            # Get metrics efficiently
            word_count, example_count, relation_count = get_word_metrics(db, words)

            # Create metrics row
            col1, col2, col3 = st.columns(3)
            metrics = [
                ("Results Found", word_count),
                ("Total Examples", example_count),
                ("Total Relationships", relation_count),
            ]

            for col, (label, count) in zip([col1, col2, col3], metrics):
                with col:
                    st.markdown(
                        f"""
                        <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; text-align: center;'>
                            <h3 style='color: #e2e8f0; margin: 0; font-size: 2rem;'>{count}</h3>
                            <p style='color: #94a3b8; margin: 0.5rem 0 0 0;'>{label}</p>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )

            st.markdown("<br>", unsafe_allow_html=True)

            # Display results in a grid
            for i in range(0, len(words), 2):
                col1, col2 = st.columns(2)

                with col1:
                    if i < len(words):
                        display_word_details(db, words[i])

                with col2:
                    if i + 1 < len(words):
                        display_word_details(db, words[i + 1])
        else:
            st.info("No results found.")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")


def app() -> None:
    """Main application entry point"""
    # Page configuration
    st.set_page_config(
        page_title="WikiLite Explorer",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": "https://www.extremelycoolapp.com/help",
            "Report a bug": "https://www.extremelycoolapp.com/bug",
            "About": "# This is a header. This is an *extremely* cool app!",
        },
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
            padding-top: 0 !important;
            max-width: 1400px;
        }
        
        h1 {
            color: #e2e8f0 !important;
            font-size: 2.5rem !important;
            margin-bottom: 1rem !important;
            font-weight: 700 !important;
        }
        
        /* Search box styling */
        .stTextInput input {
            background-color: #1e293b !important;
            color: #e2e8f0 !important;
            border: 2px solid #334155 !important;
            border-radius: 24px !important;
            padding: 0.8rem 1.5rem !important;
            font-size: 1.1rem !important;
            transition: all 0.2s ease;
            width: 100% !important;
            max-width: 600px !important;
            margin: 0 auto !important;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2) !important;
        }
        
        .stTextInput input:hover {
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.3) !important;
        }
        
        .stTextInput input:focus {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
            border-color: #3b82f6 !important;
        }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            margin-bottom: 1rem;
            background-color: #1e293b !important;
            padding: 1rem !important;
            border-radius: 8px !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 45px !important;
            padding: 0 20px !important;
            border-radius: 8px !important;
            background-color: #334155 !important;
            color: #94a3b8 !important;
            font-weight: 500 !important;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #3b82f6 !important;
            color: white !important;
        }
        
        /* Expander styling */
        .stExpander {
            border: none !important;
            background-color: transparent !important;
            margin-bottom: 1rem;
        }
        
        /* Select box styling */
        .stSelectbox [data-baseweb="select"] {
            background-color: #1e293b !important;
            border-radius: 8px !important;
        }
        
        /* Multiselect styling */
        .stMultiSelect [data-baseweb="select"] {
            background-color: #1e293b !important;
            border-radius: 8px !important;
        }
        
        /* Network view container */
        iframe {
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            background-color: #1e293b !important;
        }
        
        /* Definition and examples styling */
        .stMarkdown p {
            line-height: 1.6 !important;
            margin-bottom: 0.75rem !important;
            color: #e2e8f0 !important;
        }
        
        .stMarkdown strong {
            color: #e2e8f0 !important;
            font-weight: 600 !important;
        }
        
        /* Spinner styling */
        .stSpinner > div {
            border-color: #3b82f6 !important;
        }

        /* Select slider styling */
        .stSlider [data-baseweb="slider"] {
            margin-top: 1rem !important;
        }
        
        .stSlider [data-baseweb="thumb"] {
            background-color: #3b82f6 !important;
            border-color: #3b82f6 !important;
        }
        
        /* Container styling */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            background-color: #1e293b;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        /* Header styling */
        .header {
            display: flex;
            align-items: center;
            padding: 1rem 2rem;
            background-color: #1e293b;
            border-radius: 8px;
            margin-bottom: 2rem;
        }

        .header-logo {
            font-size: 1.5rem;
            color: #e2e8f0;
            margin: 0;
            padding-right: 2rem;
            border-right: 1px solid #334155;
        }

        .header-search {
            flex-grow: 1;
            padding-left: 2rem;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Initialize database
    db = init_db()

    # Dashboard header with logo and search
    st.markdown(
        """
        <div style='background-color: #1e293b; padding: 1.2rem 2rem; border-radius: 12px; margin-bottom: 2rem; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);'>
            <div style='display: flex; align-items: center;'>
                <h1 style='font-size: 1.5rem; color: #e2e8f0; margin: 0; display: flex; align-items: center;'>
                    <span style='font-size: 1.8rem; margin-right: 0.5rem;'>📚</span>
                    <span style='font-weight: 600;'>WikiLite</span>
                </h1>
            </div>
            <div style='flex-grow: 1; max-width: 500px; margin: 0 2rem;'>
                <div style='position: relative;'>
                    <div style='position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: #64748b; font-size: 1rem;'>
                        🔍
                    </div>
                </div>
            </div>
            <div style='width: 100px;'></div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Streamlit search input with custom styling
    search_term = st.text_input(
        "Search words...",
        key="search_input",
        help="Enter a word to explore its relationships and examples",
        label_visibility="collapsed",
    )

    # Network settings in a horizontal layout when needed
    if search_term:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        with col1:
            depth = st.select_slider(
                "Relationship Depth",
                options=[1, 2, 3],
                value=1,
                help="Number of hops to explore",
            )
        with col2:
            predicates = get_unique_predicates(db)
            selected_predicates = st.multiselect(
                "Filter Relationship Types",
                options=predicates,
                default=predicates[:5] if predicates else None,
                help="Select which types of relationships to show",
            )

        # Create tabs
        tab1, tab2 = st.tabs(["Explorer", "Network Visualization"])

        with tab1:
            show_explorer_view(db, search_term)
        with tab2:
            show_network_view(db, search_term, depth, selected_predicates)


if __name__ == "__main__":
    app()
