# domoticz-PowerWorld-heat-pump
Domoticz modbus plugin for Powerworld inverters.
This is a plugin for [Domoticz home automation system](https://www.domoticz.com) that **reads and writes parameters from and to the [PowerWorld R290 heat pumps]([https://emmeti.com](https://powerworld-e.com/content.php?cid=10))** by Modbus connection.
I used a RS485 over LAN connection to cummunicate with the inverter.

Requirements:
* python module pip -> https://pypi.org/project/pip/
    sudo apt install python3-pip
* python module modbus-crc  -> https://pypi.org/project/modbus-crc/
    sudo pip3 install modbus-crc
* Communication module Modbus USB to RS485 or Modbus TCP to RS485
    tested with Sollae CSE-H25 using RTU-over-TCP -> https://www.eztcp.com/en/products/cse-h25

Connection to CN485:
* Black = Ground
* Blue = A
* Yellow = B

![RS-485](https://github.com/user-attachments/assets/b33b0bd0-3eef-4cfc-b55e-737d282f8a35)
