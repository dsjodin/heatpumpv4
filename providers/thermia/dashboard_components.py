"""
Thermia-Specific Dashboard Components
UI components unique to Thermia Diplomat heat pumps
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def create_thermia_specific_section():
    """
    Create Thermia-specific dashboard section

    Thermia-specific features:
    - Variable speed pumps (circulation, brine)
    - Operating mode selection
    - Cooling (if installed)
    - Pressure tube temperature
    - Power consumption monitoring
    """
    return dbc.Card([
        dbc.CardBody([
            html.H4("Thermia-Specifika Funktioner", className="card-title mb-4"),

            dbc.Row([
                # Pump Speeds
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Pumpvarvtal", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Cirkulationspump: "),
                                    html.Span(id="thermia-circulation-pump-speed", className="text-info")
                                ]),
                                html.P([
                                    html.Strong("Köldbärarpump: "),
                                    html.Span(id="thermia-brine-pump-speed", className="text-info")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),

                # Operating Mode
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Driftläge", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Aktuellt läge: "),
                                    html.Span(id="thermia-operating-mode", className="text-success")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),

                # Power Consumption
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Effektförbrukning", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Aktuell: "),
                                    html.Span(id="thermia-power-current", className="text-warning")
                                ]),
                                html.P([
                                    html.Strong("Ackumulerad: "),
                                    html.Span(id="thermia-energy-accumulated", className="text-warning")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=4),
            ], className="mb-3"),

            dbc.Row([
                # Pressure Tube Temp
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Tryckrörstemperatur", className="text-muted mb-3"),
                            html.P([
                                html.Strong("Temperatur: "),
                                html.Span(id="thermia-pressure-tube-temp", className="text-info")
                            ])
                        ])
                    ], className="h-100")
                ], md=6),

                # Cooling (if installed)
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Kyla (om installerad)", className="text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Temperatur: "),
                                    html.Span(id="thermia-cooling-temp", className="text-primary")
                                ]),
                                html.P([
                                    html.Strong("Börvärde: "),
                                    html.Span(id="thermia-cooling-setpoint", className="text-primary")
                                ])
                            ])
                        ])
                    ], className="h-100")
                ], md=6),
            ])
        ])
    ], className="mb-4")


# Helper function to format operating mode
def get_operating_mode_text(mode_value):
    """Convert operating mode value to Swedish text"""
    modes = {
        0: "Alla av",
        1: "Auto",
        2: "Normal",
        3: "Endast tillsattsvärme",
        4: "Endast varmvatten"
    }
    return modes.get(int(mode_value), f"Okänt läge ({mode_value})")
