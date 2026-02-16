"""
Home Generator

Generates smart home configurations based on templates or custom parameters.
Supports various home sizes from studio apartments to smart mansions.
"""

import random
from datetime import time
from typing import Optional

from loguru import logger

from src.simulation.models import (
    Device,
    DeviceConfig,
    DeviceProtocol,
    DeviceState,
    DeviceType,
    Home,
    HomeConfig,
    HomeTemplate,
    Inhabitant,
    InhabitantType,
    Room,
    RoomConfig,
    RoomType,
    Schedule,
    SecurityLevel,
)


# =============================================================================
# Template Definitions
# =============================================================================

TEMPLATE_CONFIGS = {
    HomeTemplate.STUDIO_APARTMENT: {
        "rooms": [
            {"type": RoomType.LIVING_ROOM, "area": 25, "has_window": True},
            {"type": RoomType.BATHROOM, "area": 5, "has_window": False},
            {"type": RoomType.ENTRANCE, "area": 3, "has_external_door": True},
        ],
        "total_area": 35,
        "floors": 1,
        "typical_inhabitants": 1,
        "typical_devices": (3, 6),
    },
    HomeTemplate.ONE_BEDROOM: {
        "rooms": [
            {"type": RoomType.LIVING_ROOM, "area": 20, "has_window": True},
            {"type": RoomType.BEDROOM, "area": 15, "has_window": True},
            {"type": RoomType.KITCHEN, "area": 10, "has_window": True},
            {"type": RoomType.BATHROOM, "area": 6, "has_window": False},
            {"type": RoomType.ENTRANCE, "area": 4, "has_external_door": True},
        ],
        "total_area": 55,
        "floors": 1,
        "typical_inhabitants": 2,
        "typical_devices": (5, 10),
    },
    HomeTemplate.TWO_BEDROOM: {
        "rooms": [
            {"type": RoomType.LIVING_ROOM, "area": 25, "has_window": True},
            {"type": RoomType.MASTER_BEDROOM, "area": 18, "has_window": True},
            {"type": RoomType.BEDROOM, "area": 14, "has_window": True},
            {"type": RoomType.KITCHEN, "area": 12, "has_window": True},
            {"type": RoomType.BATHROOM, "area": 7, "has_window": False},
            {"type": RoomType.BATHROOM, "area": 5, "has_window": False},
            {"type": RoomType.ENTRANCE, "area": 5, "has_external_door": True},
            {"type": RoomType.HALLWAY, "area": 8, "has_window": False},
        ],
        "total_area": 95,
        "floors": 1,
        "typical_inhabitants": 3,
        "typical_devices": (10, 18),
    },
    HomeTemplate.FAMILY_HOUSE: {
        "rooms": [
            {"type": RoomType.LIVING_ROOM, "area": 35, "has_window": True},
            {"type": RoomType.MASTER_BEDROOM, "area": 22, "has_window": True, "floor": 1},
            {"type": RoomType.BEDROOM, "area": 16, "has_window": True, "floor": 1},
            {"type": RoomType.BEDROOM, "area": 14, "has_window": True, "floor": 1},
            {"type": RoomType.KITCHEN, "area": 18, "has_window": True},
            {"type": RoomType.DINING_ROOM, "area": 15, "has_window": True},
            {"type": RoomType.BATHROOM, "area": 8, "has_window": False, "floor": 1},
            {"type": RoomType.BATHROOM, "area": 6, "has_window": False},
            {"type": RoomType.OFFICE, "area": 12, "has_window": True},
            {"type": RoomType.GARAGE, "area": 25, "has_external_door": True},
            {"type": RoomType.ENTRANCE, "area": 8, "has_external_door": True},
            {"type": RoomType.HALLWAY, "area": 10, "has_window": False},
            {"type": RoomType.HALLWAY, "area": 8, "has_window": False, "floor": 1},
        ],
        "total_area": 200,
        "floors": 2,
        "has_garage": True,
        "typical_inhabitants": 4,
        "typical_devices": (20, 35),
    },
    HomeTemplate.SMART_MANSION: {
        "rooms": [
            {"type": RoomType.LIVING_ROOM, "area": 50, "has_window": True},
            {"type": RoomType.MASTER_BEDROOM, "area": 35, "has_window": True, "floor": 1},
            {"type": RoomType.BEDROOM, "area": 25, "has_window": True, "floor": 1},
            {"type": RoomType.BEDROOM, "area": 22, "has_window": True, "floor": 1},
            {"type": RoomType.BEDROOM, "area": 20, "has_window": True, "floor": 1},
            {"type": RoomType.BEDROOM, "area": 18, "has_window": True, "floor": 2},
            {"type": RoomType.KITCHEN, "area": 30, "has_window": True},
            {"type": RoomType.DINING_ROOM, "area": 25, "has_window": True},
            {"type": RoomType.BATHROOM, "area": 15, "has_window": True, "floor": 1},
            {"type": RoomType.BATHROOM, "area": 10, "has_window": False, "floor": 1},
            {"type": RoomType.BATHROOM, "area": 8, "has_window": False},
            {"type": RoomType.BATHROOM, "area": 8, "has_window": False, "floor": 2},
            {"type": RoomType.OFFICE, "area": 20, "has_window": True},
            {"type": RoomType.OFFICE, "area": 15, "has_window": True, "floor": 1},
            {"type": RoomType.GARAGE, "area": 50, "has_external_door": True},
            {"type": RoomType.BASEMENT, "area": 60, "has_window": False, "floor": -1},
            {"type": RoomType.GARDEN, "area": 100, "has_window": False, "floor": 0},
            {"type": RoomType.ENTRANCE, "area": 15, "has_external_door": True},
            {"type": RoomType.HALLWAY, "area": 20, "has_window": False},
            {"type": RoomType.HALLWAY, "area": 15, "has_window": False, "floor": 1},
            {"type": RoomType.HALLWAY, "area": 12, "has_window": False, "floor": 2},
        ],
        "total_area": 550,
        "floors": 3,
        "has_garage": True,
        "has_basement": True,
        "has_garden": True,
        "typical_inhabitants": 6,
        "typical_devices": (50, 80),
    },
}


