# SP108E WS2815 LED Controller

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/MatteoBorghini/sp108e_ws2815/graphs/commit-activity)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-blue)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Language-Python-blue)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/Hardware-SP108E-red)](https://www.amazon.com/s?k=SP108E)


A modern, fully asynchronous Home Assistant integration for controlling **SP108E-based Wi-Fi LED controllers**.

Designed specifically for **WS2815** and **WS2812B** strips, this integration replaces legacy YAML configurations with a robust **UI-based Config Flow**, allowing for easy setup, multi-device support, and real-time control.

---

## ⚡ Key Features

*   **Seamless Integration:** Fully compliant with Home Assistant's `light` platform.
*   **Rich Control:** Toggle On/Off, adjust brightness, and control RGB + HS colors.
*   **Effect Library:** Access over **180 built-in effects** (Rainbow, Fire, Meteor, Breath, etc.) directly from the UI.
*   **Custom Speed & auto-play:** Configure default startup effects and animation speeds.
*   **Multi-Device Support:** Add as many controllers as you need; each is handled as a separate device.
*   **Connection Valiadtion:** Smart config flow automatically validates network connectivity (TCP Port 8189) before adding the device.

---

## 🔌 Hardware Compatibility

This integration has been tested and verified with:

*   **Controller:**
    *   [ALITOVE SP108E Wi-Fi LED Controller](https://www.amazon.com/gp/product/B07DDB6JHJ)
    *   [BTF-LIGHTING SP620E Mini Controller](https://amzn.eu/d/3goQxa2)
    *   [BTF-LIGHTING WS2812B WiFi SP108E Controller](https://www.btf-lighting.com/en-intl/collections/pixels-controller/products/sp108e-wifi-magic-controller-smart-app-wireless-control-ios-10-android-4-4-ws2812b-ws2813-etc-led-strip-module-light-dc5-24v)
    *   Other controllers are welcome as long as they are based on the SP108E chipset.
*   **LED Strips:**
    *   BTF-LIGHTING WS2815 (12V, Dual-signal backup)
    *   WS2812B (Standard 5V addressable)

> **Note:** The controller must be configured in **STA (Station) Mode** connected to your Wi-Fi network. AP Mode is not supported for HA integration.

---

## 🛠 Installation

### Option 1: HACS (Recommended)

The easiest way to install and keep this integration updated.

1.  Open **HACS** in Home Assistant.
2.  Go to **Integrations** > click the **Host Menu (⋮)** > **Custom repositories**.
3.  Paste the URL of this repository.
4.  Select **Integration** as the category and click **Add**.
5.  Click **Install** on the new "SP108E WS2815" card.
6.  **Restart Home Assistant**.

### Option 2: Manual Installation

1.  Download the latest release zip or clone this repository.
2.  Copy the `sp108e_ws2815` folder into your Home Assistant simplified path:
    ```text
    /config/custom_components/sp108e_ws2815/
    ```
3.  **Restart Home Assistant**.

---

## ⚙️ Configuration

**No YAML is required.** This integration is configured entirely via the Home Assistant UI.

1.  Navigate to **Settings** → **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for **SP108E WS2815**.
4.  Enter the details:
    *   **Host:** The IP address of your controller (e.g., `192.168.1.50`).
    *   **Name:** A friendly name for the device (e.g., `Living Room LEDs`).
    *   **Effect Name:** The default effect to play on startup. 
    *   **Effect Speed:** The speed of the effect animation (0-255).
    *   **Number of Segments:** The number of LED segments to control. (Same as 'LED Shop' App setting)
    *   **Number of LEDs per Segment:** The number of LEDs in each segment. Used to calculate total LEDs for animation effects.
5.  The integration will test values throw a TCP socket and connect automatically.

### changing Options

You can adjust specific settings after installation:

1.  Go to the device page in HA.
2.  Click **Configure**.
3.  Here you can change:
    *  **Number of Segments:** Update the number of LED segments.
    *  **Number of LEDs per Segment:** Update the number of LEDs in each segment.
    *  **Effect Name:** Change the default effect.
    *  **Effect Speed:** Change the default animation speed.
  

---

## ❓ Troubleshooting

**"Failed to connect" during setup:**
The integration uses a TCP handshake validation on **Port 8189**.
1.  Ensure your SP108E is powered on.
2.  Ensure it is connected to the same network as Home Assistant.
3.  Verify the IP address is correct.
4.  If you are seeing problems with effect/effect speed not applying, double-check the "Number of Segments" and "Number of LEDs per Segment" settings match your physical setup.
5.  If problem persists, try opening an issue
   
> **⚠️ Note:** If your firewall blocks outgoing connections, you may need to allow traffic on port **8189**.

**Entities unresponsive:**
SP108E controllers can handle only limited concurrent connections. If you have the official mobile app open at the same time as Home Assistant, commands may be dropped. Close the mobile app to ensure stability.

---

## 🙌 Credits & Acknowledgments 
*   **Development:** Created by [Sam Stein](https://github.com/samhstein) Refactored and Maintained by [Matteo Borghini](https://github.com/MatteoBorghini)
*   **Logic Core:** Powered by the [pyledshop](https://github.com/kylezimmerman/pyledshop) library by @kylezimmerman.
*   **Inspirations:** Standardized structure based on modern HA custom component guidelines.

---

## 📄 License

This project is open-source. Feel free to open an issue or submit a pull request if you have ideas for improvements!