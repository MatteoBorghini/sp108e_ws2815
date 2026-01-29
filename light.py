import logging
from typing import Any

# HA imports
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

# Internal imports
from .pyledshop import WifiLedShopLight
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SP108E WS2815 light from a config entry."""
    host = config_entry.data[CONF_HOST]
    name = config_entry.data[CONF_NAME]
    config = { **config_entry.data, **config_entry.options }

    try:
        driver = await hass.async_add_executor_job(
            WifiLedShopLight, host, name, config
        )
    except Exception as err:
        _LOGGER.error("Failed to initialize SP108E Controller at %s: %s", host, err)
        return

    # Create the entity wrapper and add it to HA
    async_add_entities([SP108ELight(driver, config_entry)])
    
class SP108ELight(LightEntity):
    """Modern implementation of SP108E light"""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, driver: WifiLedShopLight, entry: ConfigEntry) -> None:
        # Initialize the light
        self._driver = driver
        self._entry = entry

        # Light's Unique ID based on entry_id
        self._attr_unique_id = entry.entry_id
        self._attr_name = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="SP108E",
            model="SP108E Wi-Fi",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
    
    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._driver.is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._driver.brightness

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value [int, int, int]."""
        return self._driver.rgb_color

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._driver.effect_list

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._driver.effect

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        
        # Call the driver in the ThreadPoll, doing so will hopefully not hang the loop
        if ATTR_BRIGHTNESS in kwargs:
            await self.hass.async_add_executor_job(
                self._driver.set_brightness, kwargs[ATTR_BRIGHTNESS]
            )

        if ATTR_RGB_COLOR in kwargs:
            await self.hass.async_add_executor_job(
                self._driver.set_rgb, kwargs[ATTR_RGB_COLOR]
            )
        
        if ATTR_EFFECT in kwargs:
            await self.hass.async_add_executor_job(
                self._driver.set_effect, kwargs[ATTR_EFFECT]
            )

        # If no args are passed just check if the light is on. This should be standard doing of HA
        if not kwargs:
            await self.hass.async_add_executor_job(self._driver.turn_on)

        # Update the state in HA
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.hass.async_add_executor_job(self._driver.turn_off)
        self.async_write_ha_state()
