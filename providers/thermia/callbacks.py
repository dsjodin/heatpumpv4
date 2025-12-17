"""
Thermia-Specific Callbacks
Callbacks for Thermia brand-specific dashboard components
"""

from dash import Input, Output
from typing import Any


def register_thermia_callbacks(app, data_query):
    """
    Register all Thermia-specific callbacks

    Args:
        app: Dash app instance
        data_query: HeatPumpDataQuery instance
    """

    @app.callback(
        [
            Output('thermia-circulation-pump-speed', 'children'),
            Output('thermia-brine-pump-speed', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_thermia_pump_speeds(n):
        """Update Thermia variable speed pump displays"""
        try:
            latest = data_query.get_latest_values()

            # Circulation pump speed
            circ_speed = latest.get('circulation_pump_speed', {}).get('value', 0)
            circ_text = f"{circ_speed:.0f}%" if circ_speed is not None else "N/A"

            # Brine pump speed
            brine_speed = latest.get('brine_pump_speed', {}).get('value', 0)
            brine_text = f"{brine_speed:.0f}%" if brine_speed is not None else "N/A"

            return circ_text, brine_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        Output('thermia-operating-mode', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_thermia_operating_mode(n):
        """Update Thermia operating mode display"""
        try:
            latest = data_query.get_latest_values()
            mode_value = latest.get('operating_mode', {}).get('value', 0)

            modes = {
                0: "Alla av",
                1: "Auto",
                2: "Normal",
                3: "Endast tillsattsvärme",
                4: "Endast varmvatten"
            }

            mode_text = modes.get(int(mode_value), f"Okänt läge ({mode_value})")
            return mode_text

        except Exception as e:
            return "N/A"

    @app.callback(
        [
            Output('thermia-power-current', 'children'),
            Output('thermia-energy-accumulated', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_thermia_power(n):
        """Update Thermia power consumption displays"""
        try:
            latest = data_query.get_latest_values()

            # Current power
            power = latest.get('power_consumption', {}).get('value', 0)
            power_text = f"{power:.0f} W" if power is not None else "N/A"

            # Accumulated energy
            energy = latest.get('energy_accumulated', {}).get('value', 0)
            energy_text = f"{energy:.1f} kWh" if energy is not None else "N/A"

            return power_text, energy_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        Output('thermia-pressure-tube-temp', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_thermia_pressure_tube(n):
        """Update Thermia pressure tube temperature"""
        try:
            latest = data_query.get_latest_values()
            temp = latest.get('pressure_tube_temp', {}).get('value')

            if temp is not None and temp > -40:
                return f"{temp:.1f} °C"
            else:
                return "Ej installerad"

        except Exception as e:
            return "N/A"

    @app.callback(
        [
            Output('thermia-cooling-temp', 'children'),
            Output('thermia-cooling-setpoint', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_thermia_cooling(n):
        """Update Thermia cooling information"""
        try:
            latest = data_query.get_latest_values()

            # Cooling temperature
            temp = latest.get('cooling_temp', {}).get('value')
            if temp is not None and temp > -40:
                temp_text = f"{temp:.1f} °C"
            else:
                temp_text = "Ej installerad"

            # Cooling setpoint
            setpoint = latest.get('cooling_setpoint', {}).get('value')
            if setpoint is not None and setpoint > -40:
                setpoint_text = f"{setpoint:.1f} °C"
            else:
                setpoint_text = "Ej installerad"

            return temp_text, setpoint_text

        except Exception as e:
            return "N/A", "N/A"
