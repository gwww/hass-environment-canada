"""Support for Environment Canada (EC) weather service."""
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from .const import (
    ATTRIBUTION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_MAP,
    CONF_LANGUAGE,
    DOMAIN,
    EC_ICON_TO_HA_CONDITION_MAP,
    FORECAST_MAP,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Environment Canada"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            ECWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, False
            ),
            ECWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, True
            ),
        ]
    )


def format_condition(ec_icon: str) -> str:
    """Return condition."""
    try:
        icon_number = int(ec_icon)
    except:
        return None
    return EC_ICON_TO_HA_CONDITION_MAP.get(icon_number)


class ECWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a EC weather condition."""

    def __init__(self, coordinator, config, is_metric, hourly):
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._config = config
        self._is_metric = is_metric
        self._hourly = hourly

    @property
    def unique_id(self):
        """Return unique ID."""
        suffix = "-hourly" if self._hourly else ""
        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}-{self._config[CONF_LANGUAGE]}{suffix}"

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)
        name_suffix = " Hourly" if self._hourly else ""
        return f"{name if name else DEFAULT_NAME}{name_suffix}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._hourly

    @property
    def condition(self):
        """Return the current condition."""
        return format_condition(
            self.coordinator.data.conditions.get("icon_code", {}).get("value")
        )

    @property
    def temperature(self):
        """Return the temperature."""
        return self.coordinator.data.conditions.get("temperature", {}).get("value")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        if self.coordinator.data.conditions.get("pressure", {}).get("value") is None:
            return None
        pressure_hpa = 10 * float(self.coordinator.data.conditions["pressure"]["value"])
        if self._is_metric:
            return pressure_hpa

        return round(convert_pressure(pressure_hpa, PRESSURE_HPA, PRESSURE_INHG), 2)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data.conditions.get("humidity", {}).get("value")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        speed_km_h = self.coordinator.data.conditions.get("wind_speed", {}).get("value")
        if self._is_metric or speed_km_h is None:
            return speed_km_h

        speed_mi_h = convert_distance(speed_km_h, LENGTH_KILOMETERS, LENGTH_MILES)
        return int(round(speed_mi_h))

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self.coordinator.data.conditions.get("wind_bearing", {}).get("value")

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    # @property
    # def forecast(self):
    #     """Return the forecast array."""
    #     if self._hourly:
    #         forecast = self.coordinator.data.hourly_forecast
    #     else:
    #         forecast = self.coordinator.data.daily_forecast

    #     required_keys = {ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME}
    #     ha_forecast = []
    #     for item in forecast:
    #         if not set(item).issuperset(required_keys):
    #             continue
    #         ha_item = {
    #             k: item[v]
    #             for k, v in FORECAST_MAP.items()
    #             if item.get(v) is not None
    #         }
    #         if not self._is_metric and ATTR_FORECAST_PRECIPITATION in ha_item:
    #             precip_inches = convert_distance(
    #                 ha_item[ATTR_FORECAST_PRECIPITATION],
    #                 LENGTH_MILLIMETERS,
    #                 LENGTH_INCHES,
    #             )
    #             ha_item[ATTR_FORECAST_PRECIPITATION] = round(precip_inches, 2)
    #         if ha_item.get(ATTR_FORECAST_CONDITION):
    #             ha_item[ATTR_FORECAST_CONDITION] = format_condition(
    #                 ha_item[ATTR_FORECAST_CONDITION]
    #             )
    #         ha_forecast.append(ha_item)
    #     return ha_forecast

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN,)},
            "manufacturer": "Environment Canada",
            "model": "Forecast",
            "default_name": "Forecast",
            "entry_type": "service",
        }
