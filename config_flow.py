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


def already_configured(hass, data):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_STATION) == data[CONF_STATION]
            and entry.data.get(CONF_LANGUAGE) == data[CONF_LANGUAGE]
        ):
            return True
    return False


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    latitude = data.get(CONF_LATITUDE)
    longitude = data.get(CONF_LONGITUDE)
    station = data.get(CONF_STATION)
    language = data.get(CONF_LANGUAGE)

    ec = ECWeather(
        station_id=station, coordinates=(latitude, longitude), language=language.lower()
    )
    await ec.update()
    if ec.station_id is None:
        raise BadStationId

    return {"title": ec.station_id, "name": ec.metadata["location"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Environment Canada weather."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                user_input[CONF_STATION] = info["title"]
                user_input[CONF_NAME] = info["name"]

                if not already_configured(self.hass, user_input):
                    self.data = user_input
                    return await self.async_step_name()

                errors["base"] = "already_configured"

            except BadStationId:
                errors["base"] = "bad_station_id"
            except aiohttp.ClientResponseError as err:
                errors["base"] = "cannot_connect"
            except vol.error.MultipleInvalid:
                errors["base"] = "config_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_STATION): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_LANGUAGE, default="English"): vol.In(
                    ["English", "French"]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_name(self, user_input=None):
        """Handle the name step."""
        errors = {}
        if user_input is not None:
            self.data[CONF_NAME] = user_input[CONF_NAME]
            return self.async_create_entry(title=user_input[CONF_NAME], data=self.data)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self.data[CONF_NAME]): str,
            }
        )

        return self.async_show_form(
            step_id="name", data_schema=data_schema, errors=errors
        )


class BadStationId(exceptions.HomeAssistantError):
    """Error to indicate station ID is missing, invalid, or not in EC database."""
