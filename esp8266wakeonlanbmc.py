#!/usr/bin/env python
import logging
import argparse
import sys
import asyncio
import asyncbmc
import esp8266bmc
from enum import IntEnum
from itertools import chain
from wakeonlan import send_magic_packet

WOL_CONFIG = {
    "mac": 'AA:BB:CC:DD:EE:FF',
    "port": 9,
    "ip": '255.255.255.255'
}

class Esp8266WakeOnLanBmc(esp8266bmc.Esp8266Bmc):
    def __init__(self, authdata, button_config, gpio_config: dict, command_telnet_config: dict, sol_telnet_config: dict, uart_config: dict, wol_config: dict, name=None, port=623, loop=None):
        esp8266bmc.Esp8266Bmc.__init__(self, authdata, button_config, gpio_config, command_telnet_config, sol_telnet_config, uart_config, name=name, port=port, loop=loop)
        
        # WakeOnLan
        self.wol_config = WOL_CONFIG
        
        if wol_config is not None:
            self.wol_config.update(wol_config)
        
        self.wol_mac = self.wol_config['mac']
        self.wol_port = self.wol_config['port']
        self.wol_ip = self.wol_config['ip']

    async def press_power_on(self, press_duration):
        #powerstate = await self.async_get_power_state()
        #if (powerstate == 0 ):
        #press_duration = 3
        send_magic_packet(self.wol_mac,
                          ip_address=self.wol_ip,
                          port=self.wol_port)
        logging.debug('''WakeOnLan: 
                        mac: {}
                         ip: {}
                       port: {}'''
                       .format(self.wol_mac, 
                               self.wol_ip, 
                               self.wol_port))

        # up retries
        connection_retries = self.command_telnet_session.connection_retries
        self.command_telnet_session.connection_retries = 5

        connection_timeout = self.command_telnet_session.connection_timeout
        self.command_telnet_session.connection_timeout = 3
        try:
            await asyncio.sleep(press_duration, loop=self.loop)
            # reset waiters
            # self._waiter_connected = None
            # self._waiter_closed = None

            # connect session
            await self.command_telnet_session.connect()
            
        except Exception as e:
            logging.error(e)
        # reset retries
        self.command_telnet_session.connection_retries = connection_retries
        self.command_telnet_session.connection_timeout = connection_timeout

        powerstate = await self.async_get_power_state()
        #else:
        #    logging.info('already powered on')
        return powerstate

    async def press_power_off(self, press_duration):
        powerstate = await self.async_get_power_state()
        if (powerstate != 0 and 
            self.power_button is not None):
            try:
                await self.power_button.press(press_duration)

                # remove session
                await self.command_telnet_session.disconnect()

            except Exception as e:
                logging.error(e)

            powerstate = await self.async_get_power_state()
        else:
            logging.info('already powered off')
        return powerstate
       
    async def setup_power_status(self):
        # create power status input pin
        self.power_status =  asyncbmc.AsyncSerialSessionConnectionStatus(self.command_telnet_session, name="power_status", loop=self.loop)
        try:
            await self.power_status.setup()
        except Exception as e:
            logging.error(e)


def main():
    parser = argparse.ArgumentParser(
        prog='esp8266wakeonelanbmc',
        description='Universal IO Bridge ESP8266 Baseboard Management Controller with WakeOnLan',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = Esp8266WakeOnLanBmc({}, {}, {}, {}, {}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())