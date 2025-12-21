import socket
import logging
import asyncio
from time import sleep
from .effects import MONO_EFFECTS, PRESET_EFFECTS
from .constants import Command, CommandFlag, StatePosition
from .utils import clamp
from .WifiLedShopLightState import WifiLedShopLightState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_HS_COLOR,
    ATTR_WHITE,
    ATTR_EFFECT,
    ColorMode,
    LightEntityFeature,
    LightEntity,
)
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

class WifiLedShopLight(LightEntity):
    """A Wifi LED Shop Light."""
    
    def __init__(self, ip, name, config, port=8189, timeout=3, retries=5):
        self._ip = ip
        self._default_effect = config.get("effect", "Solid (custom color)")
        self._default_speed = config.get("speed", 255)
        self._port = port
        self._timeout = timeout
        self._retries = retries
        self._state = WifiLedShopLightState()
        self._sock = None
        self._hass = None  # Will be set by async_added_to_hass
        self._update_lock = asyncio.Lock()
        self._brightness_task = None  # For debouncing brightness changes
        self._command_lock = asyncio.Lock()  # Prevent concurrent commands

        self._attr_name = name
        self._attr_supported_color_modes = {ColorMode.RGB}
        self._attr_color_mode = ColorMode.RGB
        self._attr_supported_features = LightEntityFeature.EFFECT

        # Try to get unique_id, but fall back to IP-based ID if connection fails
        try:
            id_response = self.send_command(Command.GET_ID, [])
            if id_response:
                self._attr_unique_id = id_response.decode("utf-8")
            else:
                self._attr_unique_id = f"sp108e_{ip}_{port}"
        except Exception:
            # If we can't get the ID, use a fallback based on IP and port
            self._attr_unique_id = f"sp108e_{ip}_{port}"

        # Don't update during init - let async_added_to_hass handle it

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self._sock:
            self._sock.close()

    def set_color(self, r=0, g=0, b=0):
        r, g, b = clamp(r), clamp(g), clamp(b)
        target = (r, g, b)

        # Send the color command
        self.send_command(Command.SET_COLOR, [r, g, b])
        # Update state optimistically
        self._state.color = target

    def set_brightness(self, brightness=0):
        brightness = clamp(brightness)
        self.send_command(Command.SET_BRIGHTNESS, [brightness])
        # Update state optimistically for immediate feedback
        self._state.brightness = brightness

    def set_white(self, white=0):
        white = clamp(white)
        self.send_command(Command.SET_WHITE, [white])
        # Don't update state optimistically - let sync handle it
        # This behavior could cause HomeAssistant to trigger a double update. Maybe it's better to do it Async

    def set_speed(self, speed=0):
        speed = clamp(speed)
        self.send_command(Command.SET_SPEED, [speed])
        # Don't update state optimistically - let sync handle it
        # This behavior could cause HomeAssistant to trigger a double update. Maybe it's better to do it Async

    def set_effect(self, effect, brightness=None):
        both = {**MONO_EFFECTS, **PRESET_EFFECTS}
        if effect not in both:
            _LOGGER.warning("Unknown effect: %s", effect)
            return
        preset = both[effect]
        # Don't clamp preset values - they can be 0-212
        # MonoEffect values are 205-212, PRESET_EFFECTS are 0-195
        self.send_command(Command.SET_PRESET, [preset])
        # Update state optimistically for immediate feedback
        self._state.mode = preset
        # If brightness is provided with effect, set it too
        if brightness is not None:
            self.set_brightness(brightness)

    def set_custom(self, custom):
        custom = clamp(custom, 1, 12)
        self._state.mode = custom
        self.send_command(Command.SET_CUSTOM, [custom])

    def _toggle_sync(self, desired_state=None):
        """Toggle the light state (synchronous).
        
        Args:
            desired_state: If provided, toggle until this state is reached.
                          None means just toggle once.
        """
        if desired_state is not None:
            # Get current state first
            current_state = False
            try:
                response = self.send_command(Command.SYNC, [])
                if response:
                    current_state = bool(bytearray(response)[StatePosition.IS_ON])
                    _LOGGER.debug("Current state before toggle: %s, desired: %s", current_state, desired_state)
            except Exception as e:
                _LOGGER.debug("Failed to get current state before toggle: %s", e)
                # Assume opposite of desired state to force toggle
                current_state = not desired_state
            
            # Only toggle if current state doesn't match desired state
            if current_state != desired_state:
                _LOGGER.debug("Toggling light from %s to %s", current_state, desired_state)
                self.send_command(Command.TOGGLE, [])
                sleep(0.15)  # Give device time to process
                
                # Verify the toggle worked by syncing again
                try:
                    response = self.send_command(Command.SYNC, [])
                    if response:
                        self._state.update_from_sync(bytearray(response))
                    else:
                        # Fallback to optimistic update
                        self._state.is_on = desired_state
                except Exception as e:
                    _LOGGER.debug("Failed to verify toggle: %s", e)
                    # Fallback to optimistic update
                    self._state.is_on = desired_state
            else:
                _LOGGER.debug("Light already in desired state %s, no toggle needed", desired_state)
                self._state.is_on = desired_state
        else:
            # Just toggle once
            _LOGGER.debug("Toggling light (no specific desired state)")
            self.send_command(Command.TOGGLE, [])
            sleep(0.5)
            # Try to sync actual state
            try:
                response = self.send_command(Command.SYNC, [])
                if response:
                    self._state.update_from_sync(bytearray(response))
            except Exception as e:
                _LOGGER.debug("Failed to sync after toggle: %s", e)
                # Fallback to optimistic toggle
                self._state.is_on = not self._state.is_on

    async def _sync_state(self):
        """Force sync state from device."""
        await self.async_update()

    async def async_turn_on(self, **kwargs):
        """Turn on the light with optional parameters (async)."""
        if self._hass is None:
            _LOGGER.error('Cannot determine HASS instance! Cannot continue further.')
            return

        async with self._command_lock:
            # 1) Get current state from device
            await self._sync_state()
            is_on = self._state.is_on

            # 2) If off, turn on first so subsequent commands are applied while on
            if not is_on:
                await self._hass.async_add_executor_job(self._toggle_sync, True)
                # # ? If no brightness was specified and the user is turning the light on,
                # # ? restore the last known brightness (unless it was 0)
                # if brightness_value is None and self._state.brightness > 0:
                #     brightness_value = self._state.brightness
                # elif brightness_value is None:
                #     brightness_value = 255

                # Brief pause and sync to ensure state is correct after turning on
                # ! _sync_state should not be called here since is already been done by _toggle_sync.
                # ! Re-doing it here only adds more lag to the HA write value and could end up in a concurrency state
                # await asyncio.sleep(0.1)
                # await self._sync_state()
                self.async_write_ha_state()

            # 3) Process all provided parameters
            #    Handle brightness separately (including *_pct and *_step variants)
            current_brightness = self._state.brightness

            brightness_value = None
            if ATTR_BRIGHTNESS in kwargs and kwargs[ATTR_BRIGHTNESS] is not None:
                brightness_value = kwargs[ATTR_BRIGHTNESS]
            elif ATTR_BRIGHTNESS_PCT in kwargs and kwargs[ATTR_BRIGHTNESS_PCT] is not None:
                brightness_value = int(255 * kwargs[ATTR_BRIGHTNESS_PCT] / 100)
            elif ATTR_BRIGHTNESS_STEP in kwargs and kwargs[ATTR_BRIGHTNESS_STEP] is not None:
                brightness_value = clamp(current_brightness + kwargs[ATTR_BRIGHTNESS_STEP])
            elif (
                ATTR_BRIGHTNESS_STEP_PCT in kwargs
                and kwargs[ATTR_BRIGHTNESS_STEP_PCT] is not None
            ):
                delta = int(255 * kwargs[ATTR_BRIGHTNESS_STEP_PCT] / 100)
                brightness_value = clamp(current_brightness + delta)

            # Remove all brightness-related keys from other params
            other_params = {
                k: v
                for k, v in kwargs.items()
                if k
                not in (
                    ATTR_BRIGHTNESS,
                    ATTR_BRIGHTNESS_PCT,
                    ATTR_BRIGHTNESS_STEP,
                    ATTR_BRIGHTNESS_STEP_PCT,
                )
            }

            # If brightness is the only parameter, use debouncing (slider dragging)
            # Otherwise apply immediately (click or combined with other params)
            use_brightness_debounce = (
                brightness_value is not None and len(other_params) == 0 and self._state.is_on
            )

            # Decide which effect to apply:
            # - If an explicit effect was provided, use it
            # - Else, if an RGB/HS color was provided, force Solid (custom color)
            # - Else, if we just turned the light on, use the configured default effect
            has_rgb = "rgb_color" in other_params or ATTR_HS_COLOR in other_params
            explicit_effect = other_params.pop(ATTR_EFFECT, None)

            effect_to_apply = None
            if explicit_effect is not None:
                effect_to_apply = explicit_effect
            elif has_rgb:
                effect_to_apply = "Solid (custom color)"
            elif not is_on:
                effect_to_apply = self._default_effect

            if effect_to_apply is not None:
                effect_brightness = (
                    brightness_value
                    if (brightness_value is not None and not use_brightness_debounce)
                    else None
                )
                # If we are turning the light on from OFF and the caller is only
                # changing the preset (no rgb/hs color), the controller is prone
                # to ignore a single preset command. In that specific case we
                # apply the effect twice with a short delay, mimicking two user
                # presses in the mobile app. For all other cases we apply it
                # once as usual.
                if (not is_on) and (explicit_effect is not None) and (not has_rgb):
                    for _ in range(2):
                        await self._hass.async_add_executor_job(
                            self.set_effect, effect_to_apply, effect_brightness
                        )
                        await asyncio.sleep(0.12)
                else:
                    await self._hass.async_add_executor_job(
                        self.set_effect, effect_to_apply, effect_brightness
                        )
                    # Give the controller a moment to apply the new effect before
                    # we start sending color/brightness updates. This mirrors the
                    # behavior of the mobile app, which spaces commands slightly.
                    await asyncio.sleep(0.1)
                self.async_write_ha_state()

            # Process non-brightness, non-effect parameters immediately
            for k, v in other_params.items():
                if k == "rgb_color":
                    await self._hass.async_add_executor_job(self.set_color, *v)
                    self.async_write_ha_state()
                elif k == ATTR_HS_COLOR:
                    r, g, b = color_util.color_hs_to_RGB(*v)
                    await self._hass.async_add_executor_job(self.set_color, r, g, b)
                    self.async_write_ha_state()
                elif k == ATTR_WHITE:
                    await self._hass.async_add_executor_job(self.set_white, v)
                    self.async_write_ha_state()
                elif k == "speed":
                    await self._hass.async_add_executor_job(self.set_speed, v)
                    self.async_write_ha_state()
                else:
                    _LOGGER.debug("Unknown control key: %s", k)

            # Handle brightness
            if brightness_value is not None:
                if use_brightness_debounce:
                    # Cancel any pending brightness operation
                    if self._brightness_task and not self._brightness_task.done():
                        self._brightness_task.cancel()
                        try:
                            await self._brightness_task
                        except asyncio.CancelledError:
                            _LOGGER.debug('Cancelled the previous unfinished brightness event...')
                            pass
                    
                    # Optimistic update for immediate UI feedback
                    self._state.brightness = brightness_value
                    self.async_write_ha_state()
                    
                    # Debounce brightness changes (for slider dragging)
                    async def set_brightness_debounced():
                        try:
                            await asyncio.sleep(0.2)  # 200ms debounce
                            await self._hass.async_add_executor_job(self.set_brightness, brightness_value)
                            # Update UI after debounced command
                            self.async_write_ha_state()
                        except asyncio.CancelledError:
                            pass
                    
                    self._brightness_task = asyncio.create_task(set_brightness_debounced())
                else:
                    # Apply immediately (click or combined with other params)
                    await self._hass.async_add_executor_job(self.set_brightness, brightness_value)
                    self.async_write_ha_state()

            # Ensure internal state reflects on
            self._state.is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the light (async)."""
        if self._hass is None:
            _LOGGER.error('Cannot determine HASS instance! Cannot continue further.')
            return
        
        async with self._command_lock:
            # Optimistic update: Trust internal state to be responsive
            if self._state.is_on:
                # Send toggle command without waiting for state sync
                # We use None to just toggle, avoiding extra reads in _toggle_sync
                await self._hass.async_add_executor_job(self._toggle_sync, None)

                # Optimistically update state to OFF immediately
                self._state.is_on = False
                self.async_write_ha_state()

    def set_segments(self, segments):
        self.send_command(Command.SET_SEGMENT_COUNT, [segments])

    def set_lights_per_segment(self, lights_per_segment):
        data = list(lights_per_segment.to_bytes(2, byteorder='little'))
        self.send_command(Command.SET_LIGHTS_PER_SEGMENT, data)

    def set_calculated_segments(self, total_lights, segments):
        self.set_segments(segments)
        self.set_lights_per_segment(int(total_lights / segments))

    def send_command(self, command, data=[]):
        result = None
        min_data_len = 3
        padded_data = data + [0] * (min_data_len - len(data))
        raw_data = [CommandFlag.START, *padded_data, command, CommandFlag.END]
        attempts = 0
        last_exception = None
        
        while attempts <= self._retries:
            try:
                _LOGGER.debug("Attempting to connect to %s:%s (attempt %d/%d)", 
                             self._ip, self._port, attempts + 1, self._retries + 1)
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(self._timeout)
                self._sock.connect((self._ip, self._port))
                _LOGGER.debug("Connected to %s:%s, sending command %s", 
                             self._ip, self._port, command)
                self._sock.sendall(bytes(raw_data))
                if command in [Command.GET_ID, Command.SYNC]:
                    result = self._sock.recv(1024)
                    _LOGGER.debug("Received %d bytes from device", len(result) if result else 0)
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close()
                self._sock = None
                return result
            except (socket.timeout, BrokenPipeError, ConnectionRefusedError, 
                    ConnectionResetError, OSError, socket.gaierror, socket.herror) as e:
                last_exception = e
                _LOGGER.warning("Connection attempt %d/%d failed: %s", 
                               attempts + 1, self._retries + 1, str(e))
                if self._sock:
                    try:
                        self._sock.close()
                    except:
                        pass
                    self._sock = None
                
                if attempts < self._retries:
                    attempts += 1
                    sleep(0.1 * attempts)  # Exponential backoff
                else:
                    # Raise a more informative error
                    error_msg = f"Failed to connect to {self._ip}:{self._port} after {self._retries + 1} attempts. "
                    if isinstance(e, ConnectionRefusedError):
                        error_msg += f"Connection refused - check if device is powered on and port {self._port} is open."
                    elif isinstance(e, socket.timeout):
                        error_msg += "Connection timeout - check network connectivity and firewall settings."
                    elif isinstance(e, (socket.gaierror, socket.herror)):
                        error_msg += f"DNS/Host resolution error: {str(e)} - verify the IP address is correct."
                    elif isinstance(e, OSError):
                        error_msg += f"Network error: {str(e)}"
                    else:
                        error_msg += f"Error: {str(e)}"
                    _LOGGER.error(error_msg)
                    raise ConnectionError(error_msg) from e

    # ! Not used. can delete? 
    # def update(self):
    #     """Update state from device (synchronous)."""
    #     response = self.send_command(Command.SYNC, [])
    #     if response:
    #         self._state.update_from_sync(bytearray(response))

    async def async_update(self):
        """Update state from device (async for Home Assistant)."""
        if self._hass is None:
            _LOGGER.error('Cannot determine HASS instance! Cannot continue further.')
            return
        async with self._update_lock:
            try:
                response = await self._hass.async_add_executor_job(self.send_command, Command.SYNC, [])
                if response:
                    # Store previous state to detect changes
                    old_is_on = self._state.is_on
                    old_brightness = self._state.brightness
                    
                    # Update state from device - this is now the source of truth
                    self._state.update_from_sync(bytearray(response))
                    _LOGGER.debug("State updated from device: is_on=%s, brightness=%s, color=%s", self._state.is_on, self._state.brightness, self._state.color)
                    
                    # If state changed significantly, force UI update
                    if (old_is_on != self._state.is_on or abs(old_brightness - self._state.brightness) > 5):
                        self.async_write_ha_state()

            except Exception as e:
                _LOGGER.warning("Failed to update state: %s", e)

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        self._hass = self.hass
        # Do initial update
        await self.async_update()

    def __repr__(self):
        return f"""WifiLedShopLight @ {self._ip}:{self._port}
  state: {self._state}
  unique_id: {self._attr_unique_id}
