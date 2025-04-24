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
# Point OTA at your public GitHub raw manifest
MANIFEST_URL    = "https://raw.githubusercontent.com/Luhaoyang0207/LightsUpdate/main/firmware.json"

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
IDLE_STATE    = "idle"
SUCCESS_STATE = "success"
FAILED_STATE  = "failed"
current_state = IDLE_STATE  # Default to idle

# Brightness and color utilities
def dynamic_brightness(t, min_brightness=0.2, max_brightness=1):
    brightness_factor = (math.sin(t * math.pi / 5) + 1) / 2
    return min_brightness + (max_brightness - min_brightness) * brightness_factor

def interpolate_color(c1, c2, factor):
    return (
        int(c1[0] + (c2[0] - c1[0]) * factor),
        int(c1[1] + (c2[1] - c1[1]) * factor),
        int(c1[2] + (c2[2] - c1[2]) * factor),
        int(c1[3] + (c2[3] - c1[3]) * factor)
    )

def color_with_brightness(t):
    transition = (t % 5) / 5
    brightness = dynamic_brightness(t)
    if t < 5:
        color = interpolate_color((255,255,255,255), (0,0,255,0), transition)
    elif t < 10:
        color = interpolate_color((0,0,255,0), (0,255,0,0), (t-5)/5)
    else:
        color = interpolate_color((0,255,0,0), (255,255,255,255), (t-10)/5)
    return tuple(int(c * brightness) for c in color)

# Main animation loop
def handle_animation():
    if current_state == IDLE_STATE:
        t = time.monotonic() % 15
        strip.fill(color_with_brightness(t))
        strip.show()
        time.sleep(0.01)

while True:
    handle_animation()
