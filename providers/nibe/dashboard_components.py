"""
NIBE-Specific Dashboard Components
Brand-specific UI components for NIBE Fighter/Supreme heat pumps
"""

from dash import html
import dash_bootstrap_components as dbc


def create_nibe_specific_section():
    """
    Create NIBE-specific dashboard section

    Returns NIBE-specific components including:
    - Degree Minutes (Gradminuter) - unique NIBE feature
    - Smart Home mode indicator
    - Compressor frequency (inverter models)
    - Hot gas temperature (BT12)
    - Calculated supply temperature
    - Runtime split (heating/hotwater)
    - Heat curve settings
    """

    return dbc.Container([
        # Section header
        dbc.Row([
            dbc.Col([
                html.H4("🔧 NIBE-Specifika Mätningar", className="mb-3"),
            ])
        ]),

        # Row 1: Degree Minutes & Smart Home
        dbc.Row([
            # Degree Minutes card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Gradminuter (DM)"),
                    dbc.CardBody([
                        html.H3(id='nibe-degree-minutes', className="text-center"),
                        html.P("NIBE:s värmereglering", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),

            # Warm Water Program card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Varmvattenprogram"),
                    dbc.CardBody([
                        html.H3(id='nibe-smart-home-mode', className="text-center"),
                        html.P("Eco/Normal/Luxury/Smart", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),
        ]),

        # Row 2: Compressor Frequency & Hot Gas Temperature
        dbc.Row([
            # Compressor Speed card (variable speed models)
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Kompressor Hastighet"),
                    dbc.CardBody([
                        html.H3(id='nibe-compressor-frequency', className="text-center"),
                        html.P("Variabel hastighet (%)", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),

            # Hot Gas Temperature card (BT12)
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Hetgas Temperatur (BT12)"),
                    dbc.CardBody([
                        html.H3(id='nibe-hot-gas-temp', className="text-center"),
                        html.P("Kompressor utgång", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),
        ]),

        # Row 3: Calculated Supply & Compressor Current
        dbc.Row([
            # Heat Carrier Forward Temperature card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Intern Värmebärare Framledning (BT2)"),
                    dbc.CardBody([
                        html.H3(id='nibe-calculated-supply', className="text-center"),
                        html.P("HP intern värmebärare", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),

            # Total Current card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Total Ström (L1+L2+L3)"),
                    dbc.CardBody([
                        html.H3(id='nibe-compressor-current', className="text-center"),
                        html.P("Aktuell strömförbrukning", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),
        ]),

        # Row 4: Energy Usage Split
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("⚡ Tillförd Energi (Uppdelad)"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.P("Total energi:", className="mb-1"),
                                html.H5(id='nibe-runtime-comp-heating', className="text-primary")
                            ], width=6),
                            dbc.Col([
                                html.P("Varmvatten energi:", className="mb-1"),
                                html.H5(id='nibe-runtime-comp-hotwater', className="text-primary")
                            ], width=6),
                        ]),
                    ])
                ], className="mb-3")
            ], width=12),
        ]),

        # Row 5: Heat Curve Settings
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📈 Värmekurva Inställningar"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.P("Kurva:", className="mb-1"),
                                html.H5(id='nibe-heat-curve', className="text-info")
                            ], width=6),
                            dbc.Col([
                                html.P("Offset (parallellförskjutning):", className="mb-1"),
                                html.H5(id='nibe-heat-curve-offset', className="text-info")
                            ], width=6),
                        ]),
                    ])
                ], className="mb-3")
            ], width=12),
        ]),

        # Row 6: Pump Status
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("💨 Pumpstatus"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.P("Intern cirkulationspump:", className="mb-1"),
                                html.H5(id='nibe-circulation-pump-speed', className="text-success")
                            ], width=6),
                            dbc.Col([
                                html.P("Köldbärarpump (LW only):", className="mb-1"),
                                html.H5(id='nibe-brine-pump-speed', className="text-success")
                            ], width=6),
                        ]),
                    ])
                ], className="mb-3")
            ], width=12),
        ]),

        # Row 7: Operating Mode & Holiday Mode
        dbc.Row([
            # Operating Mode card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Driftläge"),
                    dbc.CardBody([
                        html.H3(id='nibe-operating-mode', className="text-center"),
                        html.P("Aktuellt läge", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),

            # Pool Mode card
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Poolläge"),
                    dbc.CardBody([
                        html.H3(id='nibe-holiday-mode', className="text-center"),
                        html.P("Pool värme status", className="text-muted text-center mb-0")
                    ])
                ], className="mb-3")
            ], width=12, lg=6),
        ]),

    ], fluid=True, className="mt-4")
