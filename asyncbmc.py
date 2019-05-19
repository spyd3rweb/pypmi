#!/usr/bin/env python

import argparse
import sys
import asyncio
import concurrent.futures
import time
#import pyghmi.ipmi.bmc as bmc
import pyghmi.cmd.fakebmc as fakebmc
import pyghmi.ipmi.private.serversession as serversession

AUTH_CONFIG = {'admin': 'PleaseChangeMe'}

def wait_for_sync(coro, timeout=None, loop=None):
    try:
        if loop is None:
            loop = asyncio.get_event_loop()

        task = asyncio.ensure_future(coro, loop=loop)
        return loop.run_until_complete(asyncio.wait_for(task, timeout=timeout, loop=loop))

    except Exception as e:
        print(e)

class AsyncStatus(object):
    def __init__(self, value:bool=False, loop=None):
        # value
        self.value = value

         # loop
        self.loop = asyncio.get_event_loop() if loop is None else loop

    async def setup(self):
        # raise NotImplementedError
        await asyncio.sleep(0, loop=self.loop)

    # set
    async def set_value(self, value: bool):
        # raise NotImplementedError
        self.value = value
        return self.value

    # get
    async def get_value(self):
        # raise NotImplementedError
        return self.value

class AsyncSessionProxy(object):
    def __init__(self, session: serversession.ServerSession = None, loop=None):
        self.lastdata = None
        self.lastcode = None
        self.session: serversession.ServerSession = session
        self.loop = asyncio.get_event_loop() if loop is None else loop

    def send_ipmi_response(self, data=[], code=0):
        self._send_ipmi_net_payload(data=data, code=code)

    def _send_ipmi_net_payload(self, netfn=None, command=None, data=(), code=0,
                               bridge_request=None,
                               retry=None, delay_xmit=None, timeout=None):
        self.lastdata = data
        self.lastcode = code
        if self.session is not None:
            self.session._send_ipmi_net_payload(netfn=netfn, command=command, data=data, code=code,
                                                bridge_request=bridge_request,
                                                retry=retry, delay_xmit=delay_xmit, timeout=timeout)

    async def _keepalive_while(self, future: concurrent.futures.Future, interval: float = None):
        start = time.time()
        interval = self.session.timeout/2 if interval is None else interval
        if future is not None and self.session is not None:
            # Keep alives are only usefull for sol
            # self.session._customkeepalives = 0  # dict {}
            # self.session.incommand = False  #True
            # self.session._keepalive()
            task = asyncio.ensure_future(future, loop=self.loop)

            while not task.done():  
                await asyncio.sleep(interval, loop=self.loop)
                # print("Send keepalive after {} seconds".format(interval))                
        end = time.time()
        print("handle time: {}".format(end - start))

