#!/usr/bin/env python
import logging
import argparse
import sys
import re
import asyncio
import telnetlib3
import commandbmc
import asyncbmc
import pinbmc
from enum import IntEnum
from itertools import chain

COMMAND_TELNET_CONFIG = {
    "host": '192.168.4.1',
    "port": 24,
    "baud": 115200,
    "crlf" : '\r\n',
    "response_timeout": 0.15, 
    "connection_timeout": 2.1,
    "connection_retries": 1
}

SOL_TELNET_CONFIG = {
    "host": '192.168.4.1',
    "port": 23,
    "baud": 115200,
    "crlf" : '\r\n',
    "response_timeout": 5,
    "connection_timeout": 2.1,
    "connection_retries": 1
}

# Receiver
class TelnetSession(asyncbmc.AsyncSession):
    def __init__(self, host, port, baud, crlf, response_timeout, connection_timeout = 3, connection_retries=1, name=None, loop=None):
        asyncbmc.AsyncSession.__init__(self, name=name, loop=loop)
        self.host = host
        self.port = port
        self.baud = baud
        self.crlf = crlf
        self.response_timeout = response_timeout
        self.connection_timeout = connection_timeout
        self.connection_retries = connection_retries

        self.reader = None
        self.writer = None

        self._waiter_connected = None
        self._waiter_closed = None

    async def is_connected(self):
        await asyncio.sleep(0, loop=self.loop)
        test1 = ((self._waiter_connected is not None and self._waiter_connected.done() and not self._waiter_connected.cancelled()) 
                and (self._waiter_closed is not None and not self._waiter_closed.done()))

        test2 =  (self.reader is not None and not self.reader._eof and not self.reader._exception and 
                self.writer is not None and self.writer.protocol is not None)

        connected = test1 and test2
        return connected

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

        while (not await self.is_connected() and tries < self.connection_retries):
            tries += 1
            self._waiter_connected = self.loop.create_future() #asyncio.Future()
            self._waiter_closed = self.loop.create_future() #asyncio.Future()
            # https://stackoverflow.com/questions/50678184/how-to-pass-additional-parameters-to-handle-client-coroutine
            # reader, writer = await telnetlib3.open_connection(self.telnet_host, self.telnet_port, shell=self.shell, loop=self.loop)
            
            try:
                #self.reader, self.writer = await telnetlib3.open_connection(self.host, self.port, loop=self.loop)
                self.reader, self.writer = await asyncio.shield(asyncio.wait_for(telnetlib3.open_connection(self.host, self.port, 
                                                                                             waiter_closed=self._waiter_closed, 
                                                                                             _waiter_connected=self._waiter_connected, 
                                                                                             loop=self.loop), 
                                                                self.connection_timeout, 
                                                                loop=self.loop))

            except asyncio.TimeoutError as e:
            #except Exception as e:
                # self._waiter_connected = None
                # self._waiter_closed = None
                logging.error("Connection attempt {} timed out after {}s".format(tries, self.connection_timeout))

            #await self.shell(self.reader, self.writer)
            # coro = telnetlib3.open_connection(self.telnet_host, self.telnet_port, shell=self.shell, loop=self.loop)
            # task = asyncio.ensure_future(coro)  # asyncio.create_task(coro())  # 
            # reader, writer = await asyncio.wait({task}, loop = self.loop)

        return tries < self.connection_retries
       
        
    async def disconnect(self):
        # disconnect
        if await self.is_connected():
            self.writer.protocol.eof_received()


    async def write(self, command_text):
        is_connected = await self.connect()
        if is_connected:
            # print(command_text, end='', flush=True)
            self.writer.write(command_text)
            return await self.writer.drain()

    async def read(self, num):
        is_connected = await self.connect()
        if is_connected:
            response_line = await asyncio.wait_for(self.reader.read(num), self.response_timeout, loop = self.loop)
            # print(response_line, end='', flush=True)
            return response_line

    async def readline(self):
        is_connected = await self.connect()
        if is_connected:
            response_line = await asyncio.wait_for(self.reader.readline(), self.response_timeout, loop = self.loop)
            # print(response_line, end='', flush=True)
            return response_line

