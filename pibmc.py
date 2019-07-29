#!/usr/bin/env python
import argparse
import sys
#import fakeRPiGPIO as GPIO
import RPi.GPIO as GPIO
import time
from pinbmc import PinBmc, DigitalPin


class PiPin(DigitalPin):
    async def setup(self):
        if self.is_valid_pin(self.pin):
            if self.is_output:  # input
                GPIO.setup(self.pin, GPIO.IN)
            else:  # output
                GPIO.setup(self.pin, GPIO.OUT, self.logic_level)

    def get_true_logic_level(self):
        return GPIO.HIGH
    
    def get_false_logic_level(self):
        return GPIO.LOW

    async def write_logic_level(self):
        if self.pin is not None:
            GPIO.output(self.pin, self.logic_level)
        raise ValueError("pin is None!")

    async def read_logic_level(self, logic_level):
        if self.pin is not None:
            self.logic_level = GPIO.input(self.pin)
        raise ValueError("pin is None!")

class PiBmc(PinBmc):
   
    def __del__(self):
        PinBmc.__del__(self)
        GPIO.cleanup()

    async def setup_power_status(self):
        # create power status input pin
        self.power_status = PiPin(self.status_pin, False, 
                                  self.initial_power_status_value, self.invert_status_pin_logic, self.loop)

        await self.power_status.setup()

    async def setup_power_button(self):
        # create power output pin
        self.power_button = PiPin(self.power_pin, True, 
                                  self.initial_power_button_value, self.invert_power_pin_logic, self.loop)

        await self.power_button.setup()

    async def setup_reset_button(self):
        # create reset output pin  
        self.reset_button = PiPin(self.reset_pin, True, 
                                  self.initial_reset_button_value, self.invert_reset_pin_logic, self.loop)

        await self.reset_button.setup()

def main():
    parser = argparse.ArgumentParser(
        prog='pibmc',
        description='Raspberry Pi Baseboard Management Controller',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = PiBmc({}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())
