"""
NIBE-Specific Callbacks
Callbacks for NIBE brand-specific dashboard components
"""

from dash import Input, Output
from typing import Any


def register_nibe_callbacks(app, data_query):
    """
    Register all NIBE-specific callbacks

    Args:
        app: Dash app instance
        data_query: HeatPumpDataQuery instance
    """

    @app.callback(
        Output('nibe-degree-minutes', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_degree_minutes(n):
        """Update NIBE degree minutes display"""
        try:
            latest = data_query.get_latest_values()
            # Try both compressor and integral degree minutes
            dm = latest.get('degree_minutes_compressor', {}).get('value')
            if dm is None:
                dm = latest.get('degree_minutes_integral', {}).get('value')

            if dm is not None:
                # Degree minutes are typically negative (heating needed) or positive (cooling needed)
                return f"{dm:.0f} DM"
            else:
                return "N/A"

        except Exception as e:
            return "N/A"

    @app.callback(
        Output('nibe-smart-home-mode', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_smart_home_mode(n):
        """Update NIBE warm water program display"""
        try:
            latest = data_query.get_latest_values()
            mode = latest.get('warm_water_program', {}).get('value')

            modes = {
                0: "Eco",
                1: "Normal",
                2: "Luxury",
                4: "Smart",
            }

            if mode is not None:
                return modes.get(int(mode), f"Läge {mode}")
            else:
                return "Ej aktivt"

        except Exception as e:
            return "N/A"

    @app.callback(
        Output('nibe-compressor-frequency', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_compressor_frequency(n):
        """Update NIBE compressor speed (variable speed models)"""
        try:
            latest = data_query.get_latest_values()
            speed = latest.get('compressor_speed', {}).get('value')

            if speed is not None and speed > 0:
                return f"{speed:.0f}%"
            else:
                return "Ej variabel"

        except Exception as e:
            return "N/A"

    @app.callback(
        Output('nibe-hot-gas-temp', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_hot_gas(n):
        """Update NIBE hot gas temperature (BT12)"""
        try:
            latest = data_query.get_latest_values()
            temp = latest.get('hot_gas_temp', {}).get('value')

            if temp is not None and temp > -40:
                return f"{temp:.1f} °C"
            else:
                return "N/A"

        except Exception as e:
            return "N/A"

    @app.callback(
        Output('nibe-calculated-supply', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_calculated_supply(n):
        """Update NIBE heat carrier forward temperature"""
        try:
            latest = data_query.get_latest_values()
            temp = latest.get('heat_carrier_forward', {}).get('value')

            if temp is not None and temp > -40:
                return f"{temp:.1f} °C"
            else:
                return "N/A"

        except Exception as e:
            return "N/A"

    @app.callback(
        Output('nibe-compressor-current', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_compressor_current(n):
        """Update NIBE total current (3-phase sum)"""
        try:
            latest = data_query.get_latest_values()
            l1 = latest.get('load_l1', {}).get('value', 0)
            l2 = latest.get('load_l2', {}).get('value', 0)
            l3 = latest.get('load_l3', {}).get('value', 0)

            if l1 is not None or l2 is not None or l3 is not None:
                total = (l1 or 0) + (l2 or 0) + (l3 or 0)
                return f"{total:.1f} A"
            else:
                return "N/A"

        except Exception as e:
            return "N/A"

    @app.callback(
        [
            Output('nibe-runtime-comp-heating', 'children'),
            Output('nibe-runtime-comp-hotwater', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_runtime(n):
        """Update NIBE energy usage split (heating/hotwater)"""
        try:
            latest = data_query.get_latest_values()

            # Total energy
            total = latest.get('energy_total', {}).get('value', 0)
            total_text = f"{total:.0f} kWh" if total is not None else "N/A"

            # Hot water energy
            hotwater = latest.get('energy_hotwater', {}).get('value', 0)
            hotwater_text = f"{hotwater:.0f} kWh" if hotwater is not None else "N/A"

            return total_text, hotwater_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        [
            Output('nibe-heat-curve', 'children'),
            Output('nibe-heat-curve-offset', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_heat_curve(n):
        """Update NIBE heat curve settings"""
        try:
            latest = data_query.get_latest_values()

            # Heat curve
            curve = latest.get('heating_curve', {}).get('value')
            curve_text = f"{curve:.1f}" if curve is not None else "N/A"

            # Heat curve offset
            offset = latest.get('heating_curve_offset', {}).get('value')
            offset_text = f"{offset:.1f} °C" if offset is not None else "N/A"

            return curve_text, offset_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        [
            Output('nibe-circulation-pump-speed', 'children'),
            Output('nibe-brine-pump-speed', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_pump_speeds(n):
        """Update NIBE pump statuses"""
        try:
            latest = data_query.get_latest_values()

            # Circulation pump status
            circ_status = latest.get('radiator_pump_status', {}).get('value', 0)
            circ_text = "På" if circ_status == 1 else "Av"

            # Brine pump status
            brine_status = latest.get('brine_pump_status', {}).get('value', 0)
            brine_text = "På" if brine_status == 1 else "Av"

            return circ_text, brine_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        Output('nibe-operating-mode', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_operating_mode(n):
        """Update NIBE operating mode"""
        try:
            latest = data_query.get_latest_values()
            mode = latest.get('operating_mode', {}).get('value')

            modes = {
                0: "Auto",
                1: "Uppvärmning",
                2: "Varmvatten",
                3: "Pool",
                4: "Transfer",
                5: "Anti Frys",
                6: "Stopp",
            }

            if mode is not None:
                return modes.get(int(mode), f"Okänt ({mode})")
            else:
                return "N/A"

        except Exception as e:
            return "N/A"

    @app.callback(
        Output('nibe-holiday-mode', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_nibe_holiday_mode(n):
        """Update NIBE pool mode"""
        try:
            latest = data_query.get_latest_values()
            mode = latest.get('pool_mode', {}).get('value', 0)

            if mode == 1:
                return "Poolläge aktivt"
            else:
                return "Poolläge inaktivt"

        except Exception as e:
            return "N/A"
