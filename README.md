# pypmi
Python Baseboard Management Controller (BMC) for Intelligent Platform Management Interface (IPMI)

For my ipmi use case (openstack bifrost/ironic), I ended up extending the fakebmc from [pyghmi](https://github.com/openstack/pyghmi).  

Currently I'm using an [ESP-01S Relay](https://github.com/IOT-MCU/ESP-01S-Relay-v4.0) running [Universal I/O bridge](https://github.com/eriksl/esp8266-universal-io-bridge) to wirelessly monitor and control chassis status/power and Serial Over Lan (SOL) through ipmi.

So far, I've only tested/validated pypmi with the Esp8266Bmc and Esp8266WakeOnLanBmc (Baseboard Management Controller), but the PyPmb (Platform Management Bridge) should allow for bridging up to 255 targets from a single ipmi address:
- ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 power status

Chassis Power is off
- ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 power on

Chassis Power Control: Up/On
- ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 power status

Chassis Power is on

- ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 sol activate                               

\[SOL Session operational.  Use ~? for help]

Planned Baseboard Management Controllers (BMC):
- (Implemented/Validated) esp8266 running [Universal I/O bridge](https://github.com/eriksl/esp8266-universal-io-bridge)
- (Skeletal/Not-Validated) Raspberry Pi using GPIO

# [pyghmi](https://github.com/openstack/pyghmi) integration general diagram :
![alt text](https://github.com/spyd3rweb/pypmi/blob/master/classes_pypmb.png)
![alt text](https://github.com/spyd3rweb/pypmi/blob/master/classes_esp8266bmc.png)

# Example Platform Management Bridge (PMB) class diagram:
![alt text](https://github.com/spyd3rweb/pypmi/blob/master/PyPmb.png)

# Example Baseboard Management Controllers (BMC) class diagram:
![alt text](https://github.com/spyd3rweb/pypmi/blob/master/Esp8266Bmc.png)
