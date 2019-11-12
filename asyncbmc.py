#!/usr/bin/env python
import logging
import argparse
import sys
import asyncio
import concurrent.futures
import time
import threading 
import struct
#import pyghmi.ipmi.bmc as bmc
import pyghmi.cmd.fakebmc as fakebmc
import pyghmi.ipmi.private.serversession as serversession
import pyghmi.ipmi.console as console

AUTH_CONFIG = {'admin': 'changeme'}

def wait_for_sync(coro, timeout=None, loop=None):
    try:
        if loop is None:
            loop = asyncio.get_event_loop()

        task = asyncio.ensure_future(coro, loop=loop)
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(asyncio.wait_for(task, timeout=timeout, loop=loop), loop)
        else:
            return loop.run_until_complete(asyncio.wait_for(task, timeout=timeout, loop=loop))
    except Exception as e:
        logging.error(e)

class AsyncThreadedObject(object):
    def __init__(self, name=None, loop=None):
        self.name=name
        self.loop = loop
        self.has_new_loop = self.loop is None
        self.loop_thread = None
        
        if self.has_new_loop:
            self.loop = asyncio.new_event_loop()
            self.start_loop_thread()

    def __del__(self):
        if self.has_new_loop:
            self._stop_threaded_loop()

    def _start_threaded_loop(self):
        """Switch to new event loop and run forever"""
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()

    def _stop_threaded_loop(self):
        self.loop.stop()

    def start_loop_thread(self):
        if self.has_new_loop:
            # create loop thread
            self.loop_thread = threading.Thread(name=self.name, target=self._start_threaded_loop)
            # Start the thread
            self.loop_thread.start()

    def stop_loop_thread(self):
        if self.has_new_loop:
            self._stop_threaded_loop()

            # join thread
            if self.loop_thread:
                self.loop_thread.join(6)
                logging.debug("loop thread is alive: {}".format(self.loop_thread.isAlive()))

    def run_coroutine_threadsafe(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.loop)


