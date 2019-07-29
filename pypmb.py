#!/usr/bin/env python
import logging
import asyncio
import argparse
import pyghmi.ipmi.bmc as bmc
import pyghmi.cmd.fakebmc as fakebmc
import sys
import asyncbmc
from esp8266bmc import Esp8266Bmc
from esp8266wakeonlanbmc import Esp8266WakeOnLanBmc

'''
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-intelligent-platform-mgt-interface-spec-2nd-gen-v2-0-spec-update.pdf
'''

class PyPmb(asyncbmc.AsyncBmc):
    def __init__(self, authdata, name=None, port=623, loop=None):
        self.additionaldevices = 0
        self.targetbmcs = dict()

        asyncbmc.AsyncBmc.__init__(self, authdata, name=name, port=port, loop=loop)

    def add_target(self, addr: int, newbmc: bmc.Bmc):
        if (addr >= 0 and addr <= 255): # and self.targetbmcs[addr] is None):
            if (newbmc is not None):
                self.targetbmcs[addr] = newbmc
                self.additionaldevices += 1
            else:
                raise ValueError("invalid bmc '{0}' given".format(addr))
        else:
            raise ValueError("invalid or duplicate target addr '{0}' given".format(addr))
    
    def remove_target(self, addr: int):
        if (addr >= 0 and addr <= 255):
            # bmcs[channel] = None
            self.targetbmcs.pop(addr)
            if self.additionaldevices > 0:
                self.additionaldevices -= 1
        else:
            raise ValueError("invalid target addr '{0}' given".format(addr))

    async def setup(self):
        # setup bmcs
        for mybmc in self.targetbmcs.values():
            if isinstance(mybmc, asyncbmc.AsyncBmc):
                asyncbmc.wait_for_sync(mybmc.setup(), loop=mybmc.loop)

    def send_bridge_request(self, request, session):
        channel = int(request['data'][0])
        addr = int(request['data'][1])
        netfn = int(request['data'][2])
        # unknownone = int(request['data'][3])
        # clientaddr = int(request['data'][4])
        # unknowntwo = int(request['data'][5]) # response address?
        command = int(request['data'][6])
        data = bytearray(request['data'][7:-1])

        logging.debug('''IPMI Bridge Request :
                              localsid: {}
                        sequencenumber: {}
                               timeout: {}
                                  addr: {} 
                               channel: {}
                                 netfn: {}
                               command: {}
                                  data: {}
                        '''.format(
                            session.localsid,
                            session.sequencenumber,
                            session.timeout,
                            str(addr),
                            str(channel),
                            str(netfn), #str(request['netfn']),
                            str(command), #str(request['command']),
                            bytes(data).hex() #bytes(request['data']).hex()
                            ))

        targetbmc = self.targetbmcs.get(addr)

        if targetbmc is not None:
            # Command Completed Normally
            session.send_ipmi_response(code=0x00)

            # for _send_ipmi_net_payload
            session.clientnetfn = netfn
            session.clientcommand = command

            targetrequest = {'netfn': netfn, 'command': command, 'data': data}
            if (isinstance(targetbmc, bmc.Bmc)):
                targetbmc.port = self.port
                targetbmc.handle_raw_request(targetrequest, session)
                return 
            else:
                pass
        else:
            logging.error("Target address not found {}".format(addr))

        # Requested Sensor, data, or record not present
        return session.send_ipmi_response(code=0xcb)

    def handle_raw_request(self, request, session):
        try:
            if request['netfn'] == 6:
                if request['command'] == 1:  # get device id
                    return self.send_device_id(session)
                elif request['command'] == 2:  # cold reset
                    return session.send_ipmi_response(code=self.cold_reset())
                elif request['command'] == 52:  # master-read write
                    return self.send_bridge_request(request, session)

            # Invalid Command. Used to indicate an unrecognized or unsupported command
            session.send_ipmi_response(code=0xc1)
        except NotImplementedError:
            session.send_ipmi_response(code=0xc1)
        except Exception as e:
            session._send_ipmi_net_payload(code=0xff)
            logging.error(e)

def main():
    parser = argparse.ArgumentParser(
        prog='pypmb',
        description='Python Intelligent Platform Management Bridge',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()

    # logging
    logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')

    mypmb = PyPmb({"test":"changeme"}, name="pmb", port=args.port, loop=asyncio.get_event_loop())

    loop = None #mypmb.loop

    # add target BMCs
    mypmb.add_target(1, fakebmc.FakeBmc(mypmb.authdata, port=None))
    mypmb.add_target(2, Esp8266Bmc(mypmb.authdata, {}, {}, {'host':'192.168.3.11'}, {'host':'192.168.3.11'}, {'baud_rate':'38400'}, name="server1", port=None, loop=loop))
    mypmb.add_target(3, Esp8266WakeOnLanBmc(mypmb.authdata, {}, {}, {'host':'192.168.25.12'}, {'host':'192.168.25.12'}, {'baud_rate':'38400'}, {'mac':'AA:BB:CC:DD:EE:FF', 'ip':'192.168.25.255'}, name="server02", port=None, loop=loop)) 
    
    # setup
    asyncbmc.wait_for_sync(mypmb.setup(), loop=mypmb.loop)

    mypmb.listen()
if __name__ == '__main__':
    sys.exit(main())