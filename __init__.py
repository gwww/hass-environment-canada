"""The Environment Canada (EC) component."""
from datetime import timedelta
import logging

from env_canada import ECWeather, ECRadar, ECAirQuality

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
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import utcnow
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION_EN,
    ATTRIBUTION_FR,
    ATTR_OBSERVATION_TIME,
    ATTR_STATION,
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
)

PLATFORMS = ["camera", "sensor", "weather"]

DEFAULT_WEATHER_UPDATE_INTERVAL = timedelta(minutes=15)
DEFAULT_RADAR_UPDATE_INTERVAL = timedelta(minutes=15)

_LOGGER = logging.getLogger(__name__)


class MyECRadar(ECRadar):
    """Slim wrapper to add update method."""

    def __init__(self, coordinates):
        """Init my radar."""
        super().__init__(coordinates=coordinates, precip_type=None)
        self.image = None

    async def update(self):
        self.image = await self.get_loop(fps=2)


async def async_setup_entry(hass, config_entry):
    """Set up EC as config entry."""
    lat = config_entry.data.get(CONF_LATITUDE)
    lon = config_entry.data.get(CONF_LONGITUDE)
    station = config_entry.data.get(CONF_STATION)
    lang = config_entry.data.get(CONF_LANGUAGE)

    weather_data = ECWeather(
        station_id=station,
        coordinates=(lat, lon),
        language=lang.lower(),
    )
    weather_coord = ECDataUpdateCoordinator(
        hass, weather_data, "weather", DEFAULT_WEATHER_UPDATE_INTERVAL
    )
    await weather_coord.async_config_entry_first_refresh()

    radar_data = MyECRadar(coordinates=(lat, lon))
    radar_coord = ECDataUpdateCoordinator(
        hass, radar_data, "radar", DEFAULT_RADAR_UPDATE_INTERVAL
    )
    await radar_coord.async_config_entry_first_refresh()

    aqhi_data = ECAirQuality(coordinates=(lat, lon))
    aqhi_coord = ECDataUpdateCoordinator(
        hass, aqhi_data, "AQHI", DEFAULT_WEATHER_UPDATE_INTERVAL
    )
    await aqhi_coord.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "weather_coordinator": weather_coord,
        "radar_coordinator": radar_coord,
        "aqhi_coordinator": aqhi_coord,
    }

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

    def __init__(self, hass, ec_data, name, update_interval):
        """Initialize global EC data updater."""
        self.ec_data = ec_data
        self._name = name

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        """Fetch data from EC."""
        try:
            await self.ec_data.update()
        except Exception as err:
            raise ECUpdateFailed(
                f"Environment Canada {self._name} update failed: {err}"
            ) from err
        return self.ec_data


class ECBaseEntity(CoordinatorEntity):
    """Common base for EC weather."""

    def __init__(self, coordinator, config, name):
        """Initialise the base for all EC entities."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._config = config
        self._name = name

    def get_value(self, key):
        """Get the value for a weather attribute."""
        value = self._coordinator.data.conditions.get(key, {}).get("value")
        if value:
            return value
        return self._coordinator.data.hourly_forecasts[0].get(key)

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
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # return True  # FIX ME
        return False

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


class ECUpdateFailed(Exception):
    """Raised when an update fails to get data from Environment Canada."""