class TelnetCommand(commandbmc.GenericCommand):
    class CommandEnum(IntEnum):
        # Common
        KEEP_ALIVE    = 0x1000

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(commandbmc.GenericCommand.CommandEnum, TelnetCommand.CommandEnum)])

    def get_commands(self):
        return {
                    commandbmc.GenericCommand.CommandEnum.NONE: "^]",
                    TelnetCommand.CommandEnum.KEEP_ALIVE: ""
                }

    def get_command_text(self, command_enum: CommandEnum = commandbmc.GenericCommand.CommandEnum.NONE):
        commands = self.get_commands()
        return commands.get(command_enum)

    def get_responses(self):
        return {
                    commandbmc.GenericCommand.CommandEnum.NONE: "",
                    TelnetCommand.CommandEnum.KEEP_ALIVE: ".+"
                }

    def get_response_regex(self, command_enum: CommandEnum = commandbmc.GenericCommand.CommandEnum.NONE):
        responses = self.get_responses()
        return responses.get(command_enum)

    async def handle_response_match(self, match):
        if match:
            # handled   
            self.command_enum = commandbmc.GenericCommand.CommandEnum.HANDLED # CommandEnum.NONE

    async def process_response_text(self, response_text, response_regex = None):
        # raise NotImplementedError
        receiver = self.receiver
        command_enum = self.command_enum

        if response_regex is None:
            response_regex = self.get_response_regex(command_enum)

        match = re.search(response_regex, response_text)

        if match is not None or not response_text:
            if match is not None:    
                await self.handle_response_match(match)
            else:
                logging.warning("Unexpected blank response for command {}, expected '{}'".format(command_enum.name, response_regex))
            return True
        else:
            # retry
            return False

    async def execute(self):
        receiver: TelnetCommandReceiver = self.receiver
        command_enum = self.command_enum
        command_text = self.get_command_text(command_enum)
        response_regex = self.get_response_regex(command_enum)
        response_text = ""
        response_success = False

        # send command
        await receiver.command_telnet_session.write("{}{}".format(command_text, receiver.command_telnet_session.crlf))
        # get response
        while (True and not response_success):
            try:
                # response_line = yield from reader.read(1024)
                # response_line = yield from reader.readuntil(separator=b'\n')
                # https://stackoverflow.com/questions/28609534/python-asyncio-force-timeout
                    
                response_line = await receiver.command_telnet_session.readline()

                if not response_line:
                    # EOF
                    break
                else:
                    response_text += response_line
                    response_success = await self.process_response_text(response_text, response_regex)

            except Exception as e:
                logging.error(e)
                break

        logging.debug("Command {}:\n\tEnum: {}\n\tText: {}\n\tResponse: {}\tRegex:{}"
                      .format("Successful" if response_success else "Unsuccessful", command_enum.name, command_text, response_text, response_regex))

        return response_success


class TelnetPinCommand(TelnetCommand, commandbmc.PinCommand):
    class CommandEnum(IntEnum):
        pass

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(commandbmc.PinCommand.CommandEnum, TelnetCommand.CommandEnum, TelnetPinCommand.CommandEnum)])

    async def handle_response_match(self, match):
        pin: commandbmc.CommandPin = self.receiver
        if self.command_enum in (commandbmc.PinCommand.CommandEnum.READ_STATE, commandbmc.PinCommand.CommandEnum.WRITE_STATE):
            logic_level = match.group('logic_level')
            # self.receiver.logic_level = int(logic_level)
            pin.logic_level = int(logic_level)
        await super().handle_response_match(match)

