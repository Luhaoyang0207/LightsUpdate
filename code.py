import time
import board
import busio
import digitalio
import neopixel
import math
import storage
import supervisor

import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socketpool
import adafruit_wiznet5k.adafruit_wiznet5k as wiznet
import adafruit_requests

# ————— CONFIGURATION —————
CURRENT_VERSION = "0.1.2"
MANIFEST_URL    = "http://rawcdn.githack.com/Luhaoyang0207/LightsUpdate/main/firmware.json"
CODE_URL        = "http://rawcdn.githack.com/Luhaoyang0207/LightsUpdate/main/code.py"
# ————————————————————————

# 1) Bring up Ethernet
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs  = digitalio.DigitalInOut(board.D10)
eth = wiznet.WIZNET5K(spi, cs)
print("Ethernet IP:", eth.pretty_ip(eth.ifconfig[0]))

# 2) HTTP session (no TLS)
pool     = socketpool.SocketPool(eth)
requests = adafruit_requests.Session(pool, ssl_context=None)

def check_for_update():
    print("OTA: Checking for update…")
    try:
        r = requests.get(MANIFEST_URL)
        if r.status_code != 200:
            print("OTA: manifest fetch failed:", r.status_code)
            return
        meta = r.json()
        remote = meta.get("version", "")
        if remote != CURRENT_VERSION:
            print(f"OTA: New version {remote} available (you have {CURRENT_VERSION})")
            # download new code.py
            resp = requests.get(CODE_URL)
            if resp.status_code == 200:
                new_code = resp.text
                # remount RW, overwrite code.py
                storage.remount("/", False)
                with open("/code.py", "w") as f:
                    f.write(new_code)
                # overwrite boot.py with a no-op stub so USB comes back on next cold boot
                with open("/boot.py", "w") as f:
                    f.write("# boot.py stub — USB will stay enabled\n")
                storage.remount("/", True)
                print("OTA: Update written. Soft-reloading…")
                time.sleep(1)
                supervisor.reload()
            else:
                print("OTA: code.py download failed:", resp.status_code)
        else:
            print("OTA: Already up to date.")
    except Exception as e:
        print("OTA Error:", e)
    finally:
        try:
            r.close()
        except:
            pass

# Run the OTA check once on boot
check_for_update()

# If we fall through here, USB is now visible (boot.py stub ran on this soft-reload)
print("CIRCUITPY visible — you may now open/edit code.py")

# ————— NeoPixel Animation —————
NUM_PIXELS = 192
strip = neopixel.NeoPixel(
    board.EXTERNAL_NEOPIXELS, NUM_PIXELS,
    brightness=1, auto_write=True, pixel_order=neopixel.GRBW
)
strip.fill((0, 0, 0))
strip.show()

# Power on external strip via FET
pwr = digitalio.DigitalInOut(board.EXTERNAL_POWER)
pwr.direction = digitalio.Direction.OUTPUT
pwr.value     = True

def dynamic_brightness(t, lo=0.2, hi=1.0):
    f = (math.sin(t * math.pi/5) + 1) / 2
    return lo + (hi - lo) * f

def interpolate(c1, c2, f):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(4))

def color_with_brightness(t):
    seg  = int(t // 5)
    frac = (t % 5) / 5
    frac = (t % 5) / 5
    if seg == 0:
        base = interpolate((255,255,255,255), (0,0,255,0), frac)
    elif seg == 1:
        base = interpolate((0,0,255,0), (0,255,0,0), frac)
    else:
        base = interpolate((0,255,0,0), (255,255,255,255), frac)
    b = dynamic_brightness(t)
    return tuple(int(c * b) for c in base)

while True:
    t = time.monotonic() % 15
    strip.fill(color_with_brightness(t))
    strip.show()
    time.sleep(0.01)
