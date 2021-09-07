"""The Environment Canada (EC) component."""
from datetime import timedelta
import logging
from random import randrange
from homeassistant.util.dt import utcnow

import env_canada

from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    EVENT_CORE_CONFIG_UPDATE,
    LENGTH_FEET,
    LENGTH_METERS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.distance import convert as convert_distance
import homeassistant.util.dt as dt_util

from .const import (
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
)

PLATFORMS = ["sensor", "weather"]

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
STALE_OBSERVATION = timedelta(minutes=20)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry):
    """Set up EC as config entry."""
    coordinator = ECDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class ECDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching EC data."""

    def __init__(self, hass, config_entry):
        """Initialize global EC data updater."""
        self.weather = ECWeatherData(
            hass, config_entry.data, hass.config.units.is_metric
        )
        self.weather.init_env_canada()

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )
        self._last_update_success_time = None

    async def _async_update_data(self):
        """Fetch data from EC."""
        try:
            ret = await self.weather.fetch_data()
            self._last_update_success_time = utcnow()
            return ret
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    def stale_observation(self):
        """Returns is the latest observation is older than refresh time."""
        stale = True
        if self._last_update_success_time:
            stale = (utcnow() - self._last_update_success_time > STALE_OBSERVATION)
        return stale


class ECWeatherData:
    """Keep data for EC weather entities."""

    def __init__(self, hass, config, is_metric):
        """Initialise the weather entity data."""
        self.hass = hass
        self._config = config
        self._is_metric = is_metric
        self._weather_data = None
        self.conditions = None
        self.daily_forecast = None
        self.hourly_forecast = None
        self.alerts = None

    def init_env_canada(self):
        """Weather data inialization - set the coordinates."""
        latitude = self._config[CONF_LATITUDE]
        longitude = self._config[CONF_LONGITUDE]
        station = self._config[CONF_STATION]
        language = self._config[CONF_LANGUAGE]

        self._weather_data = env_canada.ECWeather(
            station_id=station,
            coordinates=(latitude, longitude),
            language=language.lower(),
        )

        return True

    async def fetch_data(self):
        """Fetch data from API - (current weather and forecast)."""
        await self._weather_data.update()
        self.conditions = self._weather_data.conditions
        self.daily_forecast = self._weather_data.daily_forecasts
        self.hourly_forecast = self._weather_data.hourly_forecasts
        self.alerts = self._weather_data.alerts
        return self
