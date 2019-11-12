#!/usr/bin/env python
import logging
import argparse
import sys
import commandbmc
import telnetbmc
from enum import IntEnum
from itertools import chain

UART_CONFIG = {
    "bridge_port": 23,
    "tx_pin": 1,
    "rx_pin": 3,
    "baud_rate": 9600,
    "data_bits": 8,
    "stop_bits": 1,
    "parity": "none" # "none","even","odd"
}

class Esp8266TelnetCommand(telnetbmc.TelnetCommand):
    class CommandEnum(IntEnum):
        # Common
        pass

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(telnetbmc.TelnetCommand.CommandEnum, Esp8266TelnetCommand.CommandEnum)])

    def get_commands(self):
        commands: dict = super().get_commands()
        receiver: telnetbmc.TelnetCommandReceiver = self.receiver
        if receiver:
            commands.update({
                commandbmc.GenericCommand.CommandEnum.NONE: None,
           
                telnetbmc.TelnetCommand.CommandEnum.KEEP_ALIVE: ""
            })

        return commands

    def get_responses(self):
        responses = super().get_responses()
        receiver: telnetbmc.TelnetCommandReceiver = self.receiver
        if receiver:
            responses.update({
                commandbmc.GenericCommand.CommandEnum.NONE: r"",

                telnetbmc.TelnetCommand.CommandEnum.KEEP_ALIVE: r"(\> empty command|\: command unknown)"
            })
        return responses

class Esp8266TelnetPinCommand(telnetbmc.TelnetPinCommand, Esp8266TelnetCommand):
    class CommandEnum(IntEnum):
        # Pin
        VALIDATE_IO_STATE  = 0x2100
        VALIDATE_IO_CONFIG = 0x2101
        CONFIG_IO       = 0x2110
        CONFIG_IO_FLAG  = 0x2111

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(telnetbmc.TelnetPinCommand.CommandEnum, Esp8266TelnetCommand.CommandEnum, Esp8266TelnetPinCommand.CommandEnum)])


    def get_commands(self):
        commands = super().get_commands()
        pin: Esp8266TelnetCommandPin = self.receiver
        if pin:
            commands.update({
                # im
                Esp8266TelnetPinCommand.CommandEnum.VALIDATE_IO_CONFIG: "im 0 {}".format(pin.pin),
                # im
                Esp8266TelnetPinCommand.CommandEnum.VALIDATE_IO_STATE: "im 0 {}".format(pin.pin),
                 # im 0 0 doutput
                Esp8266TelnetPinCommand.CommandEnum.CONFIG_IO: "im 0 {} {}".format(pin.pin,"doutput" if pin.is_output else "dinput"),
                # isf 0 0 autostart
                Esp8266TelnetPinCommand.CommandEnum.CONFIG_IO_FLAG: "{} 0 {} autostart".format("isf" if pin.needs_autostart() else "icf", pin.pin),
                # iw 0 0 0
                commandbmc.PinCommand.CommandEnum.WRITE_STATE: "iw 0 {} {}".format(pin.pin, pin.logic_level),
                # ir 0 2
                commandbmc.PinCommand.CommandEnum.READ_STATE: "ir 0 {}".format(pin.pin)
            })

        return commands

    def get_responses(self):
        responses = super().get_responses()
        pin: Esp8266TelnetCommandPin = self.receiver
        if pin:
            responses.update({
                 # im
                Esp8266TelnetPinCommand.CommandEnum.VALIDATE_IO_CONFIG: r"pin:  {0}, mode: digital {1}\s+\[hw: digital {1}\s*\] flags: \[{2}\],(?: {1},)? state: (?P<state>on|off), max value: 1, info:".format(pin.pin, "output" if pin.is_output else "input", "autostart" if pin.needs_autostart() else ""),
                # im
                Esp8266TelnetPinCommand.CommandEnum.VALIDATE_IO_STATE: r"pin:  {0}, mode: digital {1}\s+\[hw: digital {1}\s*\] flags: \[{2}\],(?: {1},)? state: (?P<state>{3}), max value: 1, info:".format(pin.pin,"output" if pin.is_output else "input", "autostart" if pin.needs_autostart() else "", pin.logic_level_to_state(pin.logic_level)),
                # im 0 0 doutput
                Esp8266TelnetPinCommand.CommandEnum.CONFIG_IO: r"pin:  (?P<pin>{0}), mode: digital (?P<mode>{1})\s+\[hw: digital {1}\s*\]".format(pin.pin,"output" if pin.is_output else "input"),
                # isf 0 0 autostart
                Esp8266TelnetPinCommand.CommandEnum.CONFIG_IO_FLAG: r"flags for pin 0/(?P<pin>{}):(?P<flag>{})".format(pin.pin, "autostart" if pin.needs_autostart() else ""),
                # iw 0 0 0
                commandbmc.PinCommand.CommandEnum.WRITE_STATE: r"digital output: \[(?P<logic_level>{})\]".format(pin.logic_level) if pin.is_output else "digital input: cannot write to gpio {}".format(pin.logic_level),
                # ir 0 2
                commandbmc.PinCommand.CommandEnum.READ_STATE: r"digital {}: \[(?P<logic_level>0|1)\]".format("output" if pin.is_output else "input")
            })

        return responses