class AsyncBmc(fakebmc.FakeBmc):
    def __init__(self, authdata, port=623, loop=None):
        self.power_status: AsyncStatus = None
        self.bootdevice = 'default'
        self.proxies: dict = {}

        # Auth
        self.authdata = AUTH_CONFIG
        
        if authdata is not None:
            self.authdata.update(authdata)

        # loop
        self.loop = asyncio.get_event_loop() if loop is None else loop

        coro = self.setup()

        wait_for_sync(coro, loop=self.loop)

        super(AsyncBmc, self).__init__(self.authdata, port=port)

    async def setup(self):
       # raise NotImplementedError
        return await asyncio.sleep(0, loop=self.loop)

    async def async_power_off(self):
        raise NotImplementedError

    async def async_power_on(self):
        raise NotImplementedError

    async def async_power_cycle(self):
        raise NotImplementedError

    async def async_power_reset(self):
        raise NotImplementedError

    async def async_pulse_diag(self):
        raise NotImplementedError

    async def async_power_shutdown(self):
        raise NotImplementedError

    async def async_get_chassis_status(self, session):
        try:
            powerstate = await self.async_get_power_state()
        except NotImplementedError:
            return session.send_ipmi_response(code=0xc1)
        if powerstate not in (0, 1):
            raise Exception('BMC implementation mistake')
        statusdata = [powerstate, 0, 0]
        session.send_ipmi_response(data=statusdata)

    async def async_control_chassis(self, request, session):
        rc = 0
        try:
            directive = request['data'][0]
            if directive == 0:
                # rc = self.power_off()
                rc = await self.async_power_off()
            elif directive == 1:
                # rc = self.power_on()
                rc = await self.async_power_on()
            elif directive == 2:
                # rc = self.power_cycle()
                rc = await self.async_power_cycle()
            elif directive == 3:
                # rc = self.power_reset()
                rc = await self.async_power_reset()
            elif directive == 4:
                # i.e. Pulse a diagnostic interrupt(NMI) directly
                # rc = self.pulse_diag()
                rc = await self.async_pulse_diag()
            elif directive == 5:
                # rc = self.power_shutdown()
                rc = await self.async_power_shutdown()
            if rc is None:
                rc = 0
            session.send_ipmi_response(code=rc)
        except NotImplementedError:
            session.send_ipmi_response(code=0xcc)

    async def async_handle_raw_request(self, request, session):
        try:
            if request['netfn'] == 6:
                if request['command'] == 1:  # get device id
                    return self.send_device_id(session)
                elif request['command'] == 2:  # cold reset
                    return session.send_ipmi_response(code=self.cold_reset())
                elif request['command'] == 0x48:  # activate payload
                    return self.activate_payload(request, session)
                elif request['command'] == 0x49:  # deactivate payload
                    return self.deactivate_payload(request, session)
            elif request['netfn'] == 0:
                if request['command'] == 1:  # get chassis status
                    # return self.get_chassis_status(session)
                    return await self.async_get_chassis_status(session)
                elif request['command'] == 2:  # chassis control
                    # return self.control_chassis(request, session)
                    return await self.async_control_chassis(request, session)
                elif request['command'] == 8:  # set boot options
                    return self.set_system_boot_options(request, session)
                elif request['command'] == 9:  # get boot options
                    return self.get_system_boot_options(request, session)
            session.send_ipmi_response(code=0xc1)
        except NotImplementedError:
            session.send_ipmi_response(code=0xc1)
        except Exception as e:
            session._send_ipmi_net_payload(code=0xff)
            print(e)

    async def keep_alive_during_request(self, request, proxy: AsyncSessionProxy):
        # http://blog.mathieu-leplatre.info/some-python-3-asyncio-snippets.html
        # Create a limited thread pool.
        if proxy is not None and request is not None:
            '''
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # future1 = executor.submit(super(AsyncBmc, self).handle_raw_request, request, proxy)
                # future2 = executor.submit(proxy._keepalive_while, future1)
                future1 = self.loop.run_in_executor(executor, self.async_handle_raw_request, request, proxy)
                future2 = self.loop.run_in_executor(executor, proxy._keepalive_while, future1)
                future_tasks = [future1, future2]
                results = await asyncio.gather(*future_tasks, loop = self.loop, return_exceptions=True)
                #completed, pending = await asyncio.wait(blocking_tasks, loop = self.loop)
                #results = [t.result() for t in completed]
            '''
            coro1 = self.async_handle_raw_request(request, proxy)
            future1 = asyncio.ensure_future(coro1, loop=self.loop)
            coro2 = proxy._keepalive_while(future1)
            coros = [future1, coro2]
            results = await asyncio.gather(*coros, loop=self.loop, return_exceptions=True)
            return results

    def handle_raw_request(self, request, session):
        try:
            if session.localsid not in self.proxies:
                proxy = AsyncSessionProxy(session, loop=self.loop)
                self.proxies[session.localsid] = proxy
                coro = self.keep_alive_during_request(request, proxy)
                wait_for_sync(coro, loop=self.loop)
            else:
                proxy = self.proxies[session.localsid]
                session.send_ipmi_response(data=proxy.lastdata, code=proxy.lastcode)
        except NotImplementedError:
            session.send_ipmi_response(code=0xc1)
        except Exception as e:
            session._send_ipmi_net_payload(code=0xff)
            print(e)

    def get_boot_device(self):
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        self.bootdevice = bootdevice

    def cold_reset(self):
        # Reset of the BMC, not managed system, here we will exit the demo
        print('shutting down in response to BMC cold reset request')
        sys.exit(0)

        # directive 4
    def pulse_diag(self):
        raise NotImplementedError

    async def async_get_power_state(self):
        if self.power_status is not None:
            powerstate = await self.power_status.get_value()
            self.powerstate = int(powerstate)

        return self.powerstate

    def get_power_state(self):
        coro = self.async_get_power_state()
        powerstate = wait_for_sync(coro, loop=self.loop)
        return powerstate

    def is_active(self):
        # return self.powerstate == 'on'>	asyncbmc.get_power_state : 161	Python

        return bool(self.get_power_state())

    def iohandler(self, data):
        print(data)
        if self.sol:
            self.sol.send_data(data)

def main():
    parser = argparse.ArgumentParser(
        prog='asyncbmc',
        description='Generic Baseboard Management Controller with Async loop',
        conflict_handler='resolve'
    )
    parser.add_argument('--port',
                        dest='port',
                        type=int,
                        default=623,
                        help='Port to listen on; defaults to 623')
    args = parser.parse_args()
    mybmc = AsyncBmc({}, port=args.port)
    mybmc.listen()


if __name__ == '__main__':
    sys.exit(main())