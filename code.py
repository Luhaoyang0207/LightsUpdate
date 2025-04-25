import time
import board
import busio
import digitalio
import neopixel
import math
import storage
import supervisor

# --- Networking & OTA Setup ---
import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socketpool
import adafruit_wiznet5k.adafruit_wiznet5k as wiznet
import adafruit_requests

# Current firmware version (bump on each release)
CURRENT_VERSION = "0.1.0"
# Public HTTP manifest URL (no SSL required)
MANIFEST_URL = "http://rawcdn.githack.com/Luhaoyang0207/LightsUpdate/main/firmware.json"

# Initialize Ethernet over WIZnet5K (DHCP)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = digitalio.DigitalInOut(board.D10)
eth = wiznet.WIZNET5K(spi, cs)
print("Ethernet IP:", eth.pretty_ip(eth.ifconfig[0]))

# Create HTTP session (no TLS)
pool = socketpool.SocketPool(eth)
requests = adafruit_requests.Session(pool, ssl_context=None)

# OTA check and update function
def check_for_update():
    print("OTA: Checking for update…")
    try:
        r = requests.get(MANIFEST_URL)
        if r.status_code != 200:
            print("OTA: manifest fetch failed:", r.status_code)
            return
        manifest = r.json()
        remote_ver = manifest.get("version", "")
        if remote_ver != CURRENT_VERSION:
            print(f"OTA: New version {remote_ver} available (you have {CURRENT_VERSION})")
            # Ensure HTTP-only URL
            code_url = "http://rawcdn.githack.com/Luhaoyang0207/LightsUpdate/main/code.py"
            code_resp = requests.get(code_url)
            if code_resp.status_code == 200:
                new_code = code_resp.text
                storage.disable_usb_drive()
                storage.remount('/', False)
                with open('/code.py', 'w') as f:
                    f.write(new_code)
                storage.remount('/', True)
                storage.enable_usb_drive()
                print("OTA: Update written. Reloading…")
                time.sleep(1)
                supervisor.reload()

            else:
                print("OTA: code download failed:", code_resp.status_code)
        else:
            print("OTA: Already up to date.")
    except Exception as e:
        print("OTA Error:", e)
    finally:
        try:
            r.close()
        except:
            pass

# Run OTA on boot
check_for_update()

storage.enable_usb_drive()

# --- NeoPixel Animation Setup ---
NUM_PIXELS = 192
NEOPIXEL_PIN = board.EXTERNAL_NEOPIXELS
strip = neopixel.NeoPixel(
    NEOPIXEL_PIN,
    NUM_PIXELS,
    brightness=1,
    auto_write=True,
    pixel_order=neopixel.GRBW
)
strip.fill(0)
strip.show()

# Power on external strip via FET
enable = digitalio.DigitalInOut(board.EXTERNAL_POWER)
enable.direction = digitalio.Direction.OUTPUT
enable.value = True

# Animation loop: smooth white→blue→green fade
def handle_animation():
    t = time.monotonic() % 15
    brightness = (math.sin(t * math.pi / 5) + 1) / 2
    segment = int(t // 5)
    frac = (t % 5) / 5
    if segment == 0:
        start = (255, 255, 255)
        end = (0, 0, 255)
    elif segment == 1:
        start = (0, 0, 255)
        end = (0, 255, 0)
    else:
        start = (0, 255, 0)
        end = (255, 255, 255)
    color = tuple(int(start[i] + (end[i] - start[i]) * frac) for i in range(3))
    color = tuple(int(c * brightness) for c in color)
    strip.fill(color)
    strip.show()
    time.sleep(0.01)

# Main loop
while True:
    handle_animation()