# Room-to-device recommendations
ROOM_DEVICE_RECOMMENDATIONS = {
    RoomType.LIVING_ROOM: [
        (DeviceType.SMART_LIGHT, 2, 4),
        (DeviceType.SMART_TV, 0, 1),
        (DeviceType.SMART_SPEAKER, 0, 1),
        (DeviceType.MOTION_SENSOR, 0, 1),
        (DeviceType.THERMOSTAT, 0, 1),
    ],
    RoomType.BEDROOM: [
        (DeviceType.SMART_LIGHT, 1, 2),
        (DeviceType.SMART_BLINDS, 0, 1),
        (DeviceType.MOTION_SENSOR, 0, 1),
    ],
    RoomType.MASTER_BEDROOM: [
        (DeviceType.SMART_LIGHT, 2, 3),
        (DeviceType.SMART_BLINDS, 0, 1),
        (DeviceType.SMART_TV, 0, 1),
        (DeviceType.MOTION_SENSOR, 0, 1),
    ],
    RoomType.KITCHEN: [
        (DeviceType.SMART_LIGHT, 1, 3),
        (DeviceType.SMOKE_DETECTOR, 1, 1),
        (DeviceType.SMART_PLUG, 0, 2),
        (DeviceType.SMART_SPEAKER, 0, 1),
    ],
    RoomType.BATHROOM: [
        (DeviceType.SMART_LIGHT, 1, 1),
        (DeviceType.WATER_LEAK_SENSOR, 0, 1),
    ],
    RoomType.OFFICE: [
        (DeviceType.SMART_LIGHT, 1, 2),
        (DeviceType.SMART_PLUG, 0, 2),
        (DeviceType.MOTION_SENSOR, 0, 1),
    ],
    RoomType.GARAGE: [
        (DeviceType.SMART_LIGHT, 1, 2),
        (DeviceType.MOTION_SENSOR, 0, 1),
        (DeviceType.DOOR_SENSOR, 0, 1),
        (DeviceType.SECURITY_CAMERA, 0, 1),
    ],
    RoomType.ENTRANCE: [
        (DeviceType.SMART_LOCK, 1, 1),
        (DeviceType.SMART_DOORBELL, 0, 1),
        (DeviceType.MOTION_SENSOR, 0, 1),
        (DeviceType.SMART_LIGHT, 1, 1),
    ],
    RoomType.HALLWAY: [
        (DeviceType.SMART_LIGHT, 1, 2),
        (DeviceType.MOTION_SENSOR, 0, 1),
    ],
    RoomType.DINING_ROOM: [
        (DeviceType.SMART_LIGHT, 1, 2),
    ],
    RoomType.BASEMENT: [
        (DeviceType.SMART_LIGHT, 1, 2),
        (DeviceType.MOTION_SENSOR, 0, 1),
        (DeviceType.WATER_LEAK_SENSOR, 0, 1),
    ],
    RoomType.GARDEN: [
        (DeviceType.SMART_LIGHT, 0, 3),
        (DeviceType.MOTION_SENSOR, 0, 2),
        (DeviceType.SECURITY_CAMERA, 0, 2),
    ],
    RoomType.LAUNDRY: [
        (DeviceType.SMART_LIGHT, 1, 1),
        (DeviceType.WATER_LEAK_SENSOR, 0, 1),
        (DeviceType.SMART_PLUG, 0, 1),
    ],
    RoomType.BALCONY: [
        (DeviceType.SMART_LIGHT, 0, 1),
    ],
    RoomType.ATTIC: [
        (DeviceType.SMART_LIGHT, 0, 1),
        (DeviceType.SMOKE_DETECTOR, 0, 1),
    ],
}