"""

    @property
    def is_on(self):
        return self._state.is_on

    @property
    def brightness(self):
        # Home Assistant expects None when the light is off to show 0% in the UI
        # When the light is on, return the actual brightness value
        return self._state.brightness if self._state.is_on else None

    @property
    def white_value(self):
        return self._state.white

    @property
    def hs_color(self):
        # Return current color - Home Assistant will handle display based on is_on
        r, g, b = self._state.color
        return color_util.color_RGB_to_hs(r, g, b)

    @property
    def effect_list(self):
        return list({**MONO_EFFECTS, **PRESET_EFFECTS})

    @property
    def effect(self):
        both = {**MONO_EFFECTS, **PRESET_EFFECTS}
        return next((k for k, v in both.items() if v == self._state.mode), None)

    @property
    def device_info(self):
        return {
            "identifiers": {("wifi-led-strip-controller", self._attr_unique_id)},
            "manufacturer": "BTF-LIGHTING",
            "name": self._attr_name,
            "model": "sp108e",
        }

    @property
    def extra_state_attributes(self):
        r, g, b = self._state.color
        both = {**MONO_EFFECTS, **PRESET_EFFECTS}
        current_effect = next((k for k, v in both.items() if v == self._state.mode), None)
        return {
            "brightness": self._state.brightness,
            "effect": current_effect,
            "speed": self._state.speed,
            "default_effect": self._default_effect,
            "current_rgb": f"rgb({r}, {g}, {b})",
            "white_value": self._state.white
        }

