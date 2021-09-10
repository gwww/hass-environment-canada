"""The Environment Canada (EC) component."""
from datetime import timedelta
import logging
from random import randrange
from homeassistant.util.dt import utcnow

import env_canada

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
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
    ATTR_OBSERVATION_TIME,
    ATTR_STATION,
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
)

PLATFORMS = ["sensor", "weather"]

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
ATTRIBUTION_EN = "Data provided by Environment Canada"
ATTRIBUTION_FR = "Données fournies par Environnement Canada"

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

    def __init__(self, hass, config):
        """Initialize global EC data updater."""
        self.weather = ECWeatherData(config)
        self.weather.init_env_canada()

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        """Fetch data from EC."""
        try:
            return await self.weather.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err


class ECWeatherData:
    """Keep data for EC weather entities."""

    def __init__(self, config):
        """Initialise the weather entity data."""
        self._config = config
        self._weather_data = None

        self.conditions = None
        self.daily_forecast = None
        self.hourly_forecast = None
        self.alerts = None
        self.metadata = None

    def init_env_canada(self):
        """Weather data inialization - set the coordinates."""
        latitude = self._config.data.get(CONF_LATITUDE)
        longitude = self._config.data.get(CONF_LONGITUDE)
        station = self._config.data.get(CONF_STATION)
        language = self._config.data.get(CONF_LANGUAGE)

        self._weather_data = env_canada.ECWeather(
            station_id=station,
            coordinates=(latitude, longitude),
            language=language.lower(),
        )

        return True

    async def fetch_data(self):
        """Fetch data from EC API - (current weather, alerts, and forecast)."""
        await self._weather_data.update()
        self.conditions = self._weather_data.conditions
        self.daily_forecast = self._weather_data.daily_forecasts
        self.hourly_forecast = self._weather_data.hourly_forecasts
        self.alerts = self._weather_data.alerts
        self.metadata = self._weather_data.metadata
        return self


class ECBaseEntity:
    """Common base for EC weather."""
    def __init__(self, coordinator, config, name):
        """Initialise the base for all EC entities."""
        self._coordinator = coordinator
        self._config = config
        self._name = name

    def get_value(self, key):
        """Get the value for a weather attribute."""
        value = self._coordinator.data.conditions.get(key, {}).get("value")
        if value:
            return value
        return self._coordinator.data.hourly_forecast[0].get(key)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def attribution(self):
        """Return the attribution."""
        return (
            ATTRIBUTION_EN
            if self._config[CONF_LANGUAGE] == "English"
            else ATTRIBUTION_FR
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_ATTRIBUTION: self.attribution,
            ATTR_OBSERVATION_TIME: self._coordinator.data.metadata.get("timestamp"),
            ATTR_LOCATION: self._coordinator.data.metadata.get("location"),
            ATTR_STATION: self._coordinator.data.metadata.get("station"),
        }

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN,)},
            "manufacturer": "Environment Canada",
            "model": "Weather",
            "default_name": "Weather",
            "entry_type": "service",
        }