class TelnetSerialCommand(TelnetCommand, commandbmc.SerialCommand):
    class CommandEnum(IntEnum):
        pass

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(commandbmc.SerialCommand.CommandEnum, TelnetCommand.CommandEnum, TelnetSerialCommand.CommandEnum)])

class TelnetCommandReceiver(object):
    def __init__(self, command_telnet_session: TelnetSession):
        self.command_telnet_session = command_telnet_session

class TelnetCommandPin(TelnetCommandReceiver, commandbmc.CommandPin):
    def __init__(self, pin_command_telnet_session: TelnetSession, pin: int, is_output: bool = True, value: bool = False, invert_logic: bool = False, loop=None):
        commandbmc.CommandPin.__init__(self, pin, is_output, value, invert_logic, loop=loop)
        TelnetCommandReceiver.__init__(self, pin_command_telnet_session)

class TelnetCommandSerial(TelnetCommandReceiver, commandbmc.CommandSerial):
    def __init__(self, serial_command_telnet_session: TelnetSession, name=None, loop=None):
        commandbmc.CommandSerial.__init__(self, name=name, loop=loop)
        TelnetCommandReceiver.__init__(self, serial_command_telnet_session)

class TelnetBmc(commandbmc.CommandBmc):
    def __init__(self, authdata, button_config: dict, gpio_config: dict, command_telnet_config: dict, sol_telnet_config: dict, name=None, port=623, loop=None):
        commandbmc.CommandBmc.__init__(self, authdata, button_config, gpio_config, name=name, port=port, loop=loop)

        # Command Telnet Config
        self.command_telnet_config = COMMAND_TELNET_CONFIG
        
        if command_telnet_config is not None:
            self.command_telnet_config.update(command_telnet_config)

        self.command_telnet_host = self.command_telnet_config['host']
        self.command_telnet_port = self.command_telnet_config['port']
        self.command_telnet_baud = self.command_telnet_config['baud']
        self.command_telnet_crlf = self.command_telnet_config['crlf']
        self.command_telnet_response_timeout = self.command_telnet_config['response_timeout']
        self.command_telnet_connection_timeout = self.command_telnet_config['connection_timeout']
        self.command_telnet_connection_retries = self.command_telnet_config['connection_retries']

        self.command_telnet_session = None 

         # Sol Telnet Config
        self.sol_telnet_config = SOL_TELNET_CONFIG
        if sol_telnet_config is not None:
            self.sol_telnet_config.update(sol_telnet_config)

        self.sol_telnet_host = self.sol_telnet_config['host']
        self.sol_telnet_port = self.sol_telnet_config['port']
        self.sol_telnet_baud = self.sol_telnet_config['baud']
        self.sol_telnet_crlf = self.sol_telnet_config['crlf']
        self.sol_telnet_response_timeout = self.sol_telnet_config['response_timeout']
        self.sol_telnet_connection_timeout = self.sol_telnet_config['connection_timeout']
        self.sol_telnet_connection_retries = self.sol_telnet_config['connection_retries']

    async def setup_command_telnet_session(self):
        asyncio.sleep(0, loop=self.loop)
        self.command_telnet_session = TelnetSession(self.command_telnet_host, self.command_telnet_port, 
                                                    self.command_telnet_baud, self.command_telnet_crlf, 
                                                    self.command_telnet_response_timeout, self.command_telnet_connection_timeout, 
                                                    self.command_telnet_connection_retries, loop=self.loop)

    async def setup_serial_session(self):
        asyncio.sleep(0, loop=self.loop)
        self.serial_session = TelnetSession(self.sol_telnet_host, self.sol_telnet_port, 
                                            self.sol_telnet_baud, self.sol_telnet_crlf,
                                            self.sol_telnet_response_timeout, self.sol_telnet_connection_timeout, 
                                            self.sol_telnet_connection_retries, loop=self.loop)

    async def setup(self):
        await self.setup_command_telnet_session()
        await self.setup_serial_session()
        return await super().setup()
    
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
    mybmc = TelnetBmc({}, {}, {}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())