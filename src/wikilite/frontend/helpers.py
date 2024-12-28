from typing import List

import plotly.graph_objects as go
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from wikilite.base import WikiLite
from wikilite.models import Example, Triplet, Word


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
        predicate_filter = ""
        params = {"word_id": word_id, "depth": depth}

        if rel_types:
            predicate_list = ",".join([f"'{p}'" for p in rel_types])
            predicate_filter = f"AND t.predicate IN ({predicate_list})"

        cte_query = text(f"""
            WITH RECURSIVE relationship_tree AS (
                SELECT t.*, 1 as level
                FROM triplet t
                WHERE (t.subject_id = :word_id OR t.object_id = :word_id)
                {predicate_filter}
                
                UNION ALL
                
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
        relationships = []
        for row in result:
            triplet = session.get(Triplet, row.id)
            if triplet:
                relationships.append(triplet)
        return relationships


def create_network_graph(relationships: List[Triplet]):
    """Create a Plotly network visualization of word relationships"""
    if not relationships:
        return {}

    nodes = set()
    edges = []
    node_labels = {}
    edge_labels = []

    # Add nodes and edges
    for rel in relationships:
        nodes.add(rel.subject_id)
        nodes.add(rel.object_id)
        node_labels[rel.subject_id] = rel.subject.word
        node_labels[rel.object_id] = rel.object.word
        edges.append((rel.subject_id, rel.object_id))
        edge_labels.append(rel.predicate)

    # Convert to lists for plotting
    node_x = []
    node_y = []
    edge_x = []
    edge_y = []

    # Create circular layout for nodes
    import math

    radius = 1
    angle = 2 * math.pi / len(nodes)

    # Position nodes in a circle
    node_positions = {}
    for i, node in enumerate(nodes):
        x = radius * math.cos(i * angle)
        y = radius * math.sin(i * angle)
        node_positions[node] = (x, y)
        node_x.append(x)
        node_y.append(y)

    # Create edges
    for edge in edges:
        x0, y0 = node_positions[edge[0]]
        x1, y1 = node_positions[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    # Create edge trace
    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    # Create node trace
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=list(node_labels.values()),
        textposition="top center",
        marker=dict(showscale=False, size=20, line_width=2),
    )

    # Create figure
    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        ),
    )

    return fig
