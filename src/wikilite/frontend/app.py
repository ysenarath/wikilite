from sqlalchemy import select
import streamlit as st

from wikilite.base import WikiLite
from wikilite.models import Example, Triplet, Word


# Initialize WikiLite database
@st.cache_resource
def init_db():
    return WikiLite("wiktextract-en-v1")


# Search words in database
def search_words(db, search_term, limit=50):
    from sqlalchemy.orm import Session

    with Session(db.engine) as session:
        # Use func.lower() for case-insensitive search
        from sqlalchemy import func

        query = (
            select(Word)
            .where(func.lower(Word.word).like(f"%{search_term.lower()}%"))
            .limit(limit)
        )
        return session.scalars(query).all()


# Get word examples
def get_examples(db, word_id):
    from sqlalchemy.orm import Session

    with Session(db.engine) as session:
        query = select(Example).where(Example.word_id == word_id)
        return session.scalars(query).all()


# Get semantic relationships
def get_relationships(db, word_id):
    from sqlalchemy.orm import Session

    with Session(db.engine) as session:
        # Get relationships where word is subject
        subject_query = select(Triplet).where(Triplet.subject_id == word_id)
        subject_relations = session.scalars(subject_query).all()

        # Get relationships where word is object
        object_query = select(Triplet).where(Triplet.object_id == word_id)
        object_relations = session.scalars(object_query).all()

        return subject_relations, object_relations


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
                            st.write(f"- {word.word} {rel.predicate} {rel.object.word}")

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
