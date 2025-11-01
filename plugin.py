#!/usr/bin/env python3
# https://github.com/Mike19700/domoticz-PowerWorld-heat-pump

"""
PowerWorld-Modbus Heat Pump. The Python plugin for Domoticz
Original Author: Mike70
Cleaned-up version
"""

"""
<plugin key="PowerWorld" name="PowerWorld heatpump" author="Mike70 / cleaned" version="1.0.1" wikilink="https://www.domoticz.com/wiki/Plugins" externallink="https://www.powerworld.com/">
    <description>
        <h2>Domoticz Powerworld heat pump RS-485 to LAN plugin</h2>
        Get values from the heat pump, and change them.<br/>
        <b>NO WARRANTY: USE AT YOUR OWN RISK!</b>
    </description>
    <params>
        <param field="Address" label="IP Address" width="200px" required="false" default="127.0.0.1" />
        <param field="Port" label="TCP Port" width="200px" required="false" default="1470" />
        <param field="Mode1" label="Device ID" width="40px" required="true" default="1" />
        <param field="Mode2" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz  # tested on Python 3.9.2 in Domoticz 2024.7
import time
import socket
import binascii

from modbus_crc import add_crc, check_crc


SOCKET_TIMEOUT = 2.0         # seconds
MAX_RETRIES = 2              # modest retry to avoid hanging Domoticz


class BasePlugin:
    def __init__(self):
        # number of heartbeats to wait before next read; Domoticz HB is 10s -> 3*10s = 30s
        self.runInterval = 3
        return

    def onStart(self):
        Domoticz.Log("PowerWorld-Modbus plugin start")
        self.runInterval = 3

        # Devices aanmaken
        # 1. Operation mode (selector)
        if 1 not in Devices:
            opt = {
                "LevelNames": "Off|Hot water|Heating|Cooling|Hot water + heating|Hot water + cooling",
                "LevelOffHidden": "false",
                "SelectorStyle": "1"
            }
            Domoticz.Device(Name="Operation mode", Unit=1, Type=244, Subtype=62, Switchtype=18, Options=opt, Used=1).Create()

        if 2 not in Devices:
            Domoticz.Device(Name="Water inlet temp.", Unit=2, Type=80, Subtype=5, Used=1).Create()
        if 3 not in Devices:
            Domoticz.Device(Name="Water outlet temp.", Unit=3, Type=80, Subtype=5, Used=1).Create()
        if 4 not in Devices:
            Domoticz.Device(Name="Ambient temp.", Unit=4, Type=80, Subtype=5, Used=1).Create()
        if 5 not in Devices:
            Domoticz.Device(Name="Boiler temp.", Unit=5, Type=80, Subtype=5, Used=1).Create()
        if 6 not in Devices:
            Domoticz.Device(Name="Suction gas temp.", Unit=6, Type=80, Subtype=5, Used=0).Create()
        if 7 not in Devices:
            Domoticz.Device(Name="Evaporator coil temp.", Unit=7, Type=80, Subtype=5, Used=0).Create()
        if 8 not in Devices:
            Domoticz.Device(Name="Internal coil temp.", Unit=8, Type=80, Subtype=5, Used=0).Create()
        if 9 not in Devices:
            Domoticz.Device(Name="Discharge gas temp.", Unit=9, Type=80, Subtype=5, Used=0).Create()
        if 10 not in Devices:
            Domoticz.Device(Name="Low pressure conversion temp.", Unit=10, Type=80, Subtype=5, Used=0).Create()

        if 11 not in Devices:
            opt = {'ValueStep': '1', 'ValueMin': '28', 'ValueMax': '70', 'ValueUnit': '°C'}
            Domoticz.Device(Name="Setpoint hot water", Unit=11, Type=242, Subtype=1, Options=opt, Used=1).Create()
        if 12 not in Devices:
            opt = {'ValueStep': '1', 'ValueMin': '15', 'ValueMax': '70', 'ValueUnit': '°C'}
            Domoticz.Device(Name="Setpoint heating", Unit=12, Type=242, Subtype=1, Options=opt, Used=1).Create()

        if 13 not in Devices:
            Domoticz.Device(Name="Fan 1 speed", Unit=13, Type=243, Subtype=7, Used=0).Create()
        if 14 not in Devices:
            Domoticz.Device(Name="Fan 2 speed", Unit=14, Type=243, Subtype=7, Used=0).Create()
        if 15 not in Devices:
            Domoticz.Device(Name="COP", Unit=15, Type=243, Subtype=31, Used=1).Create()
        if 16 not in Devices:
            Domoticz.Device(Name="Water pump speed", Unit=16, Type=243, Subtype=6, Used=0).Create()
        if 17 not in Devices:
            Domoticz.Device(Name="Three-way valve", Unit=17, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
        if 18 not in Devices:
            Domoticz.Device(Name="Boiler heater", Unit=18, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
        if 19 not in Devices:
            Domoticz.Device(Name="DC bus voltage", Unit=19, Type=243, Subtype=8, Used=0).Create()

        if 20 not in Devices:
            opt = {"Custom": "1;Hz"}
            Domoticz.Device(Name="Compressor frequency", Unit=20, Type=243, Subtype=31, Options=opt, Used=0).Create()
        if 21 not in Devices:
            Domoticz.Device(Name="Compressor current", Unit=21, Type=243, Subtype=23, Used=0).Create()
        if 22 not in Devices:
            opt = {'EnergyMeterMode': '0'}
            Domoticz.Device(Name="Compressor power", Unit=22, Type=243, Subtype=29, Options=opt, Used=1).Create()
        if 23 not in Devices:
            Domoticz.Device(Name="Low pressure value", Unit=23, Type=243, Subtype=9, Used=0).Create()
        if 24 not in Devices:
            Domoticz.Device(Name="Defrosting", Unit=24, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
        if 25 not in Devices:
            Domoticz.Device(Name="Anti Freezing", Unit=25, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
        if 26 not in Devices:
            Domoticz.Device(Name="Mains voltage", Unit=26, Type=243, Subtype=8, Used=0).Create()
        if 27 not in Devices:
            Domoticz.Device(Name="Consumed current device", Unit=27, Type=243, Subtype=23, Used=0).Create()
        if 28 not in Devices:
            opt = {'EnergyMeterMode': '0'}
            Domoticz.Device(Name="Consumed power device", Unit=28, Type=243, Subtype=29, Options=opt, Used=1).Create()
        if 29 not in Devices:
            opt = {"Custom": "1;m3/h"}
            Domoticz.Device(Name="Waterflow", Unit=29, Type=243, Subtype=31, Options=opt, Used=0).Create()

        if 30 not in Devices:
            opt = {
                "LevelNames": "Intermittent|Always run|Stop after target",
                "LevelOffHidden": "true",
                "SelectorStyle": "1"
            }
            Domoticz.Device(Name="Pump at target temp.", Unit=30, Type=244, Subtype=62, Switchtype=18, Options=opt, Used=1).Create()
        if 31 not in Devices:
            opt = {'ValueStep': '1', 'ValueMin': '1', 'ValueMax': '30', 'ValueUnit': 'minutes'}
            Domoticz.Device(Name="Pump on-off cycle", Unit=31, Type=242, Subtype=1, Options=opt, Used=1).Create()
        if 32 not in Devices:
            Domoticz.Device(Name="Water Pump", Unit=32, Type=244, Subtype=73, Switchtype=0, Image=9, Used=1).Create()
        if 33 not in Devices:
            Domoticz.Device(Name="Chassis electric heating", Unit=33, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
        if 34 not in Devices:
            Domoticz.Device(Name="Crankshaft electric heating", Unit=34, Type=244, Subtype=73, Switchtype=0, Image=9, Used=0).Create()
        if 35 not in Devices:
            Domoticz.Device(Name="Error state", Unit=35, Type=243, Subtype=22, Used=1).Create()
        if 36 not in Devices:
            opt = {
                "LevelNames": "Smart|Powerful|Silent|Holiday",
                "LevelOffHidden": "true",
                "SelectorStyle": "1"
            }
            Domoticz.Device(Name="Frequency mode", Unit=36, Type=244, Subtype=62, Switchtype=18, Options=opt, Used=1).Create()

        Domoticz.Heartbeat(10)

    def onStop(self):
        Domoticz.Log("PowerWorld-Modbus plugin stop")

    def onHeartbeat(self):
        self.runInterval -= 1
        if self.runInterval > 0:
            return

        self.runInterval = 3  # reset

        DevID = Parameters["Mode1"].zfill(2)
        try:
            data1 = get_data_range_from_heatpump(Parameters, DevID + '0300000078')
            data2 = get_data_range_from_heatpump(Parameters, DevID + '0300780078')
            data3 = get_data_range_from_heatpump(Parameters, DevID + '0300F00078')
            data4 = get_data_range_from_heatpump(Parameters, DevID + '0301680007')
            raw_data = (data1 + data2 + data3 + data4).hex().upper()

            # alle velden uitlezen
            unit_state = get_bit_value(get_single_data(raw_data, '003F', 0), 0)
            operation_mode = get_single_data(raw_data, '0043', 0)
            water_in_temp = round(get_single_data(raw_data, '000E', 0.10), 1)
            water_out_temp = round(get_single_data(raw_data, '0012', 0.10), 1)
            ambient_temp = round(get_single_data(raw_data, '0011', 0.50), 1)
            boiler_temp = round(get_single_data(raw_data, '000F', 0.10), 1)
            suction_gas_temp = get_single_data(raw_data, '0015', 0)
            evap_temp = get_single_data(raw_data, '0016', 0)
            internal_temp = get_single_data(raw_data, '001A', 0)
            discharge_temp = get_single_data(raw_data, '001B', 0)
            low_press_conv_temp = round(get_single_data(raw_data, '0028', 0.10), 1)
            hot_water_sp = get_single_data(raw_data, '00BE', 0)
            heating_sp = get_single_data(raw_data, '00C0', 0)
            fan1 = get_single_data(raw_data, '0026', 0)
            fan2 = get_single_data(raw_data, '0027', 0)
            cop = round(get_single_data(raw_data, '0037', 0.10), 1)
            water_pump_speed = round(get_single_data(raw_data, '002A', 0.10), 1)
            three_way = get_bit_value(get_single_data(raw_data, '0005', 0), 6)
            elec_boiler = get_bit_value(get_single_data(raw_data, '0005', 0), 7)
            dc_bus = get_single_data(raw_data, '0021', 0)
            comp_freq = get_single_data(raw_data, '001E', 0)
            comp_current = get_single_data(raw_data, '0023', 0)
            comp_power = get_single_data(raw_data, '002E', 0)
            low_press_val = round(get_single_data(raw_data, '002B', 0.01), 2)
            defrosting = get_bit_value(get_single_data(raw_data, '0003', 0), 7)
            mains_voltage = get_single_data(raw_data, '0031', 0)
            cons_current = round(get_single_data(raw_data, '0032', 0.10), 1)
            cons_power = get_single_data(raw_data, '0035', 0)
            waterflow = round(get_single_data(raw_data, '0030', 0.01), 2)
            pump_target = get_single_data(raw_data, '015B', 0)
            pump_cycle = get_single_data(raw_data, '015C', 0)
            chassis_heat = get_bit_value(get_single_data(raw_data, '0005', 0), 0)
            crank_heat = get_bit_value(get_single_data(raw_data, '0006', 0), 1)
            fault_1 = get_single_data(raw_data, '0007', 0)
            fault_2 = get_single_data(raw_data, '0008', 0)
            fault_3 = get_single_data(raw_data, '0009', 0)
            fault_4 = get_single_data(raw_data, '000A', 0)
            fault_5 = get_single_data(raw_data, '000B', 0)
            fault_6 = get_single_data(raw_data, '000C', 0)
            fault_7 = get_single_data(raw_data, '000D', 0)
            freq_mode = calculate_frequency_mode(raw_data)

            anti_freezing = 0
            if crank_heat == 1:
                anti_freezing = 1

            water_pump = 1 if water_pump_speed > 0 else 0

            error_level, error_text = interpret_errors(
                fault_1, fault_2, fault_3, fault_4, fault_5, fault_6, fault_7
            )
            if error_text.startswith("Secondary anti-freezing") or error_text.startswith("Level 1 anti-freezing"):
                anti_freezing = 1

            def upd(u, n, s):
                if u in Devices:
                    Devices[u].Update(nValue=n, sValue=str(s))

            if 1 in Devices:
                if unit_state == 0:
                    Devices[1].Update(nValue=0, sValue='0')
                else:
                    Devices[1].Update(nValue=1, sValue=str((operation_mode + 1) * 10))

            upd(2, 0, water_in_temp)
            upd(3, 0, water_out_temp)
            upd(4, 0, ambient_temp)
            upd(5, 0, boiler_temp)
            upd(6, 0, suction_gas_temp)
            upd(7, 0, evap_temp)
            upd(8, 0, internal_temp)
            upd(9, 0, discharge_temp)
            upd(10, 0, low_press_conv_temp)

            if 11 in Devices:
                Devices[11].Update(nValue=int(hot_water_sp), sValue=str(hot_water_sp))
            if 12 in Devices:
                Devices[12].Update(nValue=int(heating_sp), sValue=str(heating_sp))

            upd(13, 0, fan1)
            upd(14, 0, fan2)
            if 15 in Devices:
                Devices[15].Update(nValue=int(cop), sValue=str(cop))
            upd(16, 0, water_pump_speed)
            if 17 in Devices:
                Devices[17].Update(nValue=int(three_way), sValue="")
            if 18 in Devices:
                Devices[18].Update(nValue=int(elec_boiler), sValue="")
            upd(19, 0, dc_bus)
            upd(20, 0, comp_freq)
            upd(21, 0, comp_current)
            if 22 in Devices:
                Devices[22].Update(nValue=0, sValue=str(int(comp_power)) + ';0')
            upd(23, 0, low_press_val)
            if 24 in Devices:
                Devices[24].Update(nValue=int(defrosting), sValue="")
            if 25 in Devices:
                Devices[25].Update(nValue=int(anti_freezing), sValue="")
            upd(26, 0, mains_voltage)
            upd(27, 0, cons_current)
            if 28 in Devices:
                Devices[28].Update(nValue=0, sValue=str(int(cons_power)) + ';0')
            upd(29, 0, waterflow)
            if 30 in Devices:
                Devices[30].Update(nValue=1, sValue=str((pump_target + 1) * 10))
            if 31 in Devices:
                Devices[31].Update(nValue=int(pump_cycle), sValue=str(pump_cycle))
            if 32 in Devices:
                Devices[32].Update(nValue=int(water_pump), sValue="")
            if 33 in Devices:
                Devices[33].Update(nValue=int(chassis_heat), sValue="")
            if 34 in Devices:
                Devices[34].Update(nValue=int(crank_heat), sValue="")
            if 35 in Devices:
                Devices[35].Update(nValue=int(error_level), sValue=error_text)
            if 36 in Devices:
                Devices[36].Update(nValue=1, sValue=str(freq_mode))

            Domoticz.Heartbeat(10)

            if Parameters['Mode2'] == 'Debug':
                Domoticz.Log('------ PowerWorld Modbus Data ------')
                Domoticz.Log(f'Unit: {"On" if unit_state == 1 else "Off"}')
                Domoticz.Log(f'Operation mode: {operation_mode_text(operation_mode)}')
                Domoticz.Log(f'Water inlet temp.: {water_in_temp} C')
                Domoticz.Log(f'Water outlet temp.: {water_out_temp} C')
                Domoticz.Log(f'Ambient temp.: {ambient_temp} C')
                Domoticz.Log(f'Boiler temp.: {boiler_temp} C')
                Domoticz.Log(f'Suction gas temp.: {suction_gas_temp} C')
                Domoticz.Log(f'Evaporator coil temp.: {evap_temp} C')
                Domoticz.Log(f'Internal coil temp.: {internal_temp} C')
                Domoticz.Log(f'Discharge gas temp.: {discharge_temp} C')
                Domoticz.Log(f'Low pressure conv. temp.: {low_press_conv_temp} C')
                Domoticz.Log(f'Hot water setpoint: {hot_water_sp} C')
                Domoticz.Log(f'Heating setpoint: {heating_sp} C')
                Domoticz.Log(f'Fan1: {fan1} rpm')
                Domoticz.Log(f'Fan2: {fan2} rpm')
                Domoticz.Log(f'COP: {cop}')
                Domoticz.Log(f'Water pump speed: {water_pump_speed} %')
                Domoticz.Log(f'Three-way valve: {"On" if three_way == 1 else "Off"}')
                Domoticz.Log(f'Electric boiler heater: {"On" if elec_boiler == 1 else "Off"}')
                Domoticz.Log(f'DC bus voltage: {dc_bus} V')
                Domoticz.Log(f'Compressor frequency: {comp_freq} Hz')
                Domoticz.Log(f'Compressor current: {comp_current} A')
                Domoticz.Log(f'Compressor power: {comp_power} W')
                Domoticz.Log(f'Low pressure value: {low_press_val} Bar')
                Domoticz.Log(f'Defrosting: {"On" if defrosting == 1 else "Off"}')
                Domoticz.Log(f'Anti freezing: {"On" if anti_freezing == 1 else "Off"}')
                Domoticz.Log(f'Mains voltage: {mains_voltage} V')
                Domoticz.Log(f'Consumed current device: {cons_current} A')
                Domoticz.Log(f'Consumed power device: {cons_power} W')
                Domoticz.Log(f'Waterflow: {waterflow} m3/h')
                Domoticz.Log(f'Pump on target temp: {pump_target}')
                Domoticz.Log(f'Pump on-off cycle: {pump_cycle} min')
                Domoticz.Log(f'Water Pump: {"On" if water_pump == 1 else "Off"}')
                Domoticz.Log(f'Chassis electric heating: {"On" if chassis_heat == 1 else "Off"}')
                Domoticz.Log(f'Crankshaft electric heating: {"On" if crank_heat == 1 else "Off"}')
                Domoticz.Log(f'Error text: {error_text}')
                Domoticz.Log(f'Frequency mode: {freq_mode}')
                Domoticz.Log('------------------------------------')

        except Exception as err:
            Domoticz.Log(f"PowerWorld read error: {err}")
            Domoticz.Heartbeat(5)
            self.runInterval = 1


    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log(f"Command for {Devices[Unit].Name if Unit in Devices else Unit} -> {Command} ({Level})")
        sValue = str(Level)
        nValue = int(Level)

        if Unit == 1:
            # main operation
            unit_state_val = get_data_from_heatpump(Parameters, '3F')
            unit_state_bit = get_bit_value(unit_state_val, 0)
            # operation mode reg
            if Level == 0:
                # unit off -> clear bit 0
                new_val = clear_bit(unit_state_val, 0)
                write_data_to_heatpump(Parameters, '3F', new_val)
            elif Level == 10:
                # hot water
                if unit_state_bit == 0:
                    new_val = set_bit(unit_state_val, 0)
                    write_data_to_heatpump(Parameters, '3F', new_val)
                write_data_to_heatpump(Parameters, '43', 0)
            elif Level == 20:
                # heating
                if unit_state_bit == 0:
                    new_val = set_bit(unit_state_val, 0)
                    write_data_to_heatpump(Parameters, '3F', new_val)
                write_data_to_heatpump(Parameters, '43', 1)
            elif Level == 30:
                # cooling
                if unit_state_bit == 0:
                    new_val = set_bit(unit_state_val, 0)
                    write_data_to_heatpump(Parameters, '3F', new_val)
                write_data_to_heatpump(Parameters, '43', 2)
            elif Level == 40:
                # hot water + heating
                if unit_state_bit == 0:
                    new_val = set_bit(unit_state_val, 0)
                    write_data_to_heatpump(Parameters, '3F', new_val)
                write_data_to_heatpump(Parameters, '43', 3)
            elif Level == 50:
                # hot water + cooling
                if unit_state_bit == 0:
                    new_val = set_bit(unit_state_val, 0)
                    write_data_to_heatpump(Parameters, '3F', new_val)
                write_data_to_heatpump(Parameters, '43', 4)

        elif Unit == 11:
            # P03
            write_data_to_heatpump(Parameters, 'BE', Level)
        elif Unit == 12:
            # P05
            write_data_to_heatpump(Parameters, 'C0', Level)
        elif Unit == 30:
            # pump at target temp
            if Level == 10:
                write_data_to_heatpump(Parameters, '015B', 0)
            elif Level == 20:
                write_data_to_heatpump(Parameters, '015B', 1)
            elif Level == 30:
                write_data_to_heatpump(Parameters, '015B', 2)
        elif Unit == 36:
            # frequency mode
            val40 = get_data_from_heatpump(Parameters, '0040')
            val41 = get_data_from_heatpump(Parameters, '0041')
            power_bit = get_bit_value(val40, 4)
            silent_bit = get_bit_value(val40, 5)
            holiday_bit = get_bit_value(val41, 1)

            if Level == 10:
                # smart = alles uit
                if power_bit == 1:
                    val40 = clear_bit(val40, 4)
                if silent_bit == 1:
                    val40 = clear_bit(val40, 5)
                if holiday_bit == 1:
                    val41 = clear_bit(val41, 1)
            elif Level == 20:
                # powerful
                if power_bit == 0:
                    val40 = set_bit(val40, 4)
                if silent_bit == 1:
                    val40 = clear_bit(val40, 5)
                if holiday_bit == 1:
                    val41 = clear_bit(val41, 1)
            elif Level == 30:
                # silent
                if power_bit == 1:
                    val40 = clear_bit(val40, 4)
                if silent_bit == 0:
                    val40 = set_bit(val40, 5)
                if holiday_bit == 1:
                    val41 = clear_bit(val41, 1)
            elif Level == 40:
                # holiday
                if power_bit == 1:
                    val40 = clear_bit(val40, 4)
                if silent_bit == 1:
                    val40 = clear_bit(val40, 5)
                if holiday_bit == 0:
                    val41 = set_bit(val41, 1)

            write_data_to_heatpump(Parameters, '0040', val40)
            write_data_to_heatpump(Parameters, '0041', val41)

        if Unit in Devices:
            Devices[Unit].Update(nValue=nValue, sValue=sValue)
            Devices[Unit].Refresh()


# ---------- helper functions ----------

def get_data_from_heatpump(params, device_address_hex):
    """
    Read single register. device_address_hex: e.g. '3F'
    Returns int
    """
    host = params["Address"]
    port = int(params["Port"])
    devid = params["Mode1"].zfill(2)
    req_hex = devid + '03' + device_address_hex.zfill(4) + '0001'
    req = binascii.unhexlify(req_hex)
    req_crc = add_crc(req)

    for attempt in range(MAX_RETRIES):
        try:
            with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT) as s:
                s.send(req_crc)
                resp = s.recv(32)
            if not resp:
                continue
            if not check_crc(resp):
                continue
            bytecount = resp[2]
            if bytecount == 1:
                return resp[3]
            elif bytecount == 2:
                return (resp[3] << 8) + resp[4]
        except OSError as e:
            Domoticz.Log(f"Read single reg error: {e}")
            time.sleep(0.1)
    raise Exception("No valid response for single read")


def get_data_range_from_heatpump(params, request_hex_str):
    """
    Read multiple registers.
    request_hex_str: full hex string, already with dev ID, function, start, count
    Returns bytes of the data payload (without mbap/crc)
    """
    host = params["Address"]
    port = int(params["Port"])
    req = binascii.unhexlify(request_hex_str)
    req_crc = add_crc(req)

    for attempt in range(MAX_RETRIES):
        try:
            with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT) as s:
                s.send(req_crc)
                resp = s.recv(512)
            if not resp:
                continue
            if not check_crc(resp):
                continue
            # skip: id(1), func(1), bytecount(1)  -> data .. last 2 bytes = crc
            bytecount = resp[2]
            data = resp[3:3 + bytecount]
            return data
        except OSError as e:
            Domoticz.Log(f"Read range error: {e}")
            time.sleep(0.1)
    raise Exception("No valid response for range read")


def get_single_data(inputstring, startaddress, factor):
    start = int(startaddress, 16) * 4
    end = start + 4
    out_hex = inputstring[start:end]
    value = int(out_hex, 16)
    if factor > 0:
        value = round(value * factor, 1)
    if value > 65280:
        value = value - 65535
    return value


def write_data_to_heatpump(params, device_address_hex, value):
    host = params["Address"]
    port = int(params["Port"])
    devid = params["Mode1"].zfill(2)
    payload_hex = devid + '06' + str(device_address_hex).zfill(4) + hex(int(value))[2:].zfill(4)
    payload = binascii.unhexlify(payload_hex)
    payload_crc = add_crc(payload)
    Domoticz.Log(f"Write: {payload_hex}")

    try:
        with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT) as s:
            s.send(payload_crc)
            _ = s.recv(32)
    except OSError as e:
        Domoticz.Log(f"Write error: {e}")


def get_bit_value(x, bit_number):
    if x is None:
        return 0
    return (int(x) >> bit_number) & 0x1


def set_bit(value, bit):
    return int(value) | (1 << bit)


def clear_bit(value, bit):
    return int(value) & ~(1 << bit)


def operation_mode_text(level):
    return {
        0: 'Hot water',
        1: 'Heating',
        2: 'Cooling',
        3: 'Hot water + heating',
        4: 'Hot water + cooling'
    }.get(level, 'Unknown')


def calculate_frequency_mode(inputstring):
    out = 10
    if get_bit_value(get_single_data(inputstring, '0040', 0), 4) == 1:
        out = 20
    if get_bit_value(get_single_data(inputstring, '0040', 0), 5) == 1:
        out = 30
    if get_bit_value(get_single_data(inputstring, '0041', 0), 1) == 1:
        out = 40
    return out


def interpret_errors(f1, f2, f3, f4, f5, f6, f7):
    level = 1
    text = "None"

    def bit(v, b):
        return get_bit_value(v, b) == 1

    if f1 != 0:
        level = 4
        if bit(f1, 0):
            text = 'Er 14 Water tank temperature failure'
        elif bit(f1, 1):
            text = 'Er 21 Ambient temperature failure'
        elif bit(f1, 2):
            text = 'Er 16 Evaporator coil temperature failure'
        elif bit(f1, 4):
            text = 'Er 27 Water outlet temperature failure'
        elif bit(f1, 5):
            text = 'Er 05 High pressure fault'
        elif bit(f1, 6):
            text = 'Er 06 Low pressure fault'
        else:
            level, text = 3, 'Unknown error (1)'

    if f2 != 0:
        level = 4
        if bit(f2, 0):
            text = 'Er 03 Water flow fault'
        elif bit(f2, 2):
            text = 'Er 32 Heating outlet water temperature too high'
        else:
            level, text = 3, 'Unknown error (2)'

    if f3 != 0:
        if bit(f3, 1):
            level, text = 4, 'Er 18 Exhaust gas temperature failure'

    if f4 != 0:
        level = 4
        if bit(f4, 0):
            text = 'Er 15 Water inlet temperature failure'
        elif bit(f4, 1):
            text = 'Er 12 Exhaust gas too high protection'
        elif bit(f4, 5):
            text = 'Er 23 Cooling outlet water overcooling'
        elif bit(f4, 6):
            text = 'Er 29 Suction gas temperature failure'
        else:
            level, text = 3, 'Unknown error (4)'

    if f5 != 0:
        level = 4
        if bit(f5, 0):
            text = 'Er 69 Pressure too low protection'
        elif bit(f5, 2):
            text = 'Er 33 Evaporator coil temperature too high'
        elif bit(f5, 3):
            text = 'Er 42 Cooling pipe temperature sensor fault'
        elif bit(f5, 5):
            text = 'Er 72 DC fan communication fault'
        elif bit(f5, 7):
            text = 'Er 67 Low pressure sensor fault'
        else:
            level, text = 3, 'Unknown error (5)'

    if f6 != 0:
        if bit(f6, 4):
            level, text = 2, 'Secondary anti-freezing'
        elif bit(f6, 5):
            level, text = 2, 'Level 1 anti-freezing'
        else:
            level, text = 3, 'Unknown error (6)'

    if f7 != 0:
        level = 4
        if bit(f7, 4):
            text = 'Er 10 communication fault with frequency module'
        elif bit(f7, 5):
            text = 'Er 66 DC fan 2 fault'
        elif bit(f7, 6):
            text = 'Er 64 DC fan 1 fault'
        else:
            level, text = 3, 'Unknown error (7)'

    return level, text

global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)