class Esp8266TelnetSerialCommand(telnetbmc.TelnetSerialCommand, Esp8266TelnetCommand):

    class CommandEnum(IntEnum):
        VALIDATE_UART_BRIDGE_PORT_CONFIG  = 0x2201
        VALIDATE_UART_RX_CONFIG  = 0x2202
        VALIDATE_UART_TX_CONFIG  = 0x2203
        VALIDATE_UART_BAUD_CONFIG  = 0x2204
        VALIDATE_UART_DATA_BITS_CONFIG  = 0x2205
        VALIDATE_UART_STOP_BITS_CONFIG  = 0x2206
        VALIDATE_UART_PARITY_CONFIG  = 0x2207
        VALIDATE_FLAG_LOG_TO_UART = 0x2208
        CONFIG_UART_BRIDGE_PORT = 0x2211
        CONFIG_UART_RX = 0x2212
        CONFIG_UART_TX = 0x2213
        CONFIG_UART_BAUD    = 0x2214
        CONFIG_UART_DATA_BITS= 0x2215
        CONFIG_UART_STOP_BITS= 0x2216
        CONFIG_UART_PARITY= 0x2217
        CONFIG_FLAG_LOG_TO_UART = 0x2218

    # https://stackoverflow.com/questions/33679930/how-to-extend-python-enum
    #CommandEnum = IntEnum('Idx', [(i.name, i.value) for i in chain(telnetbmc.TelnetSerialCommand.CommandEnum, Esp8266TelnetCommand.CommandEnum, Esp8266TelnetSerialCommand.CommandEnum)])

    def get_commands(self):
        commands = super().get_commands()
        serial: Esp8266TelnetCommandSerial = self.receiver
        if serial:
            commands.update({
                # bp
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_BRIDGE_PORT_CONFIG: r"bp",
                # im 0 1
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_TX_CONFIG: r"im 0 {}".format(serial.tx_pin),
                # im 0 3
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_RX_CONFIG: r"im 0 {}".format(serial.rx_pin),
                # ub 0 38400
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_BAUD_CONFIG: r"ub 0",
                # ud 0 8
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_DATA_BITS_CONFIG: r"ud 0",
                # us 0 1
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_STOP_BITS_CONFIG: r"us 0",
                # up 0 none
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_PARITY_CONFIG: r"up 0",
                # fu
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_FLAG_LOG_TO_UART: r"fu",
                # bp 23
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_BRIDGE_PORT: r"bp {}".format(serial.bridge_port),
                # im 0 1 uart
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_RX: r"im 0 {} uart".format(serial.rx_pin),
                # im 0 3 uart
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_TX: r"im 0 {} uart".format(serial.tx_pin),
                # ub 0 38400
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_BAUD: r"ub 0 {}".format(serial.baud_rate),
                # ud 0 8
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_DATA_BITS: r"ud 0 {}".format(serial.data_bits),
                # us 0 1
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_STOP_BITS: r"us 0 {}".format(serial.stop_bits),
                # up 0 none
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_PARITY: r"up 0 {}".format(serial.parity),
                # fu log-to-uart
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_FLAG_LOG_TO_UART: r"fu log-to-uart"
            })

        return commands

    def get_responses(self):
        responses = super().get_responses()
        serial: Esp8266TelnetCommandSerial = self.receiver
        if serial:
            responses.update({
                # port: 23
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_BRIDGE_PORT_CONFIG: r"\> port: {}".format(serial.bridge_port),
                # im 0 1
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_TX_CONFIG: r"pin:  {}, mode: uart\s+\[hw: uart\s+\] flags: \[\], uart, max value: 255, info: uart 0, pin: tx, autofill: no, character: 0x00".format(serial.tx_pin),
                # im 0 3
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_RX_CONFIG: r"pin:  {}, mode: uart\s+\[hw: uart\s+\] flags: \[\], uart, max value: 255, info: uart 0, pin: rx".format(serial.rx_pin),
                # ub 0 38400
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_BAUD_CONFIG: r"\> baudrate\[0\]: {}".format(serial.baud_rate),
                # ud 0 8
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_DATA_BITS_CONFIG: r"data bits\[0\]: {}".format(serial.data_bits),
                # us 0 1
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_STOP_BITS_CONFIG: r"\> stop bits\[0\]: {}".format(serial.stop_bits),
                # up 0 none
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_PARITY_CONFIG: r"parity\[0\]: {}".format("none" if serial.parity in {"none", 0, None, ""} else 
                                                                                                            "odd"  if serial.parity in {"odd", 1} else
                                                                                                            "even" if serial.parity in {"even", 2} else serial.parity),
                # fu
                Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_FLAG_LOG_TO_UART: r">\s+no log-to-uart",
                # bp 23
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_BRIDGE_PORT: r"\> port: {}".format(serial.bridge_port),
                # im 0 1 uart
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_TX: r"pin:  {}, mode: uart\s+\[hw: uart\s+\] flags: \[\], uart, max value: 255, info: uart 0, pin: tx, autofill: no, character: 0x00".format(serial.tx_pin),
                # im 0 3 uart
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_RX: r"pin:  {}, mode: uart\s+\[hw: uart\s+\] flags: \[\], uart, max value: 255, info: uart 0, pin: rx".format(serial.rx_pin),
                # ub 0 38400
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_BAUD: r"\> baudrate\[0\]: {}".format(serial.baud_rate),
                # ud 0 8
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_DATA_BITS: r"(\> cannot set config|data bits\[0\]: {})".format(serial.data_bits),
                # us 0 1
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_STOP_BITS: r"(\> cannot delete config \(default values\)|data bits\[0\]: {})".format(serial.data_bits),
                # up 0 none
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_PARITY: r"(none\> cannot set config|parity\[0\]: {})".format("none" if serial.parity in {"none", 0, None, ""} else 
                                                                                                                                "odd"  if serial.parity in {"odd", 1} else
                                                                                                                                "even" if serial.parity in {"even", 2} else serial.parity),
                #fu log-to-uart 
                Esp8266TelnetSerialCommand.CommandEnum.CONFIG_FLAG_LOG_TO_UART: r">\s+no log-to-uart",
            })

        return responses


