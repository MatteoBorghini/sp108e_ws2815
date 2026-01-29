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
from .const import DOMAIN
from .pyledshop import WifiLedShopLight

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_NAME): str,
    # vol.Optional("effect", default="Solid (custom color)"): str,
    # vol.Optional("speed", default=255): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
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
        "title": user_input[CONF_NAME],
        CONF_HOST: host,
        "effect": "Solid (custom color)",
        "speed": 255
    } 

    # try:
    #     config = {
    #         "effect": user_input.get("effect", "Solid (custom color)"),
    #         "speed": user_input.get("speed", 255),
    #     }
    #     light = await hass.async_add_executor_job(
    #         WifiLedShopLight, user_input["host"], user_input["name"], config
    #     )
    #     await hass.async_add_executor_job(light.update)
    # except ConnectionError as e:
    #     _LOGGER.error("Failed to connect to SP108E controller at %s: %s", user_input["host"], str(e))
    #     raise CannotConnect(str(e)) from e
    # except Exception as e:
    #     _LOGGER.exception("Failed to connect to SP108E controller at %s", user_input["host"])
    #     raise CannotConnect(f"Connection failed: {str(e)}") from e

    # return {
    #     "title": user_input["name"],
    #     "effect": user_input["effect"],
    #     "speed": user_input["speed"],
    # }

# The 'timeout' is completely casual. i don't know yet if it's right
def _test_tcp_connection(host: str, port: int, timeout: int = 3) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))



class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sp108e_ws2815."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
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
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
    
    def __init__(self, message="Failed to connect to the device"):
        super().__init__(message)
        self.message = message


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""
