#                                        The sp108e_ws2815 integration.
# Basic func imports
import logging
import socket
from typing import Any

# Schema validation
import voluptuous as vol

# HA imports
from homeassistant import config_entries, core, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
# from homeassistant.data_entry_flow import FlowResult

# Internal imports
from .const import (
    DOMAIN,
    CONF_SEGMENTS,
    CONF_LEDS_PER_SEGMENT,
    CONF_EFFECT_NAME,
    CONF_EFFECT_SPEED,
    DEFAULT_SEGMENTS,
    DEFAULT_LEDS_PER_SEGMENT,
    DEFAULT_EFFECT_NAME,
    DEFAULT_EFFECT_SPEED,
    )
# from .pyledshop import WifiLedShopLight

_LOGGER = logging.getLogger(__name__)

def _get_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Helper to get the schema with optional defaults."""
    defaults = defaults or {}
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST)): str,
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "SP108E Controller")): str,
        vol.Required(CONF_SEGMENTS, default=defaults.get(CONF_SEGMENTS, DEFAULT_SEGMENTS)): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Required(CONF_LEDS_PER_SEGMENT, default=defaults.get(CONF_LEDS_PER_SEGMENT, DEFAULT_LEDS_PER_SEGMENT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=1024)),
        vol.Required(CONF_EFFECT_NAME, default=defaults.get(CONF_EFFECT_NAME, DEFAULT_EFFECT_NAME)): str,
        vol.Required(CONF_EFFECT_SPEED, default=defaults.get(CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED)): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    })


async def validate_input(hass: core.HomeAssistant, user_input: dict) -> dict:
    """Validate the user input allows us to connect to the controller."""
    host = user_input[CONF_HOST]

    # Here i try to ping the controller using TCP on port 8189.
    # This port is generally the default for ESP108E controllers
    # but this means that this integration could possibly not work with lookalike controllers anymore... i should change this in the feature
    try:
        await hass.async_add_executor_job(_test_tcp_connection, host, 8189)
    except OSError as e:
        _LOGGER.error("Failed to connect to SP108E controller at %s: %s", host, e)
        raise CannotConnect from e

    # If the data passes the validation check, return it to HA
    return {
        "title": user_input[CONF_NAME], # <-- for now i leave this here for compatibility with the light.py. Should be removed since it's redundant to the HA one
        CONF_NAME: user_input[CONF_NAME],
        CONF_HOST: host,
        CONF_SEGMENTS: user_input[CONF_SEGMENTS],
        CONF_LEDS_PER_SEGMENT: user_input[CONF_LEDS_PER_SEGMENT],
        CONF_EFFECT_NAME: user_input[CONF_EFFECT_NAME],
        CONF_EFFECT_SPEED: user_input[CONF_EFFECT_SPEED],
    }

# The 'timeout' is completely casual. i don't know yet if it's right
def _test_tcp_connection(host: str, port: int, timeout: int = 3) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))



class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sp108e_ws2815."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # =========================================================================
    # 1. INITIAL SETUP
    # =========================================================================
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        # This should fix the python type check. È una porcata
        assert self.hass is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=info)

        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema(),
            errors=errors
        )

    # =========================================================================
    # 2. RECONFIGURE FLOW (Change IP)
    # =========================================================================
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the reconfiguration flow for an existing entry."""
        # This should fix the python type check. È una porcata
        assert self.hass is not None

        # Get the entry to edit
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if not entry:
            return self.async_abort(reason="entry_missing")

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exeption during reconfigure. Revert back to old configs")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **info},
                    title=info[CONF_NAME]
                )
        
        # Populate the HA form with "default" data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_schema(defaults=entry.data),
            errors=errors
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
    def __init__(self, message="Failed to connect to the device"):
        super().__init__(message)
        self.message = message


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""