class Esp8266TelnetPinCommandClient(commandbmc.PinCommandClient):
    async def setup(self):
        if self.receiver:
            pin: Esp8266TelnetCommandPin = self.receiver
            if pin:
                has_connection = await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, telnetbmc.TelnetCommand.CommandEnum.KEEP_ALIVE, loop=self.loop))
                if has_connection:
                    # Check for valid config first
                    has_valid_config = await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, Esp8266TelnetPinCommand.CommandEnum.VALIDATE_IO_CONFIG, loop=self.loop))
                    if not has_valid_config:
                        logging.debug("Unexpected config for pin {} of host {}!".format(pin.pin, pin.command_telnet_session.host))
                        await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, Esp8266TelnetPinCommand.CommandEnum.CONFIG_IO, loop=self.loop),
                                                  Esp8266TelnetPinCommand(self.receiver, Esp8266TelnetPinCommand.CommandEnum.CONFIG_IO_FLAG, loop=self.loop))

                    # Check for valid state second
                    has_valid_state = await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, Esp8266TelnetPinCommand.CommandEnum.VALIDATE_IO_STATE, loop=self.loop))
                    if not has_valid_state:
                        logging.debug("Unexpected logic level {} for pin {}!".format(pin.logic_level, pin.pin))
                        if pin.is_output:
                            await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, commandbmc.PinCommand.CommandEnum.WRITE_STATE, loop=self.loop))
                        else:
                            pass
                else:
                    logging.warn("No connection available for pin {}!".format(pin))
            else:
                logging.warn("Unexpected receiver type {}, expecting {}!".format(type(self.receiver).__name__,type(Esp8266TelnetCommandPin).__name__))
        else:
            logging.error("Receiver is None!")

    async def write_logic_level(self):
        await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, commandbmc.PinCommand.CommandEnum.WRITE_STATE, loop=self.loop))

    async def read_logic_level(self):
        await self.invoker.invoke(Esp8266TelnetPinCommand(self.receiver, commandbmc.PinCommand.CommandEnum.READ_STATE, loop=self.loop))

class Esp8266TelnetSerialCommandClient(commandbmc.SerialCommandClient):
    async def setup(self):
        if self.receiver:
            serial: Esp8266TelnetCommandSerial = self.receiver
            if serial:
                has_connection = await self.invoker.invoke(Esp8266TelnetSerialCommand(self.receiver, telnetbmc.TelnetCommand.CommandEnum.KEEP_ALIVE, loop=self.loop))
                if has_connection:
                    # Check for valid uart config first
                    has_valid_config = await self.invoker.invoke(Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_FLAG_LOG_TO_UART, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_BRIDGE_PORT_CONFIG, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_TX_CONFIG, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_RX_CONFIG, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_BAUD_CONFIG, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_DATA_BITS_CONFIG, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_STOP_BITS_CONFIG, loop=self.loop),
                                                                 Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.VALIDATE_UART_PARITY_CONFIG, loop=self.loop))
                    if not has_valid_config:
                        logging.debug("Unexpected config for serial command host {}!".format(serial.command_telnet_session.host))
                        await self.invoker.invoke(Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_FLAG_LOG_TO_UART, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_BRIDGE_PORT, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_TX, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_RX, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_BAUD, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_STOP_BITS, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_DATA_BITS, loop=self.loop),
                                                  Esp8266TelnetSerialCommand(self.receiver, Esp8266TelnetSerialCommand.CommandEnum.CONFIG_UART_PARITY, loop=self.loop))
                else:
                    logging.warn("No connection available for serial host {}!".format(serial.command_telnet_session.host))

    async def start_shell(self, shell):
        # raise NotImplementedError
        pass

    async def stop_shell(self):
        # raise NotImplementedError
        pass

