#!/usr/bin/env python
import logging
import argparse
import sys
import asyncio
import pinbmc
from asyncbmc import AsyncThreadedObject, AsyncSerialSession
from enum import IntEnum
from itertools import chain


# https://web.csulb.edu/~pnguyen/cecs277/lecnotes/Command%20Pattern.pdf
# https://sebastiankoltun-blog.com/index.php/2018/07/08/command-handler-pattern-java-ee/

class Command(AsyncThreadedObject):
    def __init__(self, receiver, name=None, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        self.receiver = receiver

    # https://stackoverflow.com/questions/50678184/how-to-pass-additional-parameters-to-handle-client-coroutine
    @asyncio.coroutine
    async def execute(self):
        # raise NotImplementedError
        return True

class GenericCommand(Command):
    class CommandEnum(IntEnum):
        # Common
        NONE        = 0x0000
        HANDLED     = 0x0001

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(GenericCommand.CommandEnum)])

    def __init__(self, receiver, command_enum: CommandEnum = CommandEnum.NONE, loop=None):
        Command.__init__(self, receiver, loop=loop)
        self.command_enum = command_enum

class PinCommand(GenericCommand):
    class CommandEnum(IntEnum):
        # Pin
        WRITE_STATE = 0x0100
        READ_STATE  = 0x0101

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(GenericCommand.CommandEnum, PinCommand.CommandEnum)])

class SerialCommand(GenericCommand):
    class CommandEnum(IntEnum):
        # Serial
        START       = 0x0200
        STOP        = 0x0201

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(GenericCommand.CommandEnum, SerialCommand.CommandEnum)])

class CommandInvoker(AsyncThreadedObject):
    def __init__(self, retries:int=2, name=None, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        self.retries = retries

    async def invoke(self, *commands: GenericCommand):
        all_handled = True
        for command in commands:
            if command is not None:
                tries = 0
                is_handled = False
                command_name = command.command_enum.name
                while (not is_handled and tries < self.retries):
                    tries += 1
                    logging.debug("Executing Command {}, Attempt {}".format(command_name, tries))
                    try:
                        is_handled = await command.execute()
                    except Exception as e:
                        logging.error(e)

                    # status
                    logging.debug("Command {} {}".format(command_name, "Succeeded" if is_handled else "Failed"))

                if not is_handled:
                    all_handled = False
                    break
            else:
                logging.warning("Command is None!")

        return all_handled

class CommandClient(AsyncThreadedObject):
    def __init__(self, receiver, invoker: CommandInvoker=None, name=None, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        self.receiver = receiver
        self.invoker = invoker if invoker else CommandInvoker(retries=2, loop=self.loop)

    async def setup(self):
        raise NotImplementedError

class PinCommandClient(CommandClient):
     
    async def write_logic_level(self):
        raise NotImplementedError

    async def read_logic_level(self):
        raise NotImplementedError

class SerialCommandClient(CommandClient):
    async def start_shell(self, shell):
        raise NotImplementedError

    async def stop_shell(self):
        raise NotImplementedError

class CommandPin(pinbmc.DigitalPin):
    def __init__(self, pin: int, is_output: bool = True, value: bool = False, invert_logic: bool = False, loop=None):
        pinbmc.DigitalPin.__init__(self, pin, is_output, value, invert_logic, loop=loop)
        self.pin_command_client: PinCommandClient = None

    async def setup_pin_command_client(self):
        raise NotImplementedError

    async def write_logic_level(self):
        return await self.pin_command_client.write_logic_level()

    async def read_logic_level(self):
        return await self.pin_command_client.read_logic_level()

    async def setup(self):
        if self.is_valid_pin(self.pin):
            await self.setup_pin_command_client()
            if not self.pin_command_client:
                logging.warning("Pin Command Client is None!")
        else:
            logging.warning("Invalid pin {}!".format(self.pin))

class CommandSerial(AsyncSerialSession):
    def __init__(self, name=None, loop=None):
        AsyncSerialSession.__init__(self, name=name, loop=loop)
        self.serial_command_client = None
    
    async def setup_serial_command_client(self):
        raise NotImplementedError

    async def setup(self):
        await self.setup_serial_command_client()
        if not self.serial_command_client:
            logging.warning("Serial Command Client is None!")

    async def start_shell(self, shell):
        await self.serial_command_client.start_shell(shell)
        return await super().start_shell(shell)

    async def stop_shell(self):
        await self.serial_command_client.stop_shell()
        return await super().stop_shell()
   

class CommandBmc(pinbmc.PinBmc):
    pass

def main():
    parser = argparse.ArgumentParser(
        prog='commandbmc',
        description='Generic Command Pattern Baseboard Management Controller',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = CommandBmc({}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())