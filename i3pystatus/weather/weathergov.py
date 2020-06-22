import json
import requests
import logging
from datetime import datetime

from i3pystatus.core.util import internet, require
from i3pystatus.weather import WeatherBackend


class WeathergovParser():
    '''
    Obtain weather.gov API data.
    '''

    def __init__(self, logger):
        self.logger = logger
        super(WeathergovParser, self).__init__()

    def get_weather_data(self, url):
        self.logger.debug(f'Making request to {url} to retrieve current weather data')
        self.weather_data = None

        headers = {
            'Accept': 'application/geo+json',
            'User-Agent': '(i3pystatus.weather.Weathergov)'
        }

        try:
            r = requests.get(url, headers=headers)

            if r.status_code != 200:
                self.logger.debug(f'Bad request response.')
                return self.weather_data
            else:
                self.weather_data = self.load_json(r.content)
                return self.weather_data

        except Exception:
            self.logger.exception(
                'Exception raised while attempting to get weather data',
                exc_info=True
            )

    def load_json(self, json_input):
        self.logger.debug(f'Loading the following data as JSON: {json_input}')
        try:
            return json.loads(json_input)
        except json.decoder.JSONDecodeError as exc:
            self.logger.debug(f'Error loading JSON: {exc}')
            self.logger.debug(f'String that failed to load: {json_input}')
        return None


