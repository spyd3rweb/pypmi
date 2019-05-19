#!/usr/bin/env python

import argparse
import pyghmi.ipmi.bmc as bmc
import sys
import asyncbmc
from esp8266bmc import Esp8266Bmc

'''
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-intelligent-platform-mgt-interface-spec-2nd-gen-v2-0-spec-update.pdf
'''

class PyPmb(asyncbmc.AsyncBmc):
    def __init__(self, authdata, port=623, loop=None):
        self.additionaldevices = 0
        self.targetbmcs = dict()

        super(PyPmb, self).__init__(authdata, port, loop)

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
    
    def cold_reset(self):
        # Reset of the BMC, not managed system, here we will exit the demo
        print('shutting down in response to BMC cold reset request')
        sys.exit(0)

    def send_bridge_request(self, request, session):
        channel = int(request['data'][0])
        addr = int(request['data'][1])
        netfn = int(request['data'][2])
        # unknownone = int(request['data'][3])
        # clientaddr = int(request['data'][4])
        # unknowntwo = int(request['data'][5]) # response address?
        command = int(request['data'][6])
        data = bytearray(request['data'][7:-1])
        print('addr: ' + str(addr) + ', channel: ' + str(channel))
        print('netfn: ' + str(request['netfn']))
        print('command: ' + str(request['command']))
        print('data: ' + bytes(request['data']).hex())

        '''
        bridge_request = { 'addr': addr, 'channel': channel}
        session.logged = 1
        response = session.raw_command(netfn,command,bridge_request)
        '''

        targetbmc = self.targetbmcs.get(addr)

        if targetbmc is not None:
            # Command Completed Normally
            session.send_ipmi_response(code=0x00)

            # for _send_ipmi_net_payload
            session.clientnetfn = netfn
            session.clientcommand = command

            print('sequencenumber: {}'.format(session.sequencenumber))
            print('timeout: {}'.format(session.timeout))
            print('localsid: {}'.format(session.localsid))

            targetrequest = {'netfn': netfn, 'command': command, 'data': data}
            targetbmc.handle_raw_request(targetrequest, session)
            return 
        
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
            print(e)

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
    mypmb = PyPmb({}, port=args.port)
    # mybmc = fakebmc.FakeBmc(mypmb.authdata,port=None)
    # mybmc = Esp8266Bmc(mypmb.authdata, {}, {}, {'host':'192.168.3.194'}, port=None, loop=mypmb.loop)
    mybmc = Esp8266Bmc(mypmb.authdata, {}, {}, {'host':'192.168.3.198'}, port=None, loop=mypmb.loop)
    mypmb.add_target(255, mybmc) 
    mypmb.listen()


if __name__ == '__main__':
    sys.exit(main())