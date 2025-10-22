class BrakeInfo:
    FRONT_SENSOR = "div.title:has-text('FRONT BRAKE PAD WEAR SENSOR')"
    FRONT_BRAKE = "div.title:has-text('FRONT BRAKE / BRAKE DISC')"
    REAR_BRAKE = "div.title:has-text('REAR WHEEL BRAKE / BRAKE DISC')"
    REAR_SENSOR = "div.title:has-text('REAR BRAKE / BRAKE PAD / WEAR SENSOR')"
    REAR_SENSOR_ALT = "div.title:has-text('REAR BRAKE - CONTROL MODULE EMF')"
    BRAKE_PADS = "div.title:has-text('SERVICE KIT FOR BRAKE PADS / VALUE LINE')"
    BRAKE_TABLE = "#partsList > tbody"