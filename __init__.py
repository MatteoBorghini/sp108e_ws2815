#                                          The sp108e_ws2815 integration.
# HA imports
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import asyncio
from .options_flow import OptionsFlowHandler
import logging

# Import of custom integration's constants
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SUPPORTED_PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the sp108e_ws2815 component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up sp108e_ws2815 from a config entry."""
    hass.data.setdefault(DOMAIN, { })
    """Save the ENTRY ID for later referencing. Mostly logs to understand what is going on under development"""
    entry_id = config_entry.entry_id
    
    hass.data[DOMAIN][entry_id] = {
        "entities": [],
        "hosts": [], # This comes from the implementation of '@samhstein'. I need to now if it serve a purpose
        "listener": [] # This could be useful later for debugging, leave it here for now
    }
    _LOGGER.debug('Setup entry for %s', entry_id)

    # Backward check to see if there are any leftovers from previous instances of this integration... what a mess
    if "entries" in hass.data[DOMAIN]:
        _LOGGER.debug("An existing 'entities' array has been found in the HASS dictionary from previous installations of this integration... %s", { 'domain': DOMAIN, 'data': hass.data[DOMAIN]["entities"] })

    # Store entities by entry_id for service access
    # if "entities" not in hass.data[DOMAIN]:
    #     hass.data[DOMAIN]["entities"] = {}
    # else:
    #     _LOGGER.debug('Existing entities found in HASS.data registry for this Domain... %s', { 'domain': DOMAIN, 'data': hass.data[DOMAIN]["entities"] })

    await hass.config_entries.async_forward_entry_setups(config_entry, SUPPORTED_PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    # unload_ok = all(
    #     await asyncio.gather(
    #         *[
    #             hass.config_entries.async_forward_entry_unload(config_entry, component)
    #             for component in SUPPORTED_PLATFORMS
    #         ]
    #     )
    # )
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, SUPPORTED_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok

async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