class Esp8266TelnetCommandPin(telnetbmc.TelnetCommandPin):
    ON_STATE = "on"
    OFF_STATE = "off"

    async def setup_pin_command_client(self):
        self.pin_command_client = Esp8266TelnetPinCommandClient(self, invoker=None, loop=self.loop)
        await self.pin_command_client.setup()

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

class Esp8266TelnetCommandSerial(telnetbmc.TelnetCommandSerial):
    def __init__(self, bridge_port: int=23, tx_pin:int=1, rx_pin:int=3, baud_rate=38400, data_bits:int=8, stop_bits:int=1, parity_bits:int=0, 
                 serial_command_session: telnetbmc.TelnetSession=None, name=None, loop=None):
        telnetbmc.TelnetCommandSerial.__init__(self, serial_command_session, name=name, loop=loop)
        self.bridge_port = bridge_port
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        self.baud_rate = baud_rate
        self.data_bits = data_bits
        self.stop_bits = stop_bits
        self.parity = parity_bits

    async def setup_serial_command_client(self):
        self.serial_command_client = Esp8266TelnetSerialCommandClient(self, invoker=None, loop=self.loop)
        await self.serial_command_client.setup()

class Esp8266Bmc(telnetbmc.TelnetBmc):
    def __init__(self, authdata, button_config: dict, gpio_config: dict, command_telnet_config: dict, sol_telnet_config: dict, uart_config: dict, name=None, port=623, loop=None):
        telnetbmc.TelnetBmc.__init__(self, authdata, button_config, gpio_config, command_telnet_config, sol_telnet_config, name=name, port=port, loop=loop)
        # Pin Telnet Config
        self.uart_config = UART_CONFIG
        
        if uart_config is not None:
            self.uart_config.update(uart_config)

        self.uart_config_bridge_port = self.uart_config['bridge_port']
        self.uart_config_tx_pin = self.uart_config['tx_pin']
        self.uart_config_rx_pin = self.uart_config['rx_pin']
        self.uart_config_baud_rate = self.uart_config['baud_rate']
        self.uart_config_data_bits = self.uart_config['data_bits']
        self.uart_config_stop_bits = self.uart_config['stop_bits']
        self.uart_config_parity = self.uart_config['parity']

    async def setup_power_status(self):
        # create power status input pin
        # reverse logic
        
        self.power_status = Esp8266TelnetCommandPin(self.command_telnet_session, self.status_pin, False,
                                                    self.initial_power_status_value, 
                                                    self.invert_status_pin_logic,
                                                    loop=self.loop)

        try:
            await self.power_status.setup()
        except Exception as e:
            logging.error(e)
        

    async def setup_power_button(self):
         # create power output pin
        self.power_button =  Esp8266TelnetCommandPin(self.command_telnet_session, self.power_pin, True,
                                                     self.initial_power_button_value,
                                                     self.invert_power_pin_logic, 
                                                     loop=self.loop)

        try:
            await self.power_button.setup()
        except Exception as e:
            logging.error(e)

    async def setup_reset_button(self):
        # create reset output pin  
        self.reset_button =  Esp8266TelnetCommandPin(self.command_telnet_session, self.reset_pin, True,
                                                     self.initial_reset_button_value, 
                                                     self.invert_reset_pin_logic, 
                                                     loop=self.loop)

        try:
            await self.reset_button.setup()
        except Exception as e:
            logging.error(e)

    async def setup_serial_session(self):
         # create serial command invoker
        command_serial = Esp8266TelnetCommandSerial(self.uart_config_bridge_port, 
                                                    self.uart_config_tx_pin,
                                                    self.uart_config_rx_pin,
                                                    self.uart_config_baud_rate,
                                                    self.uart_config_data_bits,
                                                    self.uart_config_stop_bits,
                                                    self.uart_config_parity,
                                                    self.command_telnet_session, loop=self.loop)

        try:
            await command_serial.setup()
            await super().setup_serial_session()
        except Exception as e:
            logging.error(e)
       
        

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
    mybmc = Esp8266Bmc({}, {}, {}, {}, {}, {}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())