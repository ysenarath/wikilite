"""Streamlit app for browsing the Wiktionary database."""

import networkx as nx
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, joinedload

from wikilite.models import Entry, Sense, Example

# Set up database connection
DB_PATH = "resources/wiktextract-en.db"
engine = create_engine(f"sqlite:///{DB_PATH}")


def find_related_words(
    session, word: str, depth: int = 2, max_words_per_level: int = 10
):
    """Find related words up to n levels deep."""
    G = nx.Graph()
    G.add_node(word)  # Add the root word

    words_to_process = [(word, 0)]  # (word, depth)
    processed_words = {word}

    while words_to_process and len(processed_words) < 100:  # Limit total nodes
        current_word, current_depth = words_to_process.pop(0)

        if current_depth >= depth:
            continue

        # Find entries where this word appears in definitions or examples
        related_entries = (
            session.query(Entry)
            .join(Sense)
            .outerjoin(Example)
            .filter(
                or_(
                    Sense.definition.like(f"%{current_word}%"),
                    Example.text.like(f"%{current_word}%"),
                )
            )
            .limit(max_words_per_level)
            .all()
        )

        for entry in related_entries:
            if entry.title not in processed_words:
                G.add_node(entry.title)
                G.add_edge(current_word, entry.title)
                processed_words.add(entry.title)
                if current_depth + 1 < depth:
                    words_to_process.append((entry.title, current_depth + 1))

    return G


def search_entries(query: str, search_type: str = "title"):
    """Search entries in the database."""
    with Session(engine) as session:
        base_query = session.query(Entry).options(
            joinedload(Entry.senses).joinedload(Sense.examples)
        )

        if search_type == "title":
            # Search in entry titles
            results = base_query.filter(Entry.title.like(f"%{query}%")).limit(50).all()
        elif search_type == "definition":
            # Search in definitions
            results = (
                base_query.join(Sense)
                .filter(Sense.definition.like(f"%{query}%"))
                .limit(50)
                .all()
            )
        elif search_type == "example":
            # Search in examples
            results = (
                base_query.join(Sense)
                .join(Example)
                .filter(Example.text.like(f"%{query}%"))
                .limit(50)
                .all()
            )
        return results


def create_visualizations(results):
    """Create visualizations for the search results."""
    if not results:
        return

    # Create DataFrame from results
    data = []
    for entry in results:
        example_count = sum(len(sense.examples) for sense in entry.senses)
        data.append(
            {
                "title": entry.title,
                "language": entry.language,
                "part_of_speech": entry.part_of_speech or "unknown",
                "sense_count": len(entry.senses),
                "example_count": example_count,
            }
        )
    df = pd.DataFrame(data)

    # Create visualizations
    col1, col2 = st.columns(2)

    with col1:
        # Part of Speech distribution
        pos_counts = df["part_of_speech"].value_counts()
        fig_pos = px.pie(
            values=pos_counts.values,
            names=pos_counts.index,
            title="Distribution of Parts of Speech",
        )
        st.plotly_chart(fig_pos)

    with col2:
        # Language distribution
        lang_counts = df["language"].value_counts()
        fig_lang = px.bar(
            x=lang_counts.index,
            y=lang_counts.values,
            title="Language Distribution",
            labels={"x": "Language", "y": "Count"},
        )
        st.plotly_chart(fig_lang)

    # Examples per entry
    fig_examples = px.scatter(
        df,
        x="title",
        y="example_count",
        color="language",
        title="Number of Examples per Entry",
        labels={"title": "Word", "example_count": "Number of Examples"},
    )
    fig_examples.update_xaxes(tickangle=45)
    st.plotly_chart(fig_examples)


def create_network_graph(G):
    """Create a network visualization using plotly."""
    # Get node positions using Fruchterman-Reingold force-directed algorithm
    pos = nx.spring_layout(G)

    # Create edges
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    # Create nodes
    node_x = []
    node_y = []
    node_text = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=node_text,
        textposition="top center",
        marker=dict(
            showscale=True,
            colorscale="YlGnBu",
            size=10,
            colorbar=dict(
                thickness=15,
                title="Node Connections",
                xanchor="left",
                titleside="right",
            ),
        ),
    )

    # Color nodes by number of connections
    node_adjacencies = []
    for node in G.nodes():
        node_adjacencies.append(len(list(G.neighbors(node))))

    node_trace.marker.color = node_adjacencies

    # Create the figure
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


def main():
    """Main Streamlit app."""
    st.title("Wiktionary Browser")
    st.write("Search the Wiktionary database for words and their definitions.")

    # Search interface
    st.subheader("Search")
    query = st.text_input("Enter search term:")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_type = st.radio(
            "Search in:",
            ["title", "definition", "example"],
            horizontal=True,
        )
    with col2:
        depth = st.number_input("Network depth:", min_value=1, max_value=5, value=2)

    if query:
        results = search_entries(query, search_type)

        if not results:
            st.warning("No results found.")
            return

        # Create tabs after we have results
        tab1, tab2, tab3 = st.tabs(["Search Results", "Statistics", "Word Network"])

        with tab1:
            st.write(f"Found {len(results)} results:")

            # Display results
            for entry in results:
                with st.expander(
                    f"{entry.title} ({entry.language}) - {entry.part_of_speech or 'unknown part of speech'}"
                ):
                    if entry.etymology:
                        st.write("**Etymology:**", entry.etymology)

                    st.write("**Definitions:**")
                    for sense in entry.senses:
                        st.write(f"- {sense.definition}")
                        if sense.examples:
                            st.write("  **Examples:**")
                            for example in sense.examples:
                                st.write(f"  • {example.text}")
                                if example.translation:
                                    st.write(f"    Translation: {example.translation}")

        with tab2:
            create_visualizations(results)

        with tab3:
            with Session(engine) as session:
                G = find_related_words(session, query, depth=depth)
                if len(G.nodes()) > 1:  # Only show if we found relationships
                    fig = create_network_graph(G)
                    st.plotly_chart(fig)
                else:
                    st.info("No word relationships found in the database.")


if __name__ == "__main__":
    main()
