"""Config flow for Environment Canada integration."""
import logging

import aiohttp
from env_canada import ECWeather
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LANGUAGE, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    latitude = data.get(CONF_LATITUDE)
    longitude = data.get(CONF_LONGITUDE)
    station = data.get(CONF_STATION)
    language = data.get(CONF_LANGUAGE)

    if station is None and latitude is None and longitude is None:
        latitude = hass.config.latitude
        longitude = hass.config.longitude

    ec = ECWeather(
        station_id=station, coordinates=(latitude, longitude), language=language
    )
    try:
        await ec.update()
    except aiohttp.ClientError as err:
        _LOGGER.error("Could not connect: %s", err)
        raise CannotConnect from err

    return {"title": ec.station_id}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Environment Canada weather."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # await self.async_set_unique_id(
            #     base_unique_id(user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])
            # )
            # self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                user_input[CONF_STATION] = info["title"]
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        msg = "Can use only one location specifier."
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default="Environment Canada"): str,
                vol.Optional(CONF_STATION): str,
                vol.Optional(CONF_LATITUDE, default=self.hass.config.latitude): cv.latitude,
                vol.Optional(CONF_LONGITUDE, default=self.hass.config.longitude): cv.longitude,
                vol.Optional(CONF_LANGUAGE, default="english"): vol.In(["english", "french"]),
                # vol.Optional(CONF_NAME, default="Environment Canada"): str,
                # vol.Exclusive(CONF_STATION, "location", msg=msg): str,
                # vol.Exclusive("coordinates", "location", msg=msg): {
                #     vol.Required(
                #         CONF_LATITUDE, default=self.hass.config.latitude
                #     ): cv.latitude,
                #     vol.Required(
                #         CONF_LONGITUDE, default=self.hass.config.longitude
                #     ): cv.longitude,
                # },
                # vol.Optional(CONF_LANGUAGE, default="english"): vol.In(
                #     ["english", "french"]
                # ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
