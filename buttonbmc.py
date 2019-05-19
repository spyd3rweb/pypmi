#!/usr/bin/env python

import argparse
import sys
import asyncio
import asyncbmc

BUTTON_CONFIG = {
    "initial_power_status_value": False,
    "initial_power_button_value": False,
    "initial_reset_button_value": False,
    "power_off_press_duration": 5,
    "power_on_press_duration": 1,
    "power_cycle_off_press_duration": 5,
    "power_cycle_wait_duration": 1,
    "power_cycle_on_press_duration": 1,
    "power_reset_press_duration": 1,
    "power_shutdown_press_duration": 1,
    "power_shutdown_wait_duration": 20,
}

class Button(asyncbmc.AsyncStatus):
    async def toggle(self, toggle_duration:int ):
        assert toggle_duration >= 0
        value = await self.get_value()
        await self.set_value(not value)
        await asyncio.sleep(toggle_duration, loop=self.loop)
        return await self.set_value(value)

    async def press(self, press_duration:int):
        assert press_duration >= 0
        await self.set_value(True)
        await asyncio.sleep(press_duration, loop=self.loop)
        return await self.set_value(False)

class ButtonBmc(asyncbmc.AsyncBmc):
    def __init__(self, authdata, button_config: dict, port=623, loop=None):
        self.power_button: Button = None
        self.reset_button: Button = None

        # Button
        self.button_config = BUTTON_CONFIG
        
        if button_config is not None:
            self.button_config.update(button_config)
        
        self.initial_power_status_value = self.button_config['initial'
                                                             '_power_status_value']
        self.initial_power_button_value = self.button_config['initial'
                                                             '_power_button_value']
        self.initial_reset_button_value = self.button_config['initial'
                                                             '_reset_button_value']

        self.power_off_press_duration = self.button_config['power_off_press_duration']
        self.power_on_press_duration = self.button_config['power_on_press_duration']

        self.power_cycle_off_press_duration = self.button_config['power_cycle'
                                                                 '_off_press_duration']
        self.power_cycle_wait_duration = self.button_config['power_cycle_wait_duration']
        self.power_cycle_on_press_duration = self.button_config['power_cycle'
                                                                '_on_press_duration']

        self.power_reset_press_duration = self.button_config['power_reset_press_duration']

        self.power_shutdown_press_duration = self.button_config['power_shutdown_press_duration']
        self.power_shutdown_wait_duration = self.button_config['power_shutdown_wait_duration']

        super(ButtonBmc, self).__init__(authdata, port=port, loop=loop)

    # directive 0
    async def press_power_off(self, press_duration):
        powerstate = await self.async_get_power_state()
        if (powerstate != 0 and 
            self.power_button is not None):
            await self.power_button.press(press_duration)
            powerstate = await self.async_get_power_state()
        else:
            print('already powered off')
        return powerstate
    
    async def async_power_off(self):
        print('abruptly remove power, '
              'using power off press duration: {}'
              .format(self.power_off_press_duration))
        powerstate = await self.press_power_off(self.power_off_press_duration)
        assert powerstate == 0  # off

    def power_off(self):
        # this should power down without waiting for clean shutdown
        return asyncbmc.wait_for_sync(self.async_power_off(), loop=self.loop)

    # directive 1
    async def press_power_on(self, press_duration):
        powerstate = await self.async_get_power_state()
        if (powerstate == 0 and 
            self.power_button is not None):
            await self.power_button.press(press_duration)
            powerstate = await self.async_get_power_state()
        else:
            print('already powered on')
        return powerstate

    async def async_power_on(self):
        print('power on, using power on press duration: {}'
              .format(self.power_on_press_duration))
        powerstate = await self.press_power_on(self.power_on_press_duration)
        assert powerstate == 1  # on

    def power_on(self):
        return asyncbmc.wait_for_sync(self.async_power_on(), loop=self.loop)
        
    # directive 2
    async def press_power_cycle(self, press_off_duration, 
                    wait_duration, press_on_duration):
        powerstate = await self.async_get_power_state()
        if powerstate == 1:
            self.press_power_off(press_off_duration)
            await asyncio.sleep(wait_duration, loop=self.loop)
            # assert_power_state(0)
        
        powerstate = await self.press_power_on(press_on_duration)

        return powerstate

    async def async_power_cycle(self):
        print('power cycle, using power cycle off press duration: '
              '{}, wait duration: {}, on press duration {}'
              .format(self.power_cycle_off_press_duration,
                      self.power_cycle_wait_duration,
                      self.power_cycle_on_press_duration))
        powerstate = await self.press_power_cycle(self.power_cycle_off_press_duration,
                                      self.power_cycle_wait_duration, 
                                      self.power_cycle_on_press_duration)
        assert powerstate == 1  # on

    def power_cycle(self):
        return asyncbmc.wait_for_sync(self.async_power_cycle(), loop=self.loop)

    # directive 3
    async def press_power_reset(self, press_duration):
        if self.reset_button is not None:
            await self.reset_button.press(press_duration)
        else:
            print('unable to reset due to no reset_button')
            # power_cycle
            await self.async_power_cycle()
        
    async def async_power_reset(self):
        print('power reset, using power reset press duration: {}'
                .format(self.power_reset_press_duration))
        powerstate = await self.press_power_reset(self.power_reset_press_duration)
        assert powerstate == 1  # on

    def power_reset(self):
        return asyncbmc.wait_for_sync(self.async_power_reset(), loop=self.loop)
        
    # directive 5
    async def press_power_shutdown(self, press_duration, wait_duration):
        # should attempt a clean shutdown
        powerstate = await self.async_get_power_state()
        if powerstate == 1:
            await self.press_power_off(press_duration)
            # polite wait
            await asyncio.sleep(wait_duration, loop=self.loop)
            powerstate = await self.async_get_power_state()
        else:
            print("already powered off")
        return powerstate

    async def async_power_shutdown(self):
        print('politely shut down the system, '
              'using power shutdown press duration: '
              '{} and polite wait duration: {}'
              .format(self.power_shutdown_press_duration, 
                      self.power_shutdown_wait_duration))
        powerstate = await self.press_power_shutdown(self.power_shutdown_press_duration, 
                            self.power_shutdown_wait_duration)
        assert powerstate == 0  # off

    def power_shutdown(self):
        return asyncbmc.wait_for_sync(self.async_power_shutdown(), loop=self.loop)

def main():
    parser = argparse.ArgumentParser(
        prog='buttonbmc',
        description='Generic Baseboard Management Controller with Button(s)',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = ButtonBmc({}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())