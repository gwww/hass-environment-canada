"""Support for Environment Canada (EC) weather service."""
import datetime
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
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
from homeassistant.util import dt
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from .const import (
    ATTRIBUTION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_MAP,
    CONF_LANGUAGE,
    CONF_STATION,
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
        """Initialise the platform."""
        super().__init__(coordinator)
        self._config = config
        self._is_metric = is_metric
        self._hourly = hourly

    @property
    def unique_id(self):
        """Return unique ID."""
        suffix = "-hourly" if self._hourly else ""
        # return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}-{self._config[CONF_LANGUAGE]}{suffix}"
        return f"{self._config[CONF_STATION]}-{self._config[CONF_LANGUAGE]}{suffix}"

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

    @property
    def visibility(self):
        """Return the visibility."""
        visibility = self.coordinator.data.conditions.get("visibility", {}).get("value")
        if self._is_metric or visibility is None:
            return visibility

        visibility = convert_distance(visibility, LENGTH_KILOMETERS, LENGTH_MILES)
        return visibility
        # return int(round(visibility))

    @property
    def forecast(self):
        """Return the forecast array."""
        return get_forecast(self.coordinator.data, self._hourly)

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


def get_forecast(data, hourly_forecast):
    """Build the forecast array."""
    forecast_array = []

    if not hourly_forecast:
        half_days = data.daily_forecast

        today = {
            ATTR_FORECAST_TIME: dt.now().isoformat(),
            ATTR_FORECAST_CONDITION: format_condition(half_days[0]["icon_code"]),
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                half_days[0]["precip_probability"]
            ),
        }

        if half_days[0]["temperature_class"] == "high":
            today.update(
                {
                    ATTR_FORECAST_TEMP: int(half_days[0]["temperature"]),
                    ATTR_FORECAST_TEMP_LOW: int(half_days[1]["temperature"]),
                }
            )
            half_days = half_days[2:]
        else:
            today.update(
                {
                    ATTR_FORECAST_TEMP: None,
                    ATTR_FORECAST_TEMP_LOW: int(half_days[0]["temperature"]),
                }
            )
            half_days = half_days[1:]

        forecast_array.append(today)

        for day, high, low in zip(range(1, 6), range(0, 9, 2), range(1, 10, 2)):
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: (
                        dt.now() + datetime.timedelta(days=day)
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: int(half_days[high]["temperature"]),
                    ATTR_FORECAST_TEMP_LOW: int(half_days[low]["temperature"]),
                    ATTR_FORECAST_CONDITION: format_condition(half_days[high]["icon_code"]),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        half_days[high]["precip_probability"]
                    ),
                }
            )

    else:
        for hour in data.hourly_forecast:
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: hour["period"],
                    ATTR_FORECAST_TEMP: int(hour["temperature"]),
                    ATTR_FORECAST_CONDITION: format_condition(hour["icon_code"]),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        hour["precip_probability"]
                    ),
                }
            )

    return forecast_array