# Device configurations by type - 85 device types
DEVICE_CONFIGS = {
    # ==========================================================================
    # FREQUENTLY USED (12 devices)
    # ==========================================================================
    DeviceType.SMART_LIGHT: {
        "manufacturers": ["Philips Hue", "LIFX", "Sengled", "Wyze"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_PLUG: {
        "manufacturers": ["TP-Link", "Wemo", "Wyze", "Amazon"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.THERMOSTAT: {
        "manufacturers": ["Nest", "Ecobee", "Honeywell", "Emerson"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SECURITY_CAMERA: {
        "manufacturers": ["Ring", "Nest", "Arlo", "Wyze"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SMART_LOCK: {
        "manufacturers": ["Yale", "August", "Schlage", "Kwikset"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.CRITICAL,
        "battery_powered": True,
    },
    DeviceType.MOTION_SENSOR: {
        "manufacturers": ["Philips Hue", "SmartThings", "Aqara", "Wyze"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.SMART_SPEAKER: {
        "manufacturers": ["Amazon Echo", "Google Home", "Apple HomePod"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_TV: {
        "manufacturers": ["Samsung", "LG", "Sony", "TCL"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_DOORBELL: {
        "manufacturers": ["Ring", "Nest", "Arlo", "Eufy"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.DOOR_SENSOR: {
        "manufacturers": ["SmartThings", "Aqara", "Ring", "Wyze"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.SMOKE_DETECTOR: {
        "manufacturers": ["Nest", "First Alert", "Kidde"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.ROUTER: {
        "manufacturers": ["Eero", "Google Nest", "Netgear", "TP-Link"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },

    # ==========================================================================
    # SECURITY (12 devices)
    # ==========================================================================
    DeviceType.WINDOW_SENSOR: {
        "manufacturers": ["SmartThings", "Aqara", "Ring"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.GLASS_BREAK_SENSOR: {
        "manufacturers": ["Honeywell", "DSC", "Interlogix", "2GIG"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.PANIC_BUTTON: {
        "manufacturers": ["Ring", "SimpliSafe", "ADT", "Honeywell"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.CRITICAL,
        "battery_powered": True,
    },
    DeviceType.SIREN_ALARM: {
        "manufacturers": ["Ring", "SimpliSafe", "Honeywell", "Aeotec"],
        "protocol": DeviceProtocol.ZWAVE,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SAFE_LOCK: {
        "manufacturers": ["Yale", "SentrySafe", "Vaultek", "Hornady"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.CRITICAL,
        "battery_powered": True,
    },
    DeviceType.GARAGE_DOOR_CONTROLLER: {
        "manufacturers": ["Chamberlain", "LiftMaster", "Genie", "Ryobi"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SECURITY_KEYPAD: {
        "manufacturers": ["Ring", "SimpliSafe", "Honeywell", "DSC"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.VIDEO_DOORBELL_PRO: {
        "manufacturers": ["Ring Pro", "Nest Hello", "Arlo Essential", "Eufy"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.FLOODLIGHT_CAMERA: {
        "manufacturers": ["Ring", "Arlo", "Eufy", "Nest"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.PTZ_CAMERA: {
        "manufacturers": ["Reolink", "Hikvision", "Dahua", "Amcrest"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.INDOOR_CAMERA: {
        "manufacturers": ["Wyze", "Blink", "Ring", "Eufy"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.DRIVEWAY_SENSOR: {
        "manufacturers": ["Guardline", "Chamberlain", "SadoTech", "Hosmart"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },

    # ==========================================================================
    # LIGHTING (8 devices)
    # ==========================================================================
    DeviceType.SMART_BULB_COLOR: {
        "manufacturers": ["Philips Hue", "LIFX", "Nanoleaf", "Govee"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_BULB_WHITE: {
        "manufacturers": ["Philips Hue", "Sengled", "Wyze", "Cree"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.LIGHT_STRIP: {
        "manufacturers": ["Philips Hue", "Govee", "LIFX", "Nanoleaf"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_SWITCH: {
        "manufacturers": ["Lutron", "Leviton", "TP-Link", "Inovelli"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_DIMMER: {
        "manufacturers": ["Lutron", "Leviton", "GE", "Inovelli"],
        "protocol": DeviceProtocol.ZWAVE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_BLINDS: {
        "manufacturers": ["Lutron", "IKEA", "Hunter Douglas"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_CURTAINS: {
        "manufacturers": ["IKEA", "SwitchBot", "Aqara", "Soma"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.CEILING_FAN_LIGHT: {
        "manufacturers": ["Hunter", "Minka-Aire", "Big Ass Fans", "Fanimation"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },

    # ==========================================================================
    # CLIMATE (10 devices)
    # ==========================================================================
    DeviceType.SMART_THERMOSTAT_PRO: {
        "manufacturers": ["Nest", "Ecobee", "Honeywell Lyric", "Trane"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.TEMPERATURE_SENSOR: {
        "manufacturers": ["Ecobee", "Aqara", "SmartThings", "Govee"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.HUMIDITY_SENSOR: {
        "manufacturers": ["Aqara", "SmartThings", "Govee", "Eve"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.AIR_QUALITY_MONITOR: {
        "manufacturers": ["Awair", "Airthings", "IQAir", "uHoo"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_FAN: {
        "manufacturers": ["Dyson", "Dreo", "Levoit", "Honeywell"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_AC: {
        "manufacturers": ["LG", "Samsung", "Midea", "Frigidaire"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_HEATER: {
        "manufacturers": ["Dyson", "Heat Storm", "De'Longhi", "Dreo"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_HUMIDIFIER: {
        "manufacturers": ["Levoit", "Honeywell", "Dyson", "Govee"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_DEHUMIDIFIER: {
        "manufacturers": ["Frigidaire", "Midea", "hOmeLabs", "LG"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.HVAC_CONTROLLER: {
        "manufacturers": ["Honeywell", "Trane", "Carrier", "Lennox"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },

    # ==========================================================================
    # ENTERTAINMENT (8 devices)
    # ==========================================================================
    DeviceType.STREAMING_DEVICE: {
        "manufacturers": ["Roku", "Amazon Fire", "Apple TV", "Chromecast"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SOUNDBAR: {
        "manufacturers": ["Sonos", "Bose", "Samsung", "LG"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_DISPLAY: {
        "manufacturers": ["Amazon Echo Show", "Google Nest Hub", "Meta Portal"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.GAMING_CONSOLE: {
        "manufacturers": ["Sony PlayStation", "Microsoft Xbox", "Nintendo"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.MEDIA_SERVER: {
        "manufacturers": ["Plex", "Nvidia Shield", "Synology", "QNAP"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_PROJECTOR: {
        "manufacturers": ["Epson", "BenQ", "Optoma", "XGIMI"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.MULTI_ROOM_AUDIO: {
        "manufacturers": ["Sonos", "Bose", "Denon HEOS", "Yamaha MusicCast"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_REMOTE: {
        "manufacturers": ["Logitech Harmony", "SofaBaton", "Caavo", "BroadLink"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },

    # ==========================================================================
    # KITCHEN (10 devices)
    # ==========================================================================
    DeviceType.SMART_REFRIGERATOR: {
        "manufacturers": ["Samsung", "LG", "GE", "Whirlpool"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_OVEN: {
        "manufacturers": ["GE", "Samsung", "LG", "Whirlpool"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SMART_MICROWAVE: {
        "manufacturers": ["AmazonBasics", "GE", "Samsung", "LG"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_COFFEE_MAKER: {
        "manufacturers": ["Keurig", "Nespresso", "Breville", "Hamilton Beach"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_KETTLE: {
        "manufacturers": ["Fellow", "Breville", "Cosori", "Govee"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_TOASTER: {
        "manufacturers": ["Revolution", "Breville", "Zwilling", "Cuisinart"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_BLENDER: {
        "manufacturers": ["Vitamix", "Ninja", "NutriBullet", "KitchenAid"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_DISHWASHER: {
        "manufacturers": ["Samsung", "LG", "Bosch", "Whirlpool"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_FAUCET: {
        "manufacturers": ["Moen", "Delta", "Kohler", "Pfister"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.SMART_SCALE_KITCHEN: {
        "manufacturers": ["Drop", "Perfect Company", "Etekcity", "Greater Goods"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },

    # ==========================================================================
    # APPLIANCES (6 devices)
    # ==========================================================================
    DeviceType.SMART_WASHER: {
        "manufacturers": ["Samsung", "LG", "Whirlpool", "GE"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_DRYER: {
        "manufacturers": ["Samsung", "LG", "Whirlpool", "GE"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_IRON: {
        "manufacturers": ["Laurastar", "Rowenta", "Braun", "Philips"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_SEWING_MACHINE: {
        "manufacturers": ["Brother", "Singer", "Janome", "Bernina"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_WATER_HEATER: {
        "manufacturers": ["Rheem", "A.O. Smith", "Rinnai", "Bradford White"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_GARBAGE_DISPOSAL: {
        "manufacturers": ["InSinkErator", "Waste King", "Moen", "GE"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },

    # ==========================================================================
    # HEALTH & WELLNESS (8 devices)
    # ==========================================================================
    DeviceType.SMART_SCALE: {
        "manufacturers": ["Withings", "Fitbit", "Eufy", "Renpho"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.BLOOD_PRESSURE_MONITOR: {
        "manufacturers": ["Withings", "Omron", "QardioArm", "iHealth"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.SLEEP_TRACKER: {
        "manufacturers": ["Withings", "Eight Sleep", "Emfit", "Beautyrest"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_PILL_DISPENSER: {
        "manufacturers": ["Hero", "MedMinder", "Pill Pack", "LiveFine"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.AIR_PURIFIER: {
        "manufacturers": ["Dyson", "Coway", "Levoit", "Blueair"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_MATTRESS: {
        "manufacturers": ["Eight Sleep", "Sleep Number", "Tempur-Pedic"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.FITNESS_TRACKER_DOCK: {
        "manufacturers": ["Fitbit", "Garmin", "Apple", "Samsung"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.SMART_MIRROR: {
        "manufacturers": ["Mirror", "Tempo", "Echelon", "NordicTrack"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },

    # ==========================================================================
    # ENERGY MANAGEMENT (6 devices)
    # ==========================================================================
    DeviceType.SMART_METER: {
        "manufacturers": ["Sense", "Emporia", "Neurio"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SOLAR_INVERTER: {
        "manufacturers": ["Enphase", "SolarEdge", "SMA", "Fronius"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.BATTERY_STORAGE: {
        "manufacturers": ["Tesla Powerwall", "LG Chem", "Enphase", "Generac"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.EV_CHARGER: {
        "manufacturers": ["Tesla", "ChargePoint", "JuiceBox", "Wallbox"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.ENERGY_MONITOR: {
        "manufacturers": ["Sense", "Emporia Vue", "Curb", "Eyedro"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.SMART_CIRCUIT_BREAKER: {
        "manufacturers": ["Leviton", "Eaton", "Span", "Schneider"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },

    # ==========================================================================
    # NETWORK & INFRASTRUCTURE (6 devices)
    # ==========================================================================
    DeviceType.HUB: {
        "manufacturers": ["SmartThings", "Hubitat", "Home Assistant"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.MESH_NODE: {
        "manufacturers": ["Eero", "Google Nest", "Linksys Velop", "Orbi"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SMART_BRIDGE: {
        "manufacturers": ["Philips Hue", "Lutron", "IKEA", "Aqara"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.NETWORK_SWITCH: {
        "manufacturers": ["Ubiquiti", "Netgear", "TP-Link", "Cisco"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.RANGE_EXTENDER: {
        "manufacturers": ["TP-Link", "Netgear", "Linksys", "D-Link"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.NAS_STORAGE: {
        "manufacturers": ["Synology", "QNAP", "Western Digital", "Asustor"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },

    # ==========================================================================
    # OUTDOOR & GARDEN (8 devices)
    # ==========================================================================
    DeviceType.SMART_SPRINKLER: {
        "manufacturers": ["Rachio", "RainMachine", "Orbit B-hyve", "Wyze"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.POOL_CONTROLLER: {
        "manufacturers": ["Pentair", "Hayward", "Jandy", "Zodiac"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.WEATHER_STATION: {
        "manufacturers": ["Ambient Weather", "Davis", "Netatmo", "Acurite"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.OUTDOOR_LIGHT: {
        "manufacturers": ["Ring", "Philips Hue", "LIFX", "Eufy"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.GATE_CONTROLLER: {
        "manufacturers": ["LiftMaster", "Mighty Mule", "US Automatic", "ALEKO"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SMART_GRILL: {
        "manufacturers": ["Weber", "Traeger", "Char-Broil", "Yoder"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.GARDEN_SENSOR: {
        "manufacturers": ["Gardena", "PlantLink", "Parrot", "Xiaomi"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.PEST_REPELLER: {
        "manufacturers": ["BirdX", "Yard Sentinel", "Aspectek", "Hoont"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },

    # ==========================================================================
    # CLEANING (4 devices)
    # ==========================================================================
    DeviceType.ROBOT_VACUUM: {
        "manufacturers": ["iRobot Roomba", "Roborock", "Ecovacs", "Shark"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.ROBOT_MOP: {
        "manufacturers": ["iRobot Braava", "Roborock", "Narwal", "Ecovacs"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.WINDOW_CLEANER: {
        "manufacturers": ["Ecovacs Winbot", "Hobot", "Gladwell", "Cop Rose"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },
    DeviceType.POOL_CLEANER: {
        "manufacturers": ["Dolphin", "Polaris", "Hayward", "Zodiac"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": True,
    },

    # ==========================================================================
    # BABY & PET (6 devices)
    # ==========================================================================
    DeviceType.BABY_MONITOR: {
        "manufacturers": ["Nanit", "Owlet", "Eufy", "Infant Optics"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.SMART_CRIB: {
        "manufacturers": ["SNOO", "4moms", "Cradlewise", "Happiest Baby"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.PET_FEEDER: {
        "manufacturers": ["Petnet", "SureFeed", "PetSafe", "Whisker"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },
    DeviceType.PET_CAMERA: {
        "manufacturers": ["Furbo", "Petcube", "Wyze", "Pawbo"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.PET_DOOR: {
        "manufacturers": ["SureFlap", "PetSafe", "High Tech Pet", "Microchip"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.PET_TRACKER: {
        "manufacturers": ["Whistle", "Fi", "Tractive", "Apple AirTag"],
        "protocol": DeviceProtocol.BLE,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },

    # ==========================================================================
    # ACCESSIBILITY (4 devices)
    # ==========================================================================
    DeviceType.VOICE_ASSISTANT_HUB: {
        "manufacturers": ["Amazon Echo", "Google Home", "Apple HomePod"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": False,
    },
    DeviceType.AUTOMATED_DOOR: {
        "manufacturers": ["Autoslide", "SwiftBuild", "Door Controls", "Norton"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": False,
    },
    DeviceType.EMERGENCY_ALERT: {
        "manufacturers": ["Medical Guardian", "Life Alert", "Bay Alarm", "ADT"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.CRITICAL,
        "battery_powered": True,
    },
    DeviceType.HEARING_LOOP: {
        "manufacturers": ["Williams Sound", "Univox", "Contacta", "Ampetronic"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.LOW,
        "battery_powered": False,
    },

    # ==========================================================================
    # SAFETY SENSORS (4 devices)
    # ==========================================================================
    DeviceType.CO_DETECTOR: {
        "manufacturers": ["Nest", "First Alert", "Kidde"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.WATER_LEAK_SENSOR: {
        "manufacturers": ["Flo", "Moen", "Honeywell", "Samsung"],
        "protocol": DeviceProtocol.ZIGBEE,
        "security_level": SecurityLevel.MEDIUM,
        "battery_powered": True,
    },
    DeviceType.FLOOD_SENSOR: {
        "manufacturers": ["Flo", "Phyn", "Moen", "StreamLabs"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
    DeviceType.RADON_DETECTOR: {
        "manufacturers": ["Airthings", "Safety Siren", "Corentium", "First Alert"],
        "protocol": DeviceProtocol.WIFI,
        "security_level": SecurityLevel.HIGH,
        "battery_powered": True,
    },
}


class HomeGenerator:
    """
    Generates smart home configurations.

    Features:
    - Template-based generation (studio to mansion)
    - Realistic device placement
    - Configurable inhabitant profiles
    - Random but realistic variations
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the home generator.

        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed
        if seed is not None:
            random.seed(seed)

    def generate_from_template(
        self,
        template: HomeTemplate,
        name: str = "My Smart Home",
        num_inhabitants: Optional[int] = None,
        device_density: float = 1.0,  # 0.5 = sparse, 1.0 = normal, 1.5 = dense
    ) -> Home:
        """
        Generate a home from a template.

        Args:
            template: Home template to use
            name: Name for the home
            num_inhabitants: Number of inhabitants (None for template default)
            device_density: Device density multiplier

        Returns:
            Generated Home instance
        """
        template_config = TEMPLATE_CONFIGS[template]
        logger.info(f"Generating {template.value} home: {name}")

        # Create home config
        home_config = HomeConfig(
            template=template,
            total_area_sqm=template_config["total_area"],
            floors=template_config["floors"],
            has_garage=template_config.get("has_garage", False),
            has_garden=template_config.get("has_garden", False),
            has_basement=template_config.get("has_basement", False),
            has_smart_hub=True,
        )

        # Generate rooms
        rooms = self._generate_rooms(template_config["rooms"])

        # Determine number of inhabitants
        if num_inhabitants is None:
            num_inhabitants = template_config["typical_inhabitants"]
        inhabitants = self._generate_inhabitants(num_inhabitants)

        # Generate devices
        min_devices, max_devices = template_config["typical_devices"]
        target_devices = int((min_devices + max_devices) / 2 * device_density)
        devices = self._generate_devices(rooms, target_devices, home_config.has_smart_hub)

        # Create home
        home = Home(
            name=name,
            config=home_config,
            rooms=rooms,
            devices=devices,
            inhabitants=inhabitants,
        )

        logger.info(
            f"Generated home: {len(rooms)} rooms, {len(devices)} devices, "
            f"{len(inhabitants)} inhabitants"
        )

        return home

    def _generate_rooms(self, room_specs: list[dict]) -> list[Room]:
        """Generate rooms from specifications."""
        rooms = []
        room_counts = {}

        for spec in room_specs:
            room_type = spec["type"]
            room_counts[room_type] = room_counts.get(room_type, 0) + 1
            count = room_counts[room_type]

            # Generate name
            if count > 1:
                name = f"{room_type.value.replace('_', ' ').title()} {count}"
            else:
                name = room_type.value.replace("_", " ").title()

            room = Room(
                name=name,
                room_type=room_type,
                config=RoomConfig(
                    area_sqm=spec.get("area", 15),
                    has_window=spec.get("has_window", True),
                    has_external_door=spec.get("has_external_door", False),
                    floor_level=spec.get("floor", 0),
                ),
            )
            rooms.append(room)

        return rooms

    def _generate_inhabitants(self, count: int) -> list[Inhabitant]:
        """Generate inhabitants with realistic profiles."""
        inhabitants = []
        names = ["Alex", "Jordan", "Casey", "Morgan", "Riley", "Taylor"]

        for i in range(count):
            # First inhabitant is always an adult
            if i == 0:
                inhabitant_type = InhabitantType.ADULT
                age = random.randint(25, 55)
            elif i == 1 and count >= 2:
                # Second is usually adult or elderly
                inhabitant_type = random.choice([InhabitantType.ADULT, InhabitantType.ELDERLY])
                age = random.randint(25, 75) if inhabitant_type == InhabitantType.ADULT else random.randint(60, 85)
            else:
                # Others are children or adults
                inhabitant_type = random.choice([InhabitantType.CHILD, InhabitantType.ADULT])
                age = random.randint(5, 17) if inhabitant_type == InhabitantType.CHILD else random.randint(20, 50)

            # Generate schedule
            if inhabitant_type == InhabitantType.CHILD:
                schedule = Schedule(
                    wake_time=time(7, 0),
                    sleep_time=time(21, 0),
                    work_start=time(8, 30),  # School
                    work_end=time(15, 30),
                    works_from_home=False,
                )
            elif inhabitant_type == InhabitantType.ELDERLY:
                schedule = Schedule(
                    wake_time=time(6, 0),
                    sleep_time=time(21, 30),
                    work_start=None,
                    work_end=None,
                    works_from_home=True,  # Usually at home
                )
            else:
                works_from_home = random.random() < 0.3
                schedule = Schedule(
                    wake_time=time(random.randint(6, 8), 0),
                    sleep_time=time(random.randint(22, 24) % 24, 0),
                    work_start=time(9, 0),
                    work_end=time(17, 0),
                    works_from_home=works_from_home,
                )

            inhabitant = Inhabitant(
                name=names[i % len(names)],
                inhabitant_type=inhabitant_type,
                age=age,
                schedule=schedule,
                tech_savviness=random.uniform(0.3, 0.9),
            )
            inhabitants.append(inhabitant)

        return inhabitants

    def _generate_devices(
        self,
        rooms: list[Room],
        target_count: int,
        has_smart_hub: bool,
    ) -> list[Device]:
        """Generate devices for the home.

        This method ensures EVERY room gets at least one device (typically a light),
        then adds additional recommended devices, and finally fills to target count.
        """
        devices = []

        # Always add hub and router first
        if has_smart_hub:
            hub = self._create_device(DeviceType.HUB, None, "Smart Hub")
            devices.append(hub)

        router = self._create_device(DeviceType.ROUTER, None, "WiFi Router")
        devices.append(router)

        # PHASE 1: Ensure EVERY room has at least one device (typically a light)
        # This guarantees no room is left empty
        for room in rooms:
            room_type = RoomType(room.room_type)
            recommendations = ROOM_DEVICE_RECOMMENDATIONS.get(room_type, [])

            # Find a mandatory device for this room (prefer light, then any with min_count > 0)
            mandatory_device = None
            for device_type, min_count, max_count in recommendations:
                if device_type == DeviceType.SMART_LIGHT:
                    mandatory_device = device_type
                    break
                elif min_count > 0 and mandatory_device is None:
                    mandatory_device = device_type

            # If no mandatory device found in recommendations, default to smart light
            if mandatory_device is None:
                mandatory_device = DeviceType.SMART_LIGHT

            # Add the mandatory device to ensure room is not empty
            device = self._create_device(mandatory_device, room.id)
            room.device_ids.append(device.id)
            devices.append(device)

        # PHASE 2: Add recommended devices to each room (respecting min counts)
        for room in rooms:
            room_type = RoomType(room.room_type)
            recommendations = ROOM_DEVICE_RECOMMENDATIONS.get(room_type, [])

            for device_type, min_count, max_count in recommendations:
                # Check how many of this type already exist in the room
                existing_count = sum(
                    1 for d in devices
                    if d.room_id == room.id and d.device_type == device_type
                )

                # Add devices to meet minimum requirement
                needed = max(0, min_count - existing_count)
                for _ in range(needed):
                    device = self._create_device(device_type, room.id)
                    room.device_ids.append(device.id)
                    devices.append(device)

                # Add optional devices (up to max) if we're still under target
                if len(devices) < target_count:
                    optional = random.randint(0, max(0, max_count - min_count))
                    for _ in range(optional):
                        if len(devices) >= target_count:
                            break
                        device = self._create_device(device_type, room.id)
                        room.device_ids.append(device.id)
                        devices.append(device)

        # PHASE 3: Fill remaining slots to reach target count
        # Distribute across rooms that have fewer devices first (for balance)
        while len(devices) < target_count:
            # Sort rooms by device count (ascending) to balance distribution
            rooms_by_count = sorted(rooms, key=lambda r: len(r.device_ids))
            room = rooms_by_count[0]  # Pick room with fewest devices

            room_type = RoomType(room.room_type)
            recommendations = ROOM_DEVICE_RECOMMENDATIONS.get(room_type, [])

            if recommendations:
                device_type, _, _ = random.choice(recommendations)
            else:
                # Fallback: add a smart plug or light
                device_type = random.choice([DeviceType.SMART_LIGHT, DeviceType.SMART_PLUG])

            device = self._create_device(device_type, room.id)
            room.device_ids.append(device.id)
            devices.append(device)

        return devices

    def _create_device(
        self,
        device_type: DeviceType,
        room_id: Optional[str],
        custom_name: Optional[str] = None,
    ) -> Device:
        """Create a device with realistic configuration."""
        device_config = DEVICE_CONFIGS.get(device_type, {})

        manufacturer = random.choice(device_config.get("manufacturers", ["Generic"]))
        protocol = device_config.get("protocol", DeviceProtocol.WIFI)
        security_level = device_config.get("security_level", SecurityLevel.MEDIUM)
        battery_powered = device_config.get("battery_powered", False)

        name = custom_name or f"{manufacturer} {device_type.value.replace('_', ' ').title()}"

        # Simulate some devices having vulnerabilities
        has_vulnerability = random.random() < 0.1  # 10% chance
        default_creds = random.random() < 0.05  # 5% chance

        config = DeviceConfig(
            manufacturer=manufacturer,
            model=f"{device_type.value.upper()[:3]}-{random.randint(100, 999)}",
            firmware_version=f"{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 99)}",
            protocol=protocol,
            security_level=security_level,
            has_encryption=security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL],
            has_authentication=True,
            default_credentials=default_creds,
            known_vulnerabilities=["CVE-2023-XXXX"] if has_vulnerability else [],
        )

        state = DeviceState(
            is_on=True,
            battery_level=random.uniform(50, 100) if battery_powered else None,
            signal_strength=random.uniform(-70, -30),
            cpu_usage=random.uniform(1, 15),
            memory_usage=random.uniform(20, 50),
        )

        # Generate MAC address
        mac = ":".join([f"{random.randint(0, 255):02x}" for _ in range(6)])

        # Generate IP address (local network)
        ip = f"192.168.1.{random.randint(10, 250)}"

        return Device(
            name=name,
            device_type=device_type,
            room_id=room_id,
            config=config,
            state=state,
            ip_address=ip,
            mac_address=mac,
        )


# Global instance management
_home_generator: Optional[HomeGenerator] = None


def get_home_generator(seed: Optional[int] = None) -> HomeGenerator:
    """Get or create the global home generator instance."""
    global _home_generator
    if _home_generator is None or seed is not None:
        _home_generator = HomeGenerator(seed=seed)
    return _home_generator
