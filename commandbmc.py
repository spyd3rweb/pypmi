#!/usr/bin/env python

import argparse
import sys
import asyncio
import pinbmc
from enum import IntEnum

class CommandEnum(IntEnum):
    NONE        = 0x0000
    HANDLED     = 0x0001
    WRITE_STATE = 0x0002
    READ_STATE  = 0x0003

CommandEnum = CommandEnum

class Command(object):
    def __init__(self, receiver):
        self.receiver = receiver

    # https://stackoverflow.com/questions/50678184/how-to-pass-additional-parameters-to-handle-client-coroutine
    @asyncio.coroutine
    async def execute(self):
        # raise NotImplementedError
        return True

class PinCommand(Command):
    def __init__(self, receiver: Command, command_enum: CommandEnum = CommandEnum.NONE):
        self.command_enum = command_enum
        super(PinCommand, self).__init__(receiver)

class CommandPin(pinbmc.DigitalPin):
    def __init__(self, pin: int, is_output: bool = True, value: bool = False, loop=None, invert_logic: bool = False, retries:int = 2):
        self.retries = retries
        super(CommandPin, self).__init__(pin, is_output, value, loop, invert_logic)

    def create_command(self, receiver, command_enum: CommandEnum = CommandEnum.NONE):
        # raise NotImplementedError
        return PinCommand(receiver, command_enum)

    async def invoke(self, command_enum: CommandEnum = CommandEnum.NONE):
        tries = 0
        is_handled = False
        
        while (not is_handled and tries < self.retries):
            try:
                tries += 1
                print("Attempting to invoke command: {}, {} attempt(s)".format(command_enum.name, tries))
                command = self.create_command(self, command_enum)
                if command is not None:
                    is_handled = await command.execute()
                else:
                    print("Failed to create command: {}, {} attempt(s)".format(command_enum.name, tries))
                    break
            except Exception as e:
                print(e)

        # status
        print("{} invoking command: {}, in {} attempt(s)".format("Succeeded" if is_handled else "Failed", command_enum.name, tries))
        return is_handled

    async def write_logic_level(self):
        return await self.invoke(CommandEnum.WRITE_STATE)

    async def read_logic_level(self):
        return await self.invoke(CommandEnum.READ_STATE)

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