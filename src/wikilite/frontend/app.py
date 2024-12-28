from pathlib import Path
from typing import List

import dash
from dash import Input, Output, State, dcc, html
import dash_bootstrap_components as dbc

from wikilite.frontend.helpers import (
    create_network_graph,
    get_examples,
    get_relationships_with_depth,
    get_unique_rel_types,
    init_client,
    search_words,
)


def get_search_settings_modal(*, rel_types: List[str]) -> dbc.Modal:
    options = [{"label": p, "value": p} for p in rel_types]
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Search Settings")),
            dbc.ModalBody(
                [
                    dbc.Form(
                        [
                            html.Div(
                                [
                                    dbc.Label("Search Limit"),
                                    dbc.Input(
                                        id="search-limit-input", type="number", value=20
                                    ),
                                    dbc.FormText(
                                        "The maximum number of search results to return",
                                        color="muted",
                                    ),
                                ],
                                className="mb-3",
                            ),
                            html.Div(
                                [
                                    dbc.Label("Relationships"),
                                    dcc.Dropdown(
                                        options=options,
                                        value=[o["value"] for o in options],
                                        id="relation-types-select",
                                        multi=True,
                                        className="form-control",
                                    ),
                                    dbc.FormText(
                                        "Filter search results by relationships",
                                        color="muted",
                                    ),
                                ],
                                className="mb-3",
                            ),
                            html.Div(
                                [
                                    dbc.Label("Network Depth"),
                                    dbc.Input(
                                        id="network-depth-input", type="number", value=1
                                    ),
                                    dbc.FormText(
                                        "The maximum depth to search for relationships",
                                        color="muted",
                                    ),
                                ],
                                className="mb-3",
                            ),
                        ]
                    ),
                ]
            ),
            dbc.ModalFooter(
                dbc.Button(
                    "Close",
                    id="search-settings-close-button",
                    className="ms-auto",
                    n_clicks=0,
                )
            ),
        ],
        id="search-settings-modal",
        is_open=False,
    )


