"""Support for the Environment Canada radar imagery."""
from __future__ import annotations
import datetime

from env_canada import ECRadar
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.util import Throttle

from . import ECUpdateFailed
from .const import (
    ATTRIBUTION_EN,
    ATTRIBUTION_FR,
    ATTR_OBSERVATION_TIME,
    CONF_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
)

ATTR_UPDATED = "updated"

CONF_LOOP = "loop"
CONF_PRECIP_TYPE = "precip_type"
CONF_RADAR_TYPE = "radar_type"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)
SERVICE_SET_RADAR_TYPE = "set_radar_type"

SET_RADAR_TYPE_SCHEMA = {
    vol.Required(CONF_RADAR_TYPE, default="Auto"): vol.In(["Auto", "Rain", "Snow"])
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Environment Canada camera."""

    lat = config_entry.data.get(CONF_LATITUDE, hass.config.latitude)
    lon = config_entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    radar_object = ECRadar(
        coordinates=(lat, lon), precip_type=config_entry.data.get(CONF_PRECIP_TYPE)
    )

    async_add_entities([ECCamera(config_entry.data, radar_object)], True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_RADAR_TYPE, SET_RADAR_TYPE_SCHEMA, "async_set_radar_type"
    )


class ECCamera(Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, config, radar_object):
        """Initialize the EC camera."""
        super().__init__()

        self._radar_object = radar_object
        self._config = config
        self._name = f"{config.get(CONF_NAME, DEFAULT_NAME)} Radar"

        self.content_type = "image/gif"
        self.image = None
        self.timestamp = None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """
        Return bytes of camera image. Ignore width and height when
        the image is fetched from url. Camera component will resize it.
        """
        await self.async_update()
        return self.image

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_ATTRIBUTION: self.attribution,
            ATTR_OBSERVATION_TIME: self.timestamp,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update radar image."""
        try:
            self.image = await self._radar_object.get_loop()
        except Exception as err:
            raise ECUpdateFailed(
                f"Environment Canada Radar update failed: {err}"
            ) from err

        self.timestamp = self._radar_object.timestamp

    async def async_set_radar_type(self, radar_type):
        """Set the type of radar to display."""
        self._radar_object.precip_type = radar_type.lower()
        await self.async_update(no_throttle=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        # The combination of coords and language are unique for all EC weather reporting
        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}-{self._config[CONF_LANGUAGE]}-radar"

    @property
    def attribution(self):
        """Return the attribution."""
        return (
            ATTRIBUTION_EN
            if self._config[CONF_LANGUAGE] == "English"
            else ATTRIBUTION_FR
        )

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN,)},
            "manufacturer": "Environment Canada",
            "model": "Weather Radar",
            "default_name": "Weather Radar",
            "entry_type": "service",
        }