class AsyncStatus(AsyncThreadedObject):
    def __init__(self, value:bool=False, name=None, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        # value
        self.value = value

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


class AsyncSession(AsyncThreadedObject):
    def __init__(self, name=None, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        self.shell_future = None

    async def start_shell(self, shell):
        # self._start_threaded_loop()
        self.shell_future = asyncio.run_coroutine_threadsafe(shell(), self.loop)

    async def stop_shell(self):
        #self._stop_threaded_loop()
        if not self.shell_future.done():
            self.shell_future.cancel()

    async def is_connected(self):
        raise NotImplementedError

    async def connect(self):
        raise NotImplementedError
       
    async def disconnect(self):
        raise NotImplementedError

    async def write(self, command_text):
        raise NotImplementedError
    
    async def read(self, num):
        raise NotImplementedError

    async def readline(self):
        raise NotImplementedError

class AsyncSerialSession(AsyncSession):
    def __init__(self, name=None, loop=None):
        AsyncSession.__init__(self, name=name, loop=loop)
        self.shell_future = None

    async def setup(self):
        raise NotImplementedError

class AsyncSerialSessionConnectionStatus(AsyncStatus):
    def __init__(self, serial_session: AsyncSerialSession=None, value:bool=False, name=None, loop=None):
        AsyncStatus.__init__(self, value=value, name=name, loop=loop)
        self.serial_session = serial_session

    async def get_value(self):
        self.value = (await self.serial_session.connect()) if self.serial_session is not None else False
        return self.value

class AsyncSessionProxy(AsyncThreadedObject):
    def __init__(self, session: serversession.ServerSession = None, name=None, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        self.lastdata = None
        self.lastcode = None
        self.session: serversession.ServerSession = session
        self._sol_handler = None

    @property
    def sol_handler(self):
        # return self.session.sol_handler
        return self._sol_handler

    @sol_handler.setter
    def sol_handler(self, v):
        self.session.sol_handler = v
        self._sol_handler = v

    def send_ipmi_response(self, data=[], code=0):
        self._send_ipmi_net_payload(data=data, code=code)

    def _send_ipmi_net_payload(self, netfn=None, command=None, data=(), code=0,
                               bridge_request=None,
                               retry=None, delay_xmit=None, timeout=None):
        self.lastdata = data
        self.lastcode = code
        if self.session is not None:
            logging.info('''IPMI Response :
                              localsid: {}
                        sequencenumber: {}
                               timeout: {}
                                 netfn: {}
                               command: {}
                                  data: {}
                                  code: {}
                        '''.format(
                            self.session.localsid,
                            self.session.sequencenumber,
                            self.session.timeout,
                            str(self.session.clientnetfn if not netfn else netfn),
                            str(self.session.clientcommand if not command else command),
                            bytes(data).hex(),
                            str(code)
                            ))
            self.session._send_ipmi_net_payload(netfn=netfn, command=command, data=data, code=code,
                                                bridge_request=bridge_request,
                                                retry=retry, delay_xmit=delay_xmit, timeout=timeout)

    def send_payload(self, payload, payload_type=1, retry=True,
                     needskeepalive=False):
        self.session.send_payload(payload,
                                  payload_type=payload_type,
                                  retry=retry,
                                  needskeepalive=needskeepalive)


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
              
        end = time.time()
        logging.debug("handle time: {}".format(end - start))

    def unregister_keepalive(self, keepaliveid):
        self.session.unregister_keepalive(keepaliveid)

class AsyncBmc(fakebmc.FakeBmc, AsyncThreadedObject):
    def __init__(self, authdata, name=None, port=623, loop=None):
        AsyncThreadedObject.__init__(self, name=name, loop=loop)
        
        # Auth
        self.authdata = AUTH_CONFIG
        
        if authdata is not None:
            self.authdata.update(authdata)

        fakebmc.FakeBmc.__init__(self, self.authdata, port=port)

        self.power_status: AsyncStatus = None
        self.serial_session: AsyncSerialSession = None
        self.bootdevice = 'default'
        self.proxies: dict = {}

    async def setup_power_status(self):
        raise NotImplementedError

    async def setup_serial_session(self):
        raise NotImplementedError

    async def setup(self):
        # raise NotImplementedError
        await self.setup_power_status()
        await self.setup_serial_session()

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
            if request['netfn'] == 6 or request['netfn'] == 24:
                if request['command'] == 1:  # get device id
                    return self.send_device_id(session)
                elif request['command'] == 2:  # cold reset
                    return session.send_ipmi_response(code=self.cold_reset())
                elif request['command'] == 72:  # activate payload
                    return self.activate_payload(request, session)
                elif request['command'] == 73:  # deactivate payload
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
            logging.error(e)

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
                logging.debug("proxying session {}".format(session.localsid))
                proxy = AsyncSessionProxy(session, loop=self.loop)
                self.proxies[session.localsid] = proxy
                #coro = self.keep_alive_during_request(request, proxy)
                coro = self.async_handle_raw_request(request, proxy)
                wait_for_sync(coro, loop=self.loop)
            else:
                proxy = self.proxies[session.localsid]
                if proxy.lastcode is not None:
                    logging.debug("using cached session response {}".format(session.localsid))
                    session.send_ipmi_response(data=proxy.lastdata, code=proxy.lastcode)
                else:
                    logging.debug("skipping duplicate session {}".format(session.localsid))
        except NotImplementedError:
            session.send_ipmi_response(code=0xc1)
        except Exception as e:
            session._send_ipmi_net_payload(code=0xff)
            logging.error(e)

    def get_boot_device(self):
        return self.bootdevice

    def set_boot_device(self, bootdevice):
        self.bootdevice = bootdevice

    def cold_reset(self):
        logging.info('re-performing setup to BMC cold reset request')
        # Reset of the BMC, not managed system, here we will exit the demo
        #sys.exit(0)
        wait_for_sync(self.setup(), loop=self.loop)

        # directive 4
    def pulse_diag(self):
        raise NotImplementedError

    async def async_get_power_state(self):
        logging.info('checking power status')
        if self.power_status is not None:
            powerstate = await self.power_status.get_value()
            self.powerstate = int(powerstate)
        else:
            logging.warning("power_status is None!")

        return self.powerstate

    def get_power_state(self):
        coro = self.async_get_power_state()
        powerstate = wait_for_sync(coro, loop=self.loop)
        return powerstate

    def is_active(self):
        # return self.powerstate == 'on'>	asyncbmc.get_power_state : 161	Python
        #return bool(self.get_power_state())
        return True

        
    async def async_iohandler(self, data):
        if data:
            if self.serial_session:
                try:
                    string = data.decode('utf-8')
                    await self.serial_session.write(string)
                except Exception as e:
                    logging.error(e)
        return True


    def iohandler(self, data):
        coro = self.async_iohandler(data)
        return wait_for_sync(coro, loop=self.loop)

    async def _poll_serial(self):
        logging.debug("Entering serial poll")
        
        while self.serial_session and self.activated:
            logging.debug("polling serial...")
            await asyncio.sleep(0)
            try:
                string = await self.serial_session.read(1024)
                if string:
                    data = bytearray(string, 'utf8')
                    if self.sol and data:
                        self.sol.send_data(data)
            except Exception as e:
                logging.error(e)
        
        # disconnect
        await self.serial_session.disconnect()
        logging.debug("Exiting serial poll")

    def activate_payload(self, request, session):
        if self.iohandler is None:
            session.send_ipmi_response(code=0x81)
        elif not self.is_active():
            session.send_ipmi_response(code=0x81)
        elif self.activated:
            session.send_ipmi_response(code=0x80)
        else:
            self.activated = True
            solport = list(struct.unpack('BB', struct.pack('!H', self.port)))
            session.send_ipmi_response(data=[0, 0, 0, 0, 1, 0, 1, 0] + solport + [0xff, 0xff])
            self.sol = console.ServerConsole(session, self.iohandler)
            # fire and forget start_shell
            asyncio.ensure_future(self.serial_session.start_shell(self._poll_serial), loop=self.loop) 
            

    def deactivate_payload(self, request, session):
        if self.iohandler is None:
            session.send_ipmi_response(code=0x81)
        elif not self.activated:
            session.send_ipmi_response(code=0x80)
        else:
            session.send_ipmi_response()
            self.sol.close()
            self.activated = False
            # fire and forget stop_shell
            asyncio.ensure_future(self.serial_session.stop_shell(), loop=self.loop)
            self.sol = None



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