"""Sensors for Environment Canada (EC)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.dt import utcnow
from homeassistant.util.pressure import convert as convert_pressure

from . import ECBaseEntity
from .const import (
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
    SENSOR_TYPES,
    ECSensorEntityDescription,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the EC weather platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    station = config_entry.data[CONF_STATION]

    async_add_entities(
        ECSensor(hass, coordinator, config_entry.data, description) for description in SENSOR_TYPES
    )
    async_add_entities(
        ECAlertSensor(hass, coordinator, config_entry.data, alert) for alert in ["advisories", "endings", "statements", "warnings", "watches"]
    )


class ECSensor(CoordinatorEntity, ECBaseEntity, SensorEntity):
    """An EC Sensor Entity."""

    def __init__(self, hass, coordinator, config, description):
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)
        self._config = config
        self.entity_description = description

        if not hass.config.units.is_metric:
            self._attr_native_unit_of_measurement = description.unit_convert

    @property
    def native_value(self):
        """Return the state."""
        key = self.entity_description.key
        value = self.get_value(key)
        if value is None:
            return None

        if key == "pressure":
            value = value * 10 # Convert kPa to hPa

        # Set alias to unit property -> prevent unnecessary hasattr calls
        unit_of_measurement = self.native_unit_of_measurement
        if unit_of_measurement == SPEED_MILES_PER_HOUR:
            return round(convert_distance(value, LENGTH_KILOMETERS, LENGTH_MILES))
        if unit_of_measurement == LENGTH_MILES:
            return round(convert_distance(value, LENGTH_METERS, LENGTH_MILES))
        if unit_of_measurement == PRESSURE_INHG:
            return round(convert_pressure(value, PRESSURE_PA, PRESSURE_INHG), 2)
        if unit_of_measurement == TEMP_CELSIUS:
            return round(value, 1)
        if unit_of_measurement == PERCENTAGE:
            return round(value)
        return value

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)
        return f"{name if name else DEFAULT_NAME} {self.entity_description.name}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._config[CONF_STATION]}-{self._config[CONF_LANGUAGE]}-{self.entity_description.key}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True # FIX ME
        # return False


class ECAlertSensor(CoordinatorEntity, ECBaseEntity, SensorEntity):
    """An EC Sensor Entity for Alerts."""
    """ TODO!!! """

    def __init__(self, hass, coordinator, config, alert_name):
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)
        self._config = config
        self._alert_name = alert_name
        self._alert_attrs = None

    @property
    def native_value(self):
        """Return the state."""
        value = self.coordinator.data.alerts.get(self._alert_name, {}).get("value")

        self._alert_attrs = {}
        for index, alert in enumerate(value, start=1):
            self._alert_attrs[f"alert {index}"] = alert.get("title")
            self._alert_attrs[f"alert_time {index}"] = alert.get("date")

        return len(value)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._alert_attrs

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)
        return f"{name if name else DEFAULT_NAME} {self._alert_name}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._config[CONF_STATION]}-{self._config[CONF_LANGUAGE]}-{self._alert_name}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True # FIX ME
        # return False
