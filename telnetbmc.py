#!/usr/bin/env python

import argparse
import sys
import re
import asyncio
import telnetlib3
import commandbmc
from enum import IntEnum
from itertools import chain


__author__ = 'spyd3rweb@gmail.com'

TELNET_CONFIG = {
    "host": '192.168.4.1',
    "port": 24,
    "baud": 115200,
    "crlf" : '\r\n',
    "response_timeout": 0.1
}

class CommandEnum(IntEnum):
        KEEP_ALIVE    = 0x1000
# https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(commandbmc.CommandEnum, CommandEnum)])

# Receiver
class TelnetSession(object):
    def __init__(self, host, port, baud, crlf, response_timeout, connect_retries = 3, loop = None):
        self.host = host
        self.port = port
        self.baud = baud
        self.crlf = crlf
        self.response_timeout = response_timeout
        self.connect_retries = connect_retries

        self.reader = None
        self.writer = None

        self.loop = asyncio.get_event_loop if loop is None else loop

    def is_connected(self):
        return self.reader is not None and self.writer is not None and self.writer.protocol is not None

    async def connect(self):
        # https://telnetlib3.readthedocs.io/en/latest/intro.html
        # loop = asyncio.get_event_loop()
        # coro = telnetlib3.open_connection(self.telnet_host, self.telnet_port, shell=self.shell) # , loop=self.loop
        # https://stackoverflow.com/questions/36342899/asyncio-ensure-future-vs-baseeventloop-create-task-vs-simple-coroutine
        # https://docs.python.org/3/library/asyncio-future.html#asyncio.ensure_future
        # https://stackoverflow.com/questions/28609534/python-asyncio-force-timeout
        #task = asyncio.ensure_future(coro)  # asyncio.create_task(coro())  # 
        #reader, writer = loop.run_until_complete(asyncio.wait_for(task, 30))
        #reader, writer = self.loop.run_until_complete(coro)
        #self.loop.run_until_complete(writer.protocol.waiter_closed)
        tries = 0

        while (not self.is_connected() and tries < self.connect_retries):
            tries += 1
            
            # https://stackoverflow.com/questions/50678184/how-to-pass-additional-parameters-to-handle-client-coroutine
            # reader, writer = await telnetlib3.open_connection(self.telnet_host, self.telnet_port, shell=self.shell, loop=self.loop)
            self.reader, self.writer = await telnetlib3.open_connection(self.host, self.port, loop=self.loop)

            #await self.shell(self.reader, self.writer)
            # coro = telnetlib3.open_connection(self.telnet_host, self.telnet_port, shell=self.shell, loop=self.loop)
            # task = asyncio.ensure_future(coro)  # asyncio.create_task(coro())  # 
            # reader, writer = await asyncio.wait({task}, loop = self.loop)

        return tries < self.connect_retries
       
        
    async def disconnect(self):
        # disconnect
        if self.is_connected():
            self.writer.protocol.eof_received()

    async def write(self, command_text):
        is_connected = await self.connect()
        if is_connected:
            print(command_text, end='', flush=True)
            return self.writer.write(command_text)

    async def readline(self):
        is_connected = await self.connect()
        if is_connected:
            response_line = await asyncio.wait_for(self.reader.readline(), self.response_timeout, loop = self.loop)
            print(response_line, end='', flush=True)
            return response_line

class TelnetPinCommand(commandbmc.PinCommand):
    def get_command_text(self, command_enum: CommandEnum = CommandEnum.NONE):
        # raise NotImplementedError
        pin: TelnetPin = self.receiver
        commands = {
                    CommandEnum.NONE: "^]",
                    CommandEnum.KEEP_ALIVE: "{}".format(pin.telnet_session.crlf)
                }

        return commands.get(command_enum)

    def get_response_regex(self, command_enum: CommandEnum = CommandEnum.NONE):
        # raise NotImplementedError
        # pin: TelnetPin = self.receiver
        response_regexes = {

                    CommandEnum.NONE: "",
                    CommandEnum.KEEP_ALIVE: ".+"
                }

        return response_regexes.get(command_enum)

    async def process_response_text(self, response_text, response_regex = None):
        # raise NotImplementedError
        pin: TelnetPin = self.receiver
        command_enum = self.command_enum

        if response_regex is None:
            response_regex = self.get_response_regex(command_enum)

        match = re.search(response_regex, response_text)

        if match is not None or not response_text:
            if match is not None:    
                if command_enum in (CommandEnum.READ_STATE, CommandEnum.WRITE_STATE):
                    logic_level = match.group('logic_level')
                    # self.receiver.logic_level = int(logic_level)
                    pin.logic_level = int(logic_level)
                # handled   
                self.command_enum = CommandEnum.HANDLED # CommandEnum.NONE
            else:
                print("Unexpected blank response for command {}, expected '{}'".format(command_enum.name, response_regex))
            return True
        else:
            # retry
            return False

    async def execute(self):
        pin: TelnetPin = self.receiver
        command_enum = self.command_enum
        command_text = self.get_command_text(command_enum)
        response_regex = self.get_response_regex(command_enum)
        response_text = ""
        response_success = False

        # send command
        await pin.telnet_session.write(command_text)
        # get response  
        while (True and not response_success):
            try:
                # response_line = yield from reader.read(1024)
                # response_line = yield from reader.readuntil(separator=b'\n')
                # https://stackoverflow.com/questions/28609534/python-asyncio-force-timeout
                    
                response_line = await pin.telnet_session.readline()

                if not response_line:
                    # EOF
                    break
                else:
                    response_text += response_line
                    response_success = await self.process_response_text(response_text, response_regex)

            except Exception as e:
                print(e)
                break

        return response_success


class TelnetPin(commandbmc.CommandPin):
    def __init__(self, pin: int, telnet_session: TelnetSession = None, is_output: bool = True, value: bool = False, loop=None, invert_logic: bool = False, retries:int = 2):
        self.telnet_session = telnet_session
        super(TelnetPin, self).__init__(pin, is_output, value, loop, invert_logic, retries)

    def create_command(self, receiver, command_enum: CommandEnum = CommandEnum.NONE):
        # raise NotImplementedError
        return TelnetPinCommand(receiver, command_enum)

class TelnetBmc(commandbmc.CommandBmc):
    def __init__(self, authdata, button_config: dict, gpio_config: dict, telnet_config: dict, port=623, loop=None):
        self.telnet_config = TELNET_CONFIG
        
        if telnet_config is not None:
            self.telnet_config.update(telnet_config)

        self.telnet_host = self.telnet_config['host']
        self.telnet_port = self.telnet_config['port']
        self.telnet_baud = self.telnet_config['baud']
        self.telnet_crlf = self.telnet_config['crlf']
        self.telnet_response_timeout = self.telnet_config['response_timeout']

        self.telnet_session = TelnetSession(self.telnet_host, self.telnet_port, self.telnet_baud, self.telnet_crlf, self.telnet_response_timeout, loop = loop)

        super(TelnetBmc, self).__init__(authdata, button_config, gpio_config, port=port, loop=loop)

def main():
    parser = argparse.ArgumentParser(
        prog='telnetbmc',
        description='Generic Telnet Baseboard Management Controller',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = TelnetBmc({}, {}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())