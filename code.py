import time
import board
import busio
import digitalio
import neopixel
import math

# Networking & MQTT (WIZnet5K)
import adafruit_wiznet5k.adafruit_wiznet5k as wiznet
import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# LED Animation
from adafruit_led_animation.animation.solid import Solid

# ---------------- Configuration ----------------
NUM_PIXELS      = 192
PIN_PIXELS      = board.EXTERNAL_NEOPIXELS
MIN_IDLE_BRT    = 0.2
MAX_IDLE_BRT    = 1.0

IDLE_STATE      = "idle"
SUCCESS_STATE   = "success"
FAILED_STATE    = "failed"
ERROR_PIN_STATE = "error_pin"

MQTT_BROKER     = "192.168.51.67"  # your broker IP
MQTT_PORT       = 1883
MQTT_TOPIC      = "lights/control"

# Optional static IP (comment out to use DHCP)
STATIC_IFCONFIG = (
    (192, 168, 51, 200),  # board’s static IP
    (255, 255, 255, 0),   # subnet mask
    (192, 168, 51, 1),    # gateway
    (8, 8, 8, 8)          # DNS
)

# ---------------- Setup ----------------
# NeoPixel strip
strip = neopixel.NeoPixel(
    PIN_PIXELS,
    NUM_PIXELS,
    brightness=MIN_IDLE_BRT,
    auto_write=False,
    pixel_order=neopixel.GRBW
)
# Power gate for external strip
power = digitalio.DigitalInOut(board.EXTERNAL_POWER)
power.direction = digitalio.Direction.OUTPUT
power.value = True

# Solid animations for non-idle states
success_anim   = Solid(strip, color=(0, 255, 0, 0))
failed_anim    = Solid(strip, color=(255, 0, 0, 0))
error_pin_anim = Solid(strip, color=(255, 255, 0, 0))

# ---------------- Helper Functions ----------------
def dynamic_brightness(t):
    # Sinusoidal oscillation between MIN_IDLE_BRT and MAX_IDLE_BRT over 40s
    factor = (math.sin(t * math.pi / 20) + 1) / 2
    return MIN_IDLE_BRT + (MAX_IDLE_BRT - MIN_IDLE_BRT) * factor


def interpolate_color(c1, c2, f):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(4))


def color_with_brightness(t):
    # Extended 60s cycle: white→blue→green→white with fading brightness
    phase_time = t % 45
    transition = (phase_time % 20) / 20
    brightness = dynamic_brightness(t)

    if phase_time < 20:  # white→blue over 20s
        base = interpolate_color((255,255,255,255), (0,0,255,0), transition)
    elif phase_time < 40:  # blue→green over next 20s
        base = interpolate_color((0,0,255,0), (0,255,0,0), transition)
    else:  # green→white over final 20s
        base = interpolate_color((0,255,0,0), (255,255,255,255), transition)

    return tuple(int(c * brightness) for c in base)

# ---------------- State ----------------
current_state = IDLE_STATE

def mqtt_message(client, topic, msg):
    global current_state
    print(f"Received on {topic}: {msg}")
    current_state = msg
    strip.brightness = MAX_IDLE_BRT if msg in (SUCCESS_STATE, FAILED_STATE, ERROR_PIN_STATE) else MIN_IDLE_BRT

# ---------------- Network Setup ----------------
cs  = digitalio.DigitalInOut(board.D10)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
eth = wiznet.WIZNET5K(spi, cs)
eth.ifconfig = STATIC_IFCONFIG  # comment out for DHCP
print("IP =", eth.pretty_ip(eth.ifconfig[0]))
pool = socketpool.SocketPool(eth)

# ---------------- MQTT Setup ----------------
mqtt_client = MQTT.MQTT(
    broker=MQTT_BROKER,
    port=MQTT_PORT,
    socket_pool=pool
)
# shorten the internal socket timeout so loop can poll quickly for smooth animations
mqtt_client.socket_timeout = 0.02
mqtt_client.on_message = mqtt_message

# Raw TCP test
sock = pool.socket()
try:
    sock.connect((MQTT_BROKER, MQTT_PORT))
    print("✅ TCP to broker OK!")
except Exception as e:
    print("❌ TCP connect failed:", e)
finally:
    sock.close()

mqtt_client.connect()
mqtt_client.subscribe(MQTT_TOPIC)
print("Subscribed →", MQTT_TOPIC)

# ---------------- Main Loop ----------------
while True:
    # Drive animation continuously for smooth idle fade
    t = time.monotonic()
    if current_state == IDLE_STATE:
        strip.fill(color_with_brightness(t))
        strip.show()
    elif current_state == SUCCESS_STATE:
        success_anim.animate()
    elif current_state == FAILED_STATE:
        failed_anim.animate()
    elif current_state == ERROR_PIN_STATE:
        error_pin_anim.animate()
    # Short sleep for animation frame
    time.sleep(0.02)
    # Poll MQTT with at least 1s timeout to avoid loop-timeout errors
    try:
        mqtt_client.loop(timeout=1)
    except Exception as e:
        print("MQTT error, reconnecting…", e)
        mqtt_client.connect()
