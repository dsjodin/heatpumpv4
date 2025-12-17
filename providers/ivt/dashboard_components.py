"""
IVT-Specific Dashboard Components
UI components unique to IVT Greenline heat pumps
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def create_ivt_specific_section():
    """
    Create IVT-specific dashboard section

    IVT-specific features:
    - Internal heat carrier temperatures
    - Dual hot water sensors (internal + external tank)
    - Hot gas temperature
    - Auxiliary heat steps (3kW + 6kW)
    - Runtime split (heating/hotwater)
    - Holiday/Summer/Extra hot water modes
    """
    return dbc.Card([
        dbc.CardBody([
            html.H4("IVT-Specifika Funktioner", className="card-title mb-4"),

            dbc.Row([
                # Internal Heat Carrier
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Intern Värmebärare", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Framledning: "),
                                    html.Span(id="ivt-heat-carrier-forward", className="text-danger")
                                ]),
                                html.P([
                                    html.Strong("Retur: "),
                                    html.Span(id="ivt-heat-carrier-return", className="text-info")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),

                # Hot Water Sensors
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Varmvatten Sensorer", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("VV Tank 1 (topp): "),
                                    html.Span(id="ivt-hot-water-top", className="text-warning")
                                ]),
                                html.P([
                                    html.Strong("VV Tank 2 (mitten): "),
                                    html.Span(id="ivt-hot-water-mid", className="text-warning")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),

                # Hot Gas Temp
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Hetgas", className="text-muted mb-3"),
                            html.P([
                                html.Strong("Temperatur: "),
                                html.Span(id="ivt-hot-gas-temp", className="text-danger")
                            ])
                        ])
                    ], className="h-100")
                ], md=4),
            ], className="mb-3"),

            dbc.Row([
                # Auxiliary Heat Steps
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Tillsatsvärme Steg", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Steg 1 (3kW): "),
                                    html.Span(id="ivt-aux-step1", className="text-warning")
                                ]),
                                html.P([
                                    html.Strong("Steg 2 (6kW): "),
                                    html.Span(id="ivt-aux-step2", className="text-warning")
                                ]),
                                html.P([
                                    html.Strong("Total (%): "),
                                    html.Span(id="ivt-aux-percent", className="text-warning")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),

                # Runtime Split
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Drifttid Uppdelning", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Komp. uppvärmning: "),
                                    html.Span(id="ivt-runtime-comp-heating", className="text-info")
                                ]),
                                html.P([
                                    html.Strong("Komp. varmvatten: "),
                                    html.Span(id="ivt-runtime-comp-hotwater", className="text-info")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),

                # Special Modes
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Speciallägen", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Semesterläge: "),
                                    html.Span(id="ivt-holiday-mode", className="text-success")
                                ]),
                                html.P([
                                    html.Strong("Sommarläge: "),
                                    html.Span(id="ivt-summer-mode", className="text-success")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),
            ])
        ])
    ], className="mb-4")


# Helper functions
def format_status(value):
    """Format status value (0/1) to Swedish text"""
    return "PÅ" if value > 0 else "AV"


def format_temperature(value):
    """Format temperature value"""
    if value is None or value < -40:
        return "Ej installerad"
    return f"{value:.1f} °C"


def format_runtime_hours(hours):
    """Format runtime hours"""
    if hours is None:
        return "N/A"
    return f"{hours:.0f} h"