class Weathergov(WeatherBackend):
    '''
    This module gets the weather from weather.gov. The ``station_code``
    parameter should be set to the station code from weather.gov. To
    obtain this code, search for your location on weather.gov and look
    at the "Current Conditions" box -- the local station will be listed,
    with the station code in parenthesis after the name (e.g. ``KNYC``).

    .. _weather-usage-weathergov:

    .. rubric:: Usage example

    .. code-block:: python

        from i3pystatus import Status
        from i3pystatus.weather import weathergov

        status = Status(logfile='/home/username/var/i3pystatus.log')

        status.register(
            'weather',
            format='{condition} {current_temp}{temp_unit}[ {icon}][ Hi: {high_temp}][ Lo: {low_temp}][ {update_error}]',
            interval=900,
            colorize=True,
            hints={'markup': 'pango'},
            backend=weathergov.Weathergov(
                station_code='KNYC',
                units='imperial',
                update_error='<span color="#ff000">!</span>',
            ),
        )

        status.run()

    See :ref:`here <weather-formatters>` for a list of formatters which can be
    used.

    '''
    settings = (
        ('station_code', 'Station code from weather.gov'),
        ('units', '\'metric\' or \'imperial\''),
        ('update_error', 'Value for the ``{update_error}`` formatter when an '
                         'error is encountered while checking weather data'),
    )
    required = ('location_code',)

    location_code = None
    units = 'metric'
    update_error = '!'

    url_template = 'https://api.weather.gov/stations/{station_code}/observations/latest?require_qc=false'

    # This will be set in the init based on the passed location code
    forecast_url = None

    def init(self):
        if self.location_code is not None:
            # Ensure that the location code is a string
            self.location_code = str(self.location_code)

        self.forecast_url = self.url_template.format(**vars(self))
        self.parser = WeathergovParser(self.logger)

    def toFahrenheit(self, value):
        return (value * 1.8) + 32

    @require(internet)
    def check_weather(self):
        '''
        Fetches the current weather from api.weather.gov service.
        '''

        if self.units not in ('imperial', 'metric'):
            self.logger.error(
                'Units must be one of (imperial, metric)! See the '
                'documentation for more information.'
            )
            self.data['update_error'] = self.update_error
            return
        self.data['update_error'] = ''

        if self.location_code is None:
            self.logger.error(
                'A location_code is required to check weather.gov. See the '
                'documentation for more information.'
            )
            self.data['update_error'] = self.update_error
            return
        self.data['update_error'] = ''

        try:
            self.parser.get_weather_data(self.forecast_url)
            if self.parser.weather_data is None:
                self.logger.error(
                    'Failed to read weather data from page. Run module with '
                    'debug logging to get more information.'
                )
                self.data['update_error'] = self.update_error
                return

            try:
                observed = self.parser.weather_data['properties']
            except KeyError:
                self.logger.error(
                    'Failed to retrieve current conditions from API response. '
                    'Run module with debug logging to get more information.'
                )
                self.data['update_error'] = self.update_error
                return

            # TODO: get station data from station API endpoint

            try:
                observation_time = datetime.fromisoformat(observed.get('timestamp', ''))
            except Exception:
                pass

            current_tempC = observed.get('temperature', {}).get('value')

            high_tempC = 0 # TODO: get high temp from forecast API

            low_tempC = 0 # TODO: get low temp from forecast API

            dewpointC = observed.get('dewpoint', {}).get('value')

            # Get the compass wind direction from degrees
            directions = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"}
            wind_deg = observed.get('windDirection', {}).get('value')
            wind_index = round((wind_deg % 360) / 45)
            wind_direction = directions[wind_index]

            wind_speedKPH = observed.get('windSpeed', {}).get('value')

            wind_gustKPH = observed.get('windGust', {}).get('value')

            pressurePa = observed.get('barometricPressure', {}).get('value')

            visibilityM = observed.get('visibility', {}).get('value')

            heat_indexC = observed.get('heatIndex', {}).get('value')

            if self.units == 'imperial':
                current_temp = self.toFahrenheit(current_tempC)
                high_temp = self.toFahrenheit(high_tempC)
                low_temp = self.toFahrenheit(low_tempC)
                dewpoint = self.toFahrenheit(dewpointC)
                heat_index = self.toFahrenheit(heat_indexC)
                temp_unit = '°F'
                wind_speed = round(wind_speedKPH / 1.609)
                if wind_gustKPH != None:
                    wind_gust = round(wind_gustKPH / 1.609)
                wind_unit = 'mph'
                pressure = round(pressurePa / 3386)
                pressure_unit = 'in'
                visibility = round(visibilityM / 1609)
                visibility_unit = 'mi'
            else:
                current_temp = current_tempC
                high_temp = high_tempC
                low_temp = low_tempC
                dewpoint = dewpointC
                heat_index = round(heat_indexC, 1)
                temp_unit = '°C'
                wind_speed = round(wind_speedKPH)
                if wind_gustKPH != None:
                    wind_gust = round(wind_gustKPH)
                wind_unit = 'kph'
                pressure = round(pressurePa / 100)
                pressure_unit = 'mb'
                visibility = round(visibilityM / 1000)
                visibility_unit = 'km'

            # self.data['city'] = TODO: get city data (station info API)
            self.data['text_description'] = str(observed.get('textDescription'))
            self.data['observation_time'] = observation_time
            self.data['current_temp'] = str(current_temp)
            self.data['high_temp'] = str(high_temp)
            self.data['low_temp'] = str(low_temp)
            self.data['dewpoint'] = str(dewpoint)
            self.data['temp_unit'] = temp_unit
            self.data['wind_direction'] = wind_direction
            self.data['wind_speed'] = str(wind_speed)
            if wind_gustKPH == None:
                self.data['wind_gust'] = ''
            else:
                self.data['wind_gust'] = str(wind_gust)
            self.data['wind_unit'] = wind_unit
            self.data['pressure'] = str(pressure)
            self.data['pressure_unit'] = pressure_unit
            self.data['visibility'] = str(visibility)
            self.data['visibility_unit'] = visibility_unit
            self.data['humidity'] = str(round(observed.get('relativeHumidity', {}).get('value'))) + '%'
            self.data['heat_index'] = str(heat_index)
            
        except Exception:
            # Don't let an uncaught exception kill the update thread
            self.logger.error(
                'Uncaught error occurred while checking weather. '
                'Exception follows: ', exc_info=True
            )
            self.data['update_error'] = self.update_error
