# pypmi
Python Baseboard Management Controller ([BMC](https://en.wikipedia.org/wiki/Intelligent_Platform_Management_Interface#Baseboard_management_controller)) for Intelligent Platform Management Interface ([IPMI](https://en.wikipedia.org/wiki/Intelligent_Platform_Management_Interface))

*pypmi* primarly extends [pyghmi](https://github.com/openstack/pyghmi) to provide a configurable and extensible low cost BMC solution to monitor and control chassis power and enable Serial-over-Lan ([SoL](https://en.wikipedia.org/wiki/Serial_over_LAN)) using IPMI 2.0 and commodity internet-of-things (IOT) and off-the-shelf hardware. 

The PyPmb (Platform Management Bridge) allows for bridging up to 255 targets from a single IPMI address.

# Usage
## Import modules or modify the main method in existing BMCs:
*'pypmb.py'*
...

`mypmb = PyPmb({"admin":"changeme"}, name="pmb", port=args.port, loop=asyncio.get_event_loop())`

`mypmb.add_target(1, Esp8266Bmc(mypmb.authdata, {}, {}, {'host':'192.168.1.11'}, {'host':'192.168.1.11'}, {'baud_rate':'38400'}, name="cloud1", port=None, mypmb.loop))`

...

## Run using [python](https://www.python.org/)

`pip install -r requirements.txt`

`python ./pypmb.py --port 623`

## Run using [docker](https://www.docker.com/)

`docker build . -t pypmi`

`docker run --name=pypmi --rm -p 623:623/udp pypmi`

\# For Wake-on-Lan ([WoL](https://en.wikipedia.org/wiki/Wake-on-LAN)) support, run with host networking

`docker run --name=pypmi --rm --net=host -p 623:623/udp pypmi`


## Use your favorite [IPMI tool](https://en.wikipedia.org/wiki/Intelligent_Platform_Management_Interface#External_links)
### [ipmitool](https://github.com/ipmitool/ipmitool)
- Power Status

`ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 power status`

*Chassis Power is off*

- Power On/Off

`ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 power on`

*Chassis Power Control: Up/On*

- SoL activation/deactivation

`ipmitool -I lanplus -U admin -P changeme -H 127.0.0.1 -t 1 sol activate`

*\[SOL Session operational.  Use ~? for help\]*

*root@cloud1:~#*

### [openstack bifrost/ironic](https://docs.openstack.org/kolla-ansible/latest/reference/deployment-and-bootstrapping/bifrost.html)
- Power Status

`openstack baremetal node list`

```
+-------------------------+---------+---------------+-------------+--------------------+-------------+
| UUID                    | Name    | Instance UUID | Power State | Provisioning State | Maintenance |
+-------------------------+---------+---------------+-------------+--------------------+-------------+
| 00000000...000000000001 | cloud1  | None          | power off   | active             | False       |
+-------------------------+---------+---------------+-------------+--------------------+-------------+
```


- Power On/Off

`openstack baremetal node power on cloud1`

`openstack baremetal node list`

```
+-------------------------+---------+---------------+-------------+--------------------+-------------+
| UUID                    | Name    | Instance UUID | Power State | Provisioning State | Maintenance |
+-------------------------+---------+---------------+-------------+--------------------+-------------+
| 00000000...000000000001 | cloud1  | None          | power on    | active             | False       |
+-------------------------+---------+---------------+-------------+--------------------+-------------+
```

## Example BMCs:
- (Implemented/Validated) PyPmb (Platform Management Bridge)
- (Implemented/Validated) Esp8266 running [Universal I/O bridge](https://github.com/eriksl/esp8266-universal-io-bridge)
- (Skeletal/Not-Validated) Raspberry Pi using GPIO

### Example Bill of Materials (BoM) *(< $10/node)*
The Esp8266Bmc (power status requires pull down resistor on GPIO2) and Esp8266WakeOnLanBmc supports wireless power monitoring/control and SoL using an [ESP-01S Relay](https://github.com/IOT-MCU/ESP-01S-Relay-v4.0) running [Universal I/O bridge](https://github.com/eriksl/esp8266-universal-io-bridge). 

#### IOT HW
- [ESP8266 ESP-01S 5V Relay Module v4.0 (includes esp-01s)](https://www.aliexpress.com/item/32819462977.html)
- [PL2303TA USB to TTL Serial Cable 5V-power/3.3V-logic](https://www.amazon.com/JANSANE-PL2303TA-Serial-Console-Raspberry/dp/B07D9R5JFK)
- [MAX3232 RS232 to TTL Serial Port Converter](https://www.newegg.com/p/1B4-01F0-00007?Item=9SIACJR7MT2513) (optional, ttyS0 DB9 SOL)

#### miscellaneous cables and connectors
- [1.27mm .050" Pitch Rainbow Flat Ribbon Cable for 2.54mm Connectors](https://www.amazon.com/uxcell-Ribbon-Jumper-1-27mm-Meters/dp/B07FM69BGY)
- [2.54mm 2X4 8 Pins Dual Rows IDC Socket](https://www.amazon.com/Pc-Accessories-Connectors-25-Pack-Connector/dp/B017CMPM1A)
- [2.54mm 2x4 8 Pin Right Angle Male Shrouded IDC Box Header Connector](https://www.amazon.com/20Pcs-2-54mm-Shrouded-Header-Connector/dp/B07Z5B2RL1/)

<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/esp8266Bmc_hw1.jpg " width="250">

<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/esp8266Bmc_hw2.jpg" width="250">

<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/esp8266Bmc_hw3.jpg" width="250">

## Software Architecture

### Pmb example diagrams

#### [pyghmi](https://github.com/openstack/pyghmi) integration general diagram
<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/classes_pypmb.png" width="250">

#### Example Platform Management Bridge (PMB) class diagram
<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/PyPmb.png" width="250">

### Esp8266Bmc example diagrams

#### [pyghmi](https://github.com/openstack/pyghmi) integration general diagram
<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/classes_esp8266bmc.png" width="250">

#### Example Baseboard Management Controllers (BMC) class diagram
<img src="https://github.com/spyd3rweb/pypmi/blob/master/diagrams/Esp8266Bmc.png" width="250">
