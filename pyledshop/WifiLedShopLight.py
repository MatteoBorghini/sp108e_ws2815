import socket
import logging
from time import sleep

# Driver imports
from .effects import MONO_EFFECTS, PRESET_EFFECTS
from .constants import Command, CommandFlag, StatePosition
from .utils import clamp
from .WifiLedShopLightState import WifiLedShopLightState

_LOGGER = logging.getLogger(__name__)

class WifiLedShopLight:
    """
    A pure Python driver for Wifi LED Shop Lights (SP108E).
    This class handles the raw TCP communication and internal state tracking.
    It does NOT depend on Home Assistant logic. As it should....
    """
    
    def __init__(self, ip, name, config, port=8189, timeout=3, retries=5):
        self._ip = ip
        self._port = port
        self._timeout = timeout
        self._retries = retries
        self._name = name

        # Config
        self._default_effect = config.get("effect", "Solid (custom color)")
        self._default_speed = config.get("speed", 255)

        # Internal state (! limited to the driver. Does not always match with HA !)
        self._state = WifiLedShopLightState()

        # Moved to light.py - Leave it here as light.py maybe need to use the LightEntityFeature consts
        # self._attr_name = name
        # self._attr_supported_color_modes = {ColorMode.RGB}
        # self._attr_color_mode = ColorMode.RGB
        # self._attr_supported_features = LightEntityFeature.EFFECT

        # id_response = self.send_command(Command.GET_ID, [])
        
        # Perform an initial sync to get the real state of the device
        self.sync_state()

    def __repr__(self):
        return f"<WifiLedShopLight IP={self._ip} Port={self._port}>"
    
    # =========================================================================
    # Properties (Read-Only)
    # These are used by light.py to update HA state
    # =========================================================================

    @property
    def is_on(self):
        return self._state.is_on

    @property
    def brightness(self):
        # Home Assistant expects None when the light is off to show 0% in the UI
        # When the light is on, return the actual brightness value
        return self._state.brightness

    @property
    def white_value(self):
        return self._state.white

    @property
    def rgb_color(self):
        # Return current color - Home Assistant will handle display based on is_on
        return self._state.color

    @property
    def effect_list(self):
        return list({**MONO_EFFECTS, **PRESET_EFFECTS})

    @property
    def effect(self):
        both = {**MONO_EFFECTS, **PRESET_EFFECTS}
        # Perform reverse lookup: find name by value (mode)
        return next((k for k, v in both.items() if v == self._state.mode), None)

    # @property
    # def extra_state_attributes(self):
    #     r, g, b = self._state.color
    #     both = {**MONO_EFFECTS, **PRESET_EFFECTS}
    #     current_effect = next((k for k, v in both.items() if v == self._state.mode), None)
    #     return {
    #         "brightness": self._state.brightness,
    #         "effect": current_effect,
    #         "speed": self._state.speed,
    #         "default_effect": self._default_effect,
    #         "current_rgb": f"rgb({r}, {g}, {b})",
    #         "white_value": self._state.white
    #     }

    # =========================================================================
    # Control Methods (Write)
    # These are blocked calls, intended to be run in an Executor by HA
    # =========================================================================

    def turn_on(self):
        if not self._state.is_on:
            _LOGGER.debug("Sending ON command to %s", self._ip)
            self.send_command(Command.TOGGLE, [])
            # Optimistic update
            self._state.is_on = True
            # Verify with sync after a short delay
            sleep(1.0) # <-- This behavior can be dangerous since it hang the HA thread for a full sec. If it does not work even with a full sec i will remove the sync entirely and go only with optimistic + HA polling
            self.sync_state()

    def turn_off(self):
        if self._state.is_on:
            _LOGGER.debug("Sending OFF command to %s", self._ip)
            self.send_command(Command.TOGGLE, [])
            # Optimistic update
            self._state.is_on = False

    def set_rgb(self, rgb_tuple):
        """Send the RGB color (0-255, 0-255, 0-255)"""
        r, g, b = rgb_tuple
        r, g, b = clamp(r), clamp(g), clamp(b)

        _LOGGER.debug("Setting RGB to %s form %s", (r, g, b), self._ip)
        self.send_command(Command.SET_COLOR, [r, g, b])

        # Update the state optimistically
        self._state.color = (r, g, b)
        # Setting a static color usually implies switching to Solid mode
        self._state.mode = MONO_EFFECTS["Solid (custom color)"]

    def set_brightness(self, brightness):
        """Set brightness 0-255"""
        brightness = clamp(brightness)

        _LOGGER.debug("Stting brightness to %s for %s", brightness, self._ip)
        self.send_command(Command.SET_BRIGHTNESS, [brightness])
        self._state.brightness = brightness

    def set_white(self, white):
        white = clamp(white)
        self.send_command(Command.SET_WHITE, [white])
        self._state.white = white
    
    def set_speed(self, speed):
        speed = clamp(speed)
        self.send_command(Command.SET_SPEED,[speed])
        self._state.speed = speed

    def set_effect(self, effect_name):
        both = {**MONO_EFFECTS, **PRESET_EFFECTS}
        if effect_name not in both:
            _LOGGER.warning("Unknow effect: %s", effect_name)
            return
        preset_id = both[effect_name]
        _LOGGER.debug("Setting effect to %s (ID: %s)", effect_name, preset_id)

        self.send_command(Command.SET_PRESET, [preset_id])
        self._state.mode = preset_id

    # =========================================================================
    # Internal / Low Level
    # =========================================================================

    def sync_state(self):
        """Query the device for its status and update internal state."""
        try:
            response = self.send_command(Command.SYNC, [])
            if response:
                self._state.update_from_sync(bytearray(response))
                _LOGGER.debug("Synced state from device %s: %s", self._ip, self._state)
            else:
                _LOGGER.warning("Empty response during sync from %s", self._ip)
        except Exception as err:
            _LOGGER.warning("Failed to sync state from %s: %s", self._ip, err)

    def set_segment(self, segment):
        self.send_command(Command.SET_SEGMENT_COUNT, [segment])

    def set_lights_per_segment(self, light_per_segment):
        data = list(int(light_per_segment).to_bytes(2, byteorder='little'))
        self.send_command(Command.SET_LIGHTS_PER_SEGMENT, data)

    def send_command(self, command, data=[]):
        """
        Open socket, send command, receive response, close socket.
        This is a blocking (synchronous) operation.
        """
        result = None
        min_data_len = 3
        # Add data padding if necessary
        padded_data = data + [0] * (min_data_len - len(data))
        raw_data = [CommandFlag.START, *padded_data, command, CommandFlag.END]

        attempts = 0

        # Retry loop
        while attempts <= self._retries:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._timeout)
                sock.connect((self._ip, self._port))

                sock.sendall(bytes(raw_data))

                # Check if we expect a response
                if command in [Command.GET_ID, Command.SYNC]:
                    result = sock.recv(1024)

                # Am i fucking done?
                return result
            
            except (socket.timeout, OSError) as e:
                attempts += 1
                if attempts > self._retries:
                    _LOGGER.error("Failed to send command to %s after %d attempts: %s", self._ip, self._retries, e)
                    # It should not launch an exception here to not break the integration flow.
                    # Just logging for now
                    return None
                sleep(0.1 * attempts) # Safe Backoff
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

