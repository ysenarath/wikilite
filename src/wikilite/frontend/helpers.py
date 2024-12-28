from __future__ import annotations

from typing import List

import dash_cytoscape as cyto
from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.orm import Session, aliased

from wikilite.base import WikiLite
from wikilite.models import Example, Triplet, Word

CYTOSCAPE_LAYOUT = "cose"

# from packaging.version import Version
# if Version(cyto.__version__) > Version("0.2.0"):
#     cyto.load_extra_layouts()
#     CYTOSCAPE_LAYOUT = "cola"


def init_client() -> WikiLite:
    """Initialize the WikiLite database connection"""
    try:
        return WikiLite("wiktextract-en-v1")
    except Exception as e:
        print(f"Failed to initialize database: {str(e)}")
        raise


# Search words in database
def search_words(db: WikiLite, search_term: str, limit: int = 50) -> List[Word]:
    with Session(db.engine) as session:
        query = (
            session.query(Word)
            .where(func.lower(Word.word).like(f"%{search_term.lower()}%"))
            .limit(limit)
        )
        return query.all()


# Get word examples
def get_examples(db: WikiLite, word_id: int) -> List[Example]:
    with Session(db.engine) as session:
        query = select(Example).where(Example.word_id == word_id)
        return session.scalars(query).all()


def get_unique_rel_types(db: WikiLite) -> List[str]:
    with Session(db.engine) as session:
        query = select(func.distinct(Triplet.predicate)).order_by(Triplet.predicate)
        return [predicate[0] for predicate in session.execute(query).fetchall()]


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


def get_relationships_with_depth(
    db: WikiLite, word_id: int, depth: int = 1, rel_types: List[str] = None
) -> List[Triplet]:
    """Get word relationships up to a specified depth with optional predicate filtering"""
    with Session(db.engine) as session:
        # Base level relationships
        triplet = aliased(Triplet)
        base = select(
            triplet.id,
            triplet.subject_id,
            triplet.predicate,
            triplet.object_id,
            literal_column("1").label("level"),
        ).where((triplet.subject_id == word_id) | (triplet.object_id == word_id))

        if rel_types:
            base = base.where(triplet.predicate.in_(rel_types))

        # Create CTE
        cte = base.cte("relationship_tree", recursive=True)

        # Recursive part
        t = aliased(Triplet)
        recursive = (
            select(
                t.id,
                t.subject_id,
                t.predicate,
                t.object_id,
                (cte.c.level + 1).label("level"),
            )
            .join(
                cte,
                or_(
                    t.subject_id == cte.c.object_id,
                    t.subject_id == cte.c.subject_id,
                    t.object_id == cte.c.object_id,
                    t.object_id == cte.c.subject_id,
                ),
            )
            .where(cte.c.level < depth)
        )

        if rel_types:
            recursive = recursive.where(t.predicate.in_(rel_types))

        # Complete CTE with union
        cte = cte.union_all(recursive)

        # Final query
        final_query = (
            select(Triplet)
            .join(cte, Triplet.id == cte.c.id)
            .distinct()
            .order_by(Triplet.id)
        )

        return session.scalars(final_query).all()


def create_network_graph(
    relationships: List[Triplet], id: str | None = None
) -> cyto.Cytoscape:
    """Create a Plotly network visualization of word relationships"""
    if id is None:
        id = "triplets-network"
    if not relationships:
        return cyto.Cytoscape(
            id=id,
            layout={"name": "preset"},
            style={"width": "100%", "height": "800px"},
            elements=[],
        )
    nodes = []
    existing_nodes = set()
    edges = []
    for rel in relationships:
        if rel.subject_id not in existing_nodes:
            nodes.append(
                {
                    "data": {
                        "id": f"node-{rel.subject_id}",
                        "label": rel.subject.word,
                        "type": "word",
                    }
                }
            )
            existing_nodes.add(rel.subject_id)
        if rel.object_id not in existing_nodes:
            nodes.append(
                {
                    "data": {
                        "id": f"node-{rel.object_id}",
                        "label": rel.object.word,
                        "type": "word",
                    }
                }
            )
            existing_nodes.add(rel.object_id)
        edges.append(
            {
                "data": {
                    "source": f"node-{rel.subject_id}",
                    "target": f"node-{rel.object_id}",
                    "label": rel.predicate,
                    "type": "relationship",
                }
            }
        )
    elements = nodes + edges
    return cyto.Cytoscape(
        id=id,
        layout={"name": CYTOSCAPE_LAYOUT},
        style={"width": "100%", "height": "800px"},
        elements=elements,
        stylesheet=[
            {
                "selector": "node",
                "style": {
                    "label": "data(label)",
                    # "shape": "round-octagon",
                    "background-color": "lightblue",
                    "border-width": 0.1,
                    "outline-width": 0,
                    "border-color": "lightblue",
                    "border-opacity": 0.5,
                    "color": "orange",
                    "width": "1.5rem",
                    "height": "1.5rem",
                    "font-size": "1.5rem",
                    "arrow-scale": 0.1,
                },
            },
            {
                "selector": "edge",
                "style": {
                    "label": "data(label)",
                    "curve-style": "bezier",
                    "target-arrow-shape": "triangle",
                    "arrow-scale": 0.1,
                    "width": 0.1,
                    "font-size": "1.5rem",
                    "color": "orange",
                },
            },
        ],
    )
