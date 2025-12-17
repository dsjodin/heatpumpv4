"""
IVT-Specific Callbacks
Callbacks for IVT brand-specific dashboard components
"""

from dash import Input, Output
from typing import Any


def register_ivt_callbacks(app, data_query):
    """
    Register all IVT-specific callbacks

    Args:
        app: Dash app instance
        data_query: HeatPumpDataQuery instance
    """

    @app.callback(
        [
            Output('ivt-heat-carrier-forward', 'children'),
            Output('ivt-heat-carrier-return', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_ivt_heat_carrier(n):
        """Update IVT internal heat carrier temperatures"""
        try:
            latest = data_query.get_latest_values()

            # Heat carrier forward
            forward = latest.get('heat_carrier_forward', {}).get('value')
            forward_text = f"{forward:.1f} °C" if forward is not None and forward > -40 else "N/A"

            # Heat carrier return
            ret = latest.get('heat_carrier_return', {}).get('value')
            ret_text = f"{ret:.1f} °C" if ret is not None and ret > -40 else "N/A"

            return forward_text, ret_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        [
            Output('ivt-hot-water-top', 'children'),
            Output('ivt-hot-water-mid', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_ivt_hot_water(n):
        """Update IVT hot water sensor temperatures"""
        try:
            latest = data_query.get_latest_values()

            # Hot water top (Tank 1)
            top = latest.get('hot_water_top', {}).get('value')
            top_text = f"{top:.1f} °C" if top is not None and top > -40 else "Ej installerad"

            # Hot water mid (Tank 2)
            mid = latest.get('warm_water_2_mid', {}).get('value')
            mid_text = f"{mid:.1f} °C" if mid is not None and mid > -40 else "Ej installerad"

            return top_text, mid_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        Output('ivt-hot-gas-temp', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_ivt_hot_gas(n):
        """Update IVT hot gas temperature"""
        try:
            latest = data_query.get_latest_values()
            temp = latest.get('hot_gas_compressor', {}).get('value')

            if temp is not None and temp > -40:
                return f"{temp:.1f} °C"
            else:
                return "N/A"

        except Exception as e:
            return "N/A"

    @app.callback(
        [
            Output('ivt-aux-step1', 'children'),
            Output('ivt-aux-step2', 'children'),
            Output('ivt-aux-percent', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_ivt_auxiliary_heat(n):
        """Update IVT auxiliary heater steps and percentage"""
        try:
            latest = data_query.get_latest_values()

            # Step 1 (3kW)
            step1 = latest.get('add_heat_step_1', {}).get('value', 0)
            step1_text = "PÅ" if step1 > 0 else "AV"

            # Step 2 (6kW)
            step2 = latest.get('add_heat_step_2', {}).get('value', 0)
            step2_text = "PÅ" if step2 > 0 else "AV"

            # Total percentage
            percent = latest.get('additional_heat_percent', {}).get('value', 0)
            percent_text = f"{percent:.0f}%" if percent is not None else "0%"

            return step1_text, step2_text, percent_text

        except Exception as e:
            return "AV", "AV", "0%"

    @app.callback(
        [
            Output('ivt-runtime-comp-heating', 'children'),
            Output('ivt-runtime-comp-hotwater', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_ivt_runtime(n):
        """Update IVT runtime split (heating/hotwater)"""
        try:
            latest = data_query.get_latest_values()

            # Compressor heating runtime
            heating = latest.get('compressor_runtime_heating', {}).get('value', 0)
            heating_text = f"{heating:.0f} h" if heating is not None else "N/A"

            # Compressor hotwater runtime
            hotwater = latest.get('compressor_runtime_hotwater', {}).get('value', 0)
            hotwater_text = f"{hotwater:.0f} h" if hotwater is not None else "N/A"

            return heating_text, hotwater_text

        except Exception as e:
            return "N/A", "N/A"

    @app.callback(
        [
            Output('ivt-holiday-mode', 'children'),
            Output('ivt-summer-mode', 'children'),
        ],
        Input('interval-component', 'n_intervals')
    )
    def update_ivt_special_modes(n):
        """Update IVT special modes (holiday, summer)"""
        try:
            latest = data_query.get_latest_values()

            # Holiday mode (hours remaining)
            holiday = latest.get('holiday_mode', {}).get('value', 0)
            if holiday is not None and holiday > 0:
                days = holiday / 24
                holiday_text = f"Aktivt ({days:.1f} dagar kvar)"
            else:
                holiday_text = "Inaktivt"

            # Summer mode temperature setting
            summer = latest.get('summer_mode_temp', {}).get('value')
            if summer is not None:
                summer_text = f"{summer:.1f} °C"
            else:
                summer_text = "N/A"

            return holiday_text, summer_text

        except Exception as e:
            return "N/A", "N/A"
