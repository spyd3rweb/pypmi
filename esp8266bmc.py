#!/usr/bin/env python
import argparse
import sys
import telnetbmc
from enum import IntEnum
from itertools import chain

class CommandEnum(IntEnum):
    CONFIG_IO       = 0x2000
    CONFIG_IO_FLAG  = 0x2001
    VALIDATE_CONFIG = 0x2002
    VALIDATE_STATE  = 0x2003
    SAVE_CONFIG     = 0x2004

# https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(telnetbmc.CommandEnum, CommandEnum)])

class Esp8266PinCommand(telnetbmc.TelnetPinCommand):

    def get_command_text(self, command_enum: CommandEnum = CommandEnum.NONE):
        pin: Esp8266Pin = self.receiver
        commands = {
            CommandEnum.NONE: None,
            # im 0 0 doutput
            CommandEnum.CONFIG_IO: "im 0 {} {}{}".format(pin.pin,"doutput" if pin.is_output else "dinput", pin.telnet_session.crlf),
            # isf 0 0 autostart
            CommandEnum.CONFIG_IO_FLAG: "{} 0 {} autostart{}".format("isf" if pin.needs_autostart() else "icf", pin.pin, pin.telnet_session.crlf),
            # iw 0 0 0
            CommandEnum.WRITE_STATE: "iw 0 {} {}{}".format(pin.pin, pin.logic_level, pin.telnet_session.crlf),
            # ir 0 2
            CommandEnum.READ_STATE: "ir 0 {}{}".format(pin.pin, pin.telnet_session.crlf),
            # im
            CommandEnum.VALIDATE_CONFIG: "im 0 {}{}".format(pin.pin, pin.telnet_session.crlf),
            # im
            CommandEnum.VALIDATE_STATE: "im 0 {}{}".format(pin.pin, pin.telnet_session.crlf),
            # cw
            CommandEnum.SAVE_CONFIG: "cw{}".format(pin.telnet_session.crlf),

            CommandEnum.KEEP_ALIVE: "{}".format(pin.telnet_session.crlf)
        }

        return commands.get(command_enum)

    def get_response_regex(self, command_enum: CommandEnum = CommandEnum.NONE):
        pin: Esp8266Pin = self.receiver
        response_regexes = {
            CommandEnum.NONE: r"",
            # im 0 0 doutput
            CommandEnum.CONFIG_IO: r"pin:  (?P<pin>{0}), mode: digital (?P<mode>{1})\s+\[hw: digital {1}\s*\]".format(pin.pin,"output" if pin.is_output else "input"),
            # isf 0 0 autostart
            CommandEnum.CONFIG_IO_FLAG: r"flags for pin 0/(?P<pin>{}):(?P<flag>{})".format(pin.pin, "autostart" if pin.needs_autostart() else "none"),
            # iw 0 0 0
            CommandEnum.WRITE_STATE: r"digital output: \[(?P<logic_level>{})\]".format(pin.logic_level) if pin.is_output else "digital input: cannot write to gpio {}".format(pin.logic_level),
            # ir 0 2
            CommandEnum.READ_STATE: r"digital {}: \[(?P<logic_level>0|1)\]".format("output" if pin.is_output else "input"),
            # im
            CommandEnum.VALIDATE_CONFIG: r"pin:  {0}, mode: digital {1}\s+\[hw: digital {1}\s*\] flags: \[{2}\],(?: {1},)? state: (?P<state>on|off), max value: 1, info:".format(pin.pin, "output" if pin.is_output else "input", "autostart" if pin.needs_autostart() else "none"),
                # im
            CommandEnum.VALIDATE_STATE: r"pin:  {0}, mode: digital {1}\s+\[hw: digital {1}\s*\] flags: \[{2}\],(?: {1},)? state: (?P<state>{3}), max value: 1, info:".format(pin.pin,"output" if pin.is_output else "input", "autostart" if pin.needs_autostart() else "none", pin.logic_level_to_state(pin.logic_level)),
            # cw
            CommandEnum.SAVE_CONFIG: r"\> config write done, space used: \d+, free: \d+",
            # : command unknown 
            CommandEnum.KEEP_ALIVE: r"(\> empty command|\: command unknown)"
        }

        return response_regexes.get(command_enum)


class Esp8266Pin(telnetbmc.TelnetPin):
    ON_STATE = "on"
    OFF_STATE = "off"

    def get_true_logic_level(self):
        return 1
    
    def get_false_logic_level(self):
        return 0

    def logic_level_to_state(self, logic_level: int):
        return self.ON_STATE if logic_level == self.get_true_logic_level() else self.OFF_STATE

    def state_to_logic_level(self, state: str):
        return self.get_true_logic_level() if state is self.ON_STATE else self.get_false_logic_level()

    def needs_autostart(self):
        logic_level = self.value_to_logic_level(self.initial_value)
        return self.is_output and self.logic_level_to_state(logic_level) == self.ON_STATE

    def create_command(self, receiver, command_enum: CommandEnum = CommandEnum.NONE):
        # raise NotImplementedError
        return Esp8266PinCommand(receiver, command_enum)

    async def setup(self):
        if self.is_valid_pin(self.pin):
            # Check for valid config first
            has_valid_config = await self.invoke(CommandEnum.VALIDATE_CONFIG)
            if not has_valid_config:
                print("Unexpected config for pin {} of host {}!".format(self.pin, self.telnet_session.host))
                await self.invoke(CommandEnum.CONFIG_IO)
                await self.invoke(CommandEnum.CONFIG_IO_FLAG)
                await self.invoke(CommandEnum.SAVE_CONFIG)

            # Check for valid state second
            has_valid_state = await self.invoke(CommandEnum.VALIDATE_STATE)
            if not has_valid_state:
                print("Unexpected logic level {} for pin {} of host {}!".format(self.logic_level, self.pin, self.telnet_session.host))
                if self.is_output:
                    await self.invoke(CommandEnum.WRITE_STATE)
                else:
                    pass

class Esp8266Bmc(telnetbmc.TelnetBmc):
    async def setup(self):
        # create power status input pin
        # reverse logic
        self.power_status = Esp8266Pin(self.status_pin, self.telnet_session, False,
                                       self.initial_power_status_value, self.loop, self.invert_status_pin_logic)
        await self.power_status.setup()

        # create power output pin
        self.power_button = Esp8266Pin(self.power_pin, self.telnet_session, True,
                                       self.initial_power_button_value, self.loop, self.invert_power_pin_logic)
        await self.power_button.setup()

        # create reset output pin  
        self.reset_button = Esp8266Pin(self.reset_pin, self.telnet_session, True,
                                       self.initial_reset_button_value, self.loop, self.invert_reset_pin_logic)
        await self.reset_button.setup()

def main():
    parser = argparse.ArgumentParser(
        prog='esp8266bmc',
        description='Universal IO Bridge ESP8266 Baseboard Management Controller',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = Esp8266Bmc({}, {}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())