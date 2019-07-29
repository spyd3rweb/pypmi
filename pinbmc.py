#!/usr/bin/env python

import argparse
import sys
import asyncio
import buttonbmc

GPIO_CONFIG = {
    "status_pin": 2,
    "power_pin": 0,
    "reset_pin": None,
    "invert_status_pin_logic": False,
    "invert_power_pin_logic": True,
    "invert_reset_pin_logic": False,
}

class DigitalPin(buttonbmc.Button):

    def __init__(self, pin: int, is_output: bool = True, value: bool = False, invert_logic: bool = False, loop=None):
        buttonbmc.Button.__init__(self, value, loop=loop)
        self.pin: int = pin
        self.is_output: bool = is_output
        self.initial_value: bool = value
        self.invert_logic: bool = invert_logic
        self.value: bool = value
        self.logic_level = self.value_to_logic_level(value)

    async def setup(self):
        # raise NotImplementedError
        if self.is_valid_pin(self.pin):
            await asyncio.sleep(0, loop=self.loop)
            # Check for valid config first
    
    def get_true_logic_level(self):
        # raise NotImplementedError
        return True

    def get_false_logic_level(self):
        # raise NotImplementedError
        return False

    def value_to_logic_level(self, value):
        return self.get_true_logic_level() if ((value and not self.invert_logic) or (not value and self.invert_logic)) else self.get_false_logic_level()

    def logic_level_to_value(self, logic_level):
        return (logic_level == self.get_true_logic_level()) or self.invert_logic

    async def write_logic_level(self):
        # raise NotImplementedError
        await asyncio.sleep(0, loop=self.loop)

    async def read_logic_level(self):
        # raise NotImplementedError
        await asyncio.sleep(0, loop=self.loop)
        return self.logic_level

    async def set_value(self, value: bool):
        if self.pin is not None:
            self.logic_level = self.value_to_logic_level(value)
            # attempt to write logic level
            await self.write_logic_level()
            self.value = self.logic_level_to_value(self.logic_level)
            return self.value
        raise ValueError("pin is None!")

    async def get_value(self):
        if self.pin is not None:
            await self.read_logic_level()
            self.value = self.logic_level_to_value(self.logic_level)
            return self.value 
        raise ValueError("pin is None!")

    def is_valid_pin(self, s):
        # raise NotImplementedError
        try:
            int(s)
            return True
        except ValueError:
            return False
        except TypeError:
            return False


class PinBmc(buttonbmc.ButtonBmc):
    def __init__(self, authdata, button_config: dict, gpio_config: dict, name=None, port=623, loop=None):
        buttonbmc.ButtonBmc.__init__(self, authdata, button_config, name=name, port=port, loop=loop)

        # GPIO
        self.gpio_config = GPIO_CONFIG
        
        if gpio_config is not None:
            self.gpio_config.update(gpio_config)

        # status pin
        self.status_pin = self.gpio_config['status_pin']
        self.invert_status_pin_logic = self.gpio_config['invert'
                                                        '_status_pin_logic']

        # power pin
        self.power_pin = self.gpio_config['power_pin']
        self.invert_power_pin_logic = self.gpio_config['invert'
                                                       '_power_pin_logic']

        # reset pin
        self.reset_pin = self.gpio_config['reset_pin']
        self.invert_reset_pin_logic = self.gpio_config['invert'
                                                       '_reset_pin_logic']


def main():
    parser = argparse.ArgumentParser(
        prog='pinbmc',
        description='Generic Baseboard Management Controller with GPIO based Button(s)',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = buttonbmc.ButtonBmc({}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())
