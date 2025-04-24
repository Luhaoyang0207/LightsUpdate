import time
import board
import busio
import digitalio
import neopixel
import math

# --- Networking & OTA Setup ---
import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socketpool
import adafruit_wiznet5k.adafruit_wiznet5k as wiznet
import adafruit_requests
import storage
import supervisor

# Current firmware version (bump on each release)
CURRENT_VERSION = "0.1.0"
# Point OTA at a public HTTP manifest via raw.githack.com (no SSL required)
MANIFEST_URL    = "http://raw.githack.com/Luhaoyang0207/LightsUpdate/main/firmware.json"

# Initialize Ethernet
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs  = digitalio.DigitalInOut(board.D10)
eth = wiznet.WIZNET5K(spi, cs)
print("Ethernet IP:", eth.pretty_ip(eth.ifconfig[0]))

# Optional: static IP to ensure same subnet as server
eth.ifconfig = (
    (192, 168, 2, 50),     # choose an unused .2.x address
    (255, 255, 255, 0),    # netmask
    (192, 168, 2, 1),      # your gateway/router on .2.x
    (8, 8, 8, 8)           # DNS
)
print("Static IP:", eth.pretty_ip(eth.ifconfig[0]))

pool    = socketpool.SocketPool(eth)
# Use HTTP (no TLS), so ssl_context=None
requests = adafruit_requests.Session(pool, ssl_context=None)

# OTA check function

def check_for_update():
    print("OTA: Checking for update…")
    try:
        r = requests.get(MANIFEST_URL)
        if r.status_code != 200:
            print("OTA: manifest fetch failed:", r.status_code)
            return
        meta = r.json()
        remote_ver = meta.get("version", "")
        if remote_ver != CURRENT_VERSION:
            print(f"OTA: New version {remote_ver} available (you have {CURRENT_VERSION})")
            resp = requests.get(meta["url"])
            if resp.status_code == 200:
                new_code = resp.text
                storage.remount("/", False)
                with open("/code.py", "w") as f:
                    f.write(new_code)
                storage.remount("/", True)
                print("OTA: Update written. Reloading…")
                time.sleep(1)
                supervisor.reload()
            else:
                print("OTA: code download failed:", resp.status_code)
        else:
            print("OTA: Already up to date.")
    except Exception as e:
        print("OTA Error:", e)
    finally:
        try:
            r.close()
        except:
            pass

# Perform OTA on boot
check_for_update()

# NeoPixel setup
NUM_PIXELS   = 192
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

# Turn on 5V FET to power external strip
pwr = digitalio.DigitalInOut(board.EXTERNAL_POWER)
pwr.direction = digitalio.Direction.OUTPUT
pwr.value     = True

# Animation states
def handle_animation():
    t = time.monotonic() % 15
    brightness = (math.sin(t * math.pi / 5) + 1) / 2
    # Simple white-to-blue-to-green fade
    transition = (t % 5) / 5
    if t < 5:
        r_color = (255, 255, 255)
        g_color = (0, 0, 255)
    elif t < 10:
        r_color = (0, 0, 255)
        g_color = (0, 255, 0)
        transition = (t - 5) / 5
    else:
        r_color = (0, 255, 0)
        g_color = (255, 255, 255)
        transition = (t - 10) / 5
    # Linear interpolate channel-wise
    color = tuple(int(r_color[i] + (g_color[i] - r_color[i]) * transition) for i in range(3))
    # Apply brightness
    color = tuple(int(c * brightness) for c in color)
    # Fill strip
    strip.fill(color)
    strip.show()
    time.sleep(0.01)

# Main loop
while True:
    handle_animation()