def get_navbar(*, color_mode: str, rel_types: List[str]) -> dbc.Navbar:
    color_mode_switch = html.Span(
        [
            dbc.Label(
                html.I(className="bi bi-moon-stars-fill"),
                html_for="switch",
                className="m-0",
            ),
            dbc.Switch(
                id="switch",
                value=color_mode == "light",
                style={"margin": ".125rem", "padding-left": "2.8rem"},
                persistence=True,
            ),
            dbc.Label(
                html.I(className="bi bi-sun-fill"),
                html_for="switch",
                className="m-0",
            ),
        ],
        className="d-flex h-100 justify-content-center align-items-center",
    )
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    [
                        html.I(className="bi bi-lightbulb-fill me-2"),
                        "WikiLite",
                    ],
                    href="#",
                    className="me-2",
                ),
                dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                dbc.Collapse(
                    [
                        dbc.Nav(
                            [
                                dbc.NavItem(
                                    dbc.InputGroup(
                                        [
                                            dbc.Input(
                                                id="nav-search-input",
                                                type="text",
                                                placeholder="Search Wikipedia",
                                                className="form-control",
                                                style={"width": "40rem"},
                                            ),
                                            dbc.Button(
                                                html.I(className="bi bi-gear-fill"),
                                                id="search-settings-open-button",
                                            ),
                                            get_search_settings_modal(
                                                rel_types=rel_types
                                            ),
                                            dbc.Button(
                                                html.I(className="bi bi-search"),
                                                id="search-button",
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                            className="me-auto ms-3",
                            navbar=True,
                        ),
                        dbc.Nav(
                            [
                                dbc.NavItem(color_mode_switch, className="ms-3"),
                            ],
                            navbar=True,
                        ),
                    ],
                    is_open=False,
                    navbar=True,
                    id="navbar-collapse",
                ),
            ],
            fluid=True,
        ),
        className="navbar navbar-expand-md bg-body-tertiary mb-3",
    )


def get_layout(*, color_mode: str, rel_types: List[str]) -> List:
    """Generate the layout for the WikiLite Dash app"""
    layout = [
        get_navbar(color_mode=color_mode, rel_types=rel_types),
        html.Div(
            [
                dbc.Tabs(
                    [
                        dbc.Tab(label="Explorer", tab_id="tab-1"),
                        dbc.Tab(label="Network", tab_id="tab-2"),
                    ],
                    id="tabs",
                    active_tab="tab-1",
                    # class_name="nav nav-underline",
                    # persistence=True,
                    # persistence_type="local",
                ),
                html.Div(id="tabs-content"),
            ],
        ),
    ]
    return layout


class WikiLiteApp(dash.Dash):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "WikiLite"
        self.client = init_client()
        self.rel_types = get_unique_rel_types(self.client)
        self.layout = get_layout(color_mode="dark", rel_types=self.rel_types)
        self.register_callbacks()

    def interpolate_index(self, **kwargs):
        with open(Path(__file__).parent / "assets" / "template.html") as f:
            TEMPLATE = f.read()
        return TEMPLATE.format(
            # default_color_mode=self.default_color_mode,
            metas=kwargs["metas"],
            title=kwargs["title"],
            favicon=kwargs["favicon"],
            css=kwargs["css"],
            app_entry=kwargs["app_entry"],
            config=kwargs["config"],
            scripts=kwargs["scripts"],
            renderer=kwargs["renderer"],
        )

    def register_callbacks(self):
        self.clientside_callback(
            """
                (switchOn) => {
                document.documentElement.setAttribute("data-bs-theme", switchOn ? "light" : "dark"); 
                return window.dash_clientside.no_update
                }
                """,
            Output("switch", "id"),
            Input("switch", "value"),
        )

        @self.callback(
            Output("search-settings-modal", "is_open"),
            [
                Input("search-settings-open-button", "n_clicks"),
                Input("search-settings-close-button", "n_clicks"),
            ],
            [State("search-settings-modal", "is_open")],
        )
        def toggle_search_settings_modal(open_clicks, close_clicks, is_open):
            if open_clicks or close_clicks:
                return not is_open
            return is_open

        @self.callback(
            Output("navbar-collapse", "is_open"),
            [Input("navbar-toggler", "n_clicks")],
            [State("navbar-collapse", "is_open")],
        )
        def toggle_navbar_collapse(n, is_open):
            if n:
                return not is_open
            return is_open

        @self.callback(
            Output("tabs-content", "children"),
            Input("tabs", "active_tab"),
            Input("nav-search-input", "value"),
            Input("search-limit-input", "value"),
            Input("network-depth-input", "value"),
            Input("relation-types-select", "value"),
        )
        def render_tab_content(active_tab, query, limit, depth, rel_types):
            if active_tab == "tab-1":
                return self.get_explorer_tab(query, limit=limit)
            elif active_tab == "tab-2":
                return self.get_network_tab(
                    query, limit=limit, depth=depth, rel_types=rel_types
                )
            return html.Div("No tab selected")

    def get_explorer_tab(self, query: str | None = None, limit: int = 10):
        results = search_words(self.client, query, limit=limit) if query else []
        children = []
        for word in results:
            children.append(
                dbc.Card(
                    [
                        dbc.CardHeader(word.word),
                        dbc.CardBody(
                            [
                                html.H6("Definitions", className="card-title"),
                                html.P(word.definition),
                                html.H6("Examples", className="card-title"),
                                html.Ul(
                                    [
                                        html.Li(example.example)
                                        for example in get_examples(
                                            self.client, word.id
                                        )
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                )
            )
        return html.Div(children, id="explorer-tab", className="p-3")

    def get_network_tab(
        self,
        query: str | None = None,
        limit: int = 10,
        depth: int = 3,
        rel_types: List[str] = [],
    ):
        if query:
            word_ids = [
                word.id for word in search_words(self.client, query, limit=limit)
            ]
            relationships = []
            for word_id in word_ids:
                relationships.extend(
                    get_relationships_with_depth(
                        self.client,
                        word_id,
                        depth=depth,
                        rel_types=rel_types,
                    )
                )
            return create_network_graph(relationships)
        return html.Div("No search query provided", id="network-tab", className="p-3")


if __name__ == "__main__":
    app = WikiLiteApp(__name__)
    app.run_server(debug=True, threaded=True)
