#!/usr/bin/env python3

# https://github.com/Sateetje/SPRSUN-Modbus/blob/master/plugin.py#L652

# Basic PowerWorld heatpump Python plugin
#
# Author: Mike70
#
"""
PowerWorld-Modbus Heat Pump. The Python plugin for Domoticz
Original Author: Mike70

Works with PowerWorld HeatPumps.

Requirements:
    1. python module pip -> https://pypi.org/project/pip/
        sudo apt install python3-pip
    1. python module modbus-crc  -> https://pypi.org/project/modbus-crc/
        sudo pip3 install modbus-crc
    2. Communication module Modbus USB to RS485 or Modbus TCP to RS485
        tested with Sollae CSE-H25 using RTU-over-TCP -> https://www.eztcp.com/en/products/cse-h25
"""
"""
<plugin key="PowerWorld" name="PowerWorld heatpump" author="Mike70" version="1.0.0" wikilink="https://www.domoticz.com/wiki/Plugins" externallink="https://www.powerworld.com/">
    <description>
        <h2>Domoticz Powerworld heat pump RS-485 to LAN plugin version 1.0</h2>
        Get some values from the heat pump, and change them.<br/>
        I used a RS-485 to LAN converter to use it with the CN9 connector of the PowerWorld hetpump.<br/>
        <b>THIS SOFTWARE COMES WITH ABSOLUTE NO WARRANTY: USE AT YOUR OWN RISK!</b>
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

# Read: 01 03 00 12 00 01 + CRC = Water outlet temperature

import Domoticz #tested on Python 3.9.2 in Domoticz 2024.7
import time
import socket
import binascii

from modbus_crc import add_crc
from modbus_crc import check_crc
           
class SettingToWrite:
    def __init__(self, register, value, decimalPlaces, isBit):
        self.register = register
        self.value = value
        self.decimalPlaces = decimalPlaces
        self.isBit = isBit

class BasePlugin:
    def __init__(self):
        self.runInterval = 3    # Success so call again in 1x10 seconds.
        self.settingsToWrite = []
        return

    def onStart(self):
        devicecreated = []
        Domoticz.Log("PowerWorld-Modbus plugin start")
        self.runInterval = 3    # Success so call again in 1x10 seconds.
        
        # https://wiki.domoticz.com/Developing_a_Python_plugin
        # https://github.com/domoticz/domoticz/blob/master/hardware/hardwaretypes.h
        
        #  1.1 = 0x003F   Bit 0     (Switch on/off machine)
        #  1.2 = 0x0043             (Operation mode)
        #  2   = 0x000E             (Water inlet temperature)
        #  3   = 0x0012             (Water outlet temperature)
        #  4   = 0x0011             (ambient temperature)
        #  5   = 0x000F             (Boiler temperature)
        #  6   = 0x0015             (Suction gas temperature)
        #  7   = 0x0016             (Evaporator coil temperature)
        #  8   = 0x001A             (Internal coil temperature)
        #  9   = 0x001B             (Discharge gas temperature)
        # 10   = 0x0028             (Low pressure conversion temperature)
        # 11   = 0x00BE             (P03 Setpoint hot water)
        # 12   = 0x00C0             (P05 Setpoint heating)
        # 13   = 0x0026             (DC fan 1 speed)
        # 14   = 0x0027             (DC fan 2 speed)
        # 15   = 0x0037             (COP)
        # 16   = 0x002A             (DC pump rotation speed)
        # 17   = 0x0005   Bit 6     (output sign 2 - Three-Way Valve)
        # 18   = 0x0005   Bit 7     (output sign 2 - Electric boiler heater)
        # 19   = 0x0021             (DC bus voltage)
        # 20   = 0x001E             (Actual frequency compressor)
        # 21   = 0x0023             (Compressor current)
        # 22   = 0x002E             (Compressor operating power)
        # 23   = 0x002B             (Low pressure value)
        # 24   = 0x0003   Bit 7     (Operating state - Defrosting)
        # 25   =                    (Anti Freezing)
        # 26   = 0x0003             (Mains voltage)
        # 27   = 0x0032             (Consumed current device)
        # 28   = 0x0035             (Consumed power device)
        # 29   = 0x0030             (Waterflow)
        # 30   = 0x015B             (Status water pump after reaching target temperature)
        # 31   = 0x015C             (Water pump on-off cycle after reaching target temperature)
        # 32   =                    (Water pump)
        # 33   = 0x0005   Bit 0     (Chassis electric heating)
        # 34   = 0x0006   Bit 1     (Crankshaft electric heating)
        # 35.1 = 0x0007             (Fault sign 1)
        # 35.2 = 0x0008             (Fault sign 2)
        # 35.3 = 0x0009             (Fault sign 3)
        # 35.4 = 0x000A             (Fault sign 4)
        # 35.5 = 0x000B             (Fault sign 5)
        # 35.6 = 0x000C             (Fault sign 6)
        # 35.7 = 0x000D             (Fault sign 7)
        # 36.1 = 0x0040             (Control sign 1)
        # 36.2 = 0x0041             (Control sign 2)
        
        if 1 not in Devices:
            Opt = {"LevelNames": "|| ||","LevelNames": "Off|Hot water|Heating|Cooling|Hot water + heating|Hot water + cooling","LevelOffHidden": "false","SelectorStyle": "1"}
            Domoticz.Device(Name="Operation mode", Unit=1,Type=244,Subtype=62,Switchtype=18,Options=Opt,Used=1).Create()
        if 2 not in Devices:
            Domoticz.Device(Name="Water inlet temp.",Unit=2,Type=80,Subtype=5,Used=1).Create()
        if 3 not in Devices:
            Domoticz.Device(Name="Water outlet temp.",Unit=3,Type=80,Subtype=5,Used=1).Create()
        if 4 not in Devices:
            Domoticz.Device(Name="Ambient temp.",Unit=4,Type=80,Subtype=5,Used=1).Create()
        if 5 not in Devices:
            Domoticz.Device(Name="Boiler temp.",Unit=5,Type=80,Subtype=5,Used=1).Create()
        if 6 not in Devices:
            Domoticz.Device(Name="Suction gas temp.",Unit=6,Type=80,Subtype=5,Used=0).Create()
        if 7 not in Devices:
            Domoticz.Device(Name="Evaporator coil temp.",Unit=7,Type=80,Subtype=5,Used=0).Create()
        if 8 not in Devices:
            Domoticz.Device(Name="Internal coil temp.",Unit=8,Type=80,Subtype=5,Used=0).Create()
        if 9 not in Devices:
            Domoticz.Device(Name="Discharge gas temp.",Unit=9,Type=80,Subtype=5,Used=0).Create()
        if 10 not in Devices:
            Domoticz.Device(Name="Low pressure conversion temp.",Unit=10,Type=80,Subtype=5,Used=0).Create()
        if 11 not in Devices:
            Opt={'ValueStep':'1', 'ValueMin':'28', 'ValueMax':'70', 'ValueUnit':'°C'}
            Domoticz.Device(Name="Setpoint hot water",Unit=11,Type=242,Subtype=1,Options=Opt,Used=1).Create()
        if 12 not in Devices:
            Opt={'ValueStep':'1', 'ValueMin':'15', 'ValueMax':'70', 'ValueUnit':'°C'}
            Domoticz.Device(Name="Setpoint heating",Unit=12,Type=242,Subtype=1,Options=Opt,Used=1).Create()
        if 13 not in Devices:
            Domoticz.Device(Name="Fan 1 speed",Unit=13,Type=243,Subtype=7,Used=0).Create()
        if 14 not in Devices:
            Domoticz.Device(Name="Fan 2 speed",Unit=14,Type=243,Subtype=7,Used=0).Create()
        if 15 not in Devices:
            Domoticz.Device(Name="COP",Unit= 15,Type=243,Subtype=31,Used=1).Create()
        if 16 not in Devices:
            Domoticz.Device(Name="Water pump speed",Unit=16,Type=243,Subtype=6,Used=0).Create()
        if 17 not in Devices:
            Domoticz.Device(Name="Three-way valve",Unit=17,Type=244,Subtype=73,Switchtype=0,Image=9,Used=1).Create()
        if 18 not in Devices:
            Domoticz.Device(Name="Boiler heater",Unit=18,Type=244,Subtype=73,Switchtype=0,Image=9,Used=1).Create()
        if 19 not in Devices:
            Domoticz.Device(Name="DC bus voltage",Unit=19,Type=243,Subtype=8,Used=0).Create()
        if 20 not in Devices:
            Opt={"Custom":"1;Hz"}
            Domoticz.Device(Name="Compressor frequency",Unit=20,Type=243,Subtype=31,Options=Opt,Used=0).Create()
        if 21 not in Devices:
            Domoticz.Device(Name="Compressor current",Unit=21,Type=243,Subtype=23,Used=0).Create()
        if 22 not in Devices:
            Opt={'EnergyMeterMode': '0'}
            Domoticz.Device(Name="Compressor power",Unit=22,Type=243,Subtype=29,Options=Opt,Used=1).Create()
        if 23 not in Devices:
            Domoticz.Device(Name="Low pressure value",Unit=23,Type=243,Subtype=9,Used=0).Create()
        if 24 not in Devices:
            Domoticz.Device(Name="Defrosting",Unit=24,Type=244,Subtype=73,Switchtype=0,Image=9,Used=0).Create()
        if 25 not in Devices:
            Domoticz.Device(Name="Anti Freezing",Unit=25,Type=244,Subtype=73,Switchtype=0,Image=9,Used=1).Create()
        if 26 not in Devices:
            Domoticz.Device(Name="mains voltage",Unit=26,Type=243,Subtype=8,Used=0).Create()
        if 27 not in Devices:
            Domoticz.Device(Name="Consumed current device",Unit=27,Type=243,Subtype=23,Used=0).Create()
        if 28 not in Devices:
            Opt={'EnergyMeterMode': '0'}
            Domoticz.Device(Name="Consumed power device",Unit=28,Type=243,Subtype=29,Options=Opt,Used=1).Create()
        if 29 not in Devices:
            Opt={"Custom":"1;m3/h"}
            Domoticz.Device(Name="Waterflow",Unit=29,Type=243,Subtype=31,Options=Opt,Used=0).Create()
        if 30 not in Devices:
            Opt = {"LevelNames": "|| ||","LevelNames": "Off|Intermitting|Always run|Stop after reaching target temperature","LevelOffHidden": "true","SelectorStyle": "1"}
            Domoticz.Device(Name="Pump at target temp.", Unit=30,Type=244,Subtype=62,Switchtype=18,Options=Opt,Used=1).Create()
        if 31 not in Devices:
            Opt={'ValueStep':'1', 'ValueMin':'1', 'ValueMax':'30', 'ValueUnit':'minutes'}
            Domoticz.Device(Name="Pump on-off cycle",Unit=31,Type=242,Subtype=1,Options=Opt,Used=1).Create()
        if 32 not in Devices:
            Domoticz.Device(Name="Water Pump",Unit=32,Type=244,Subtype=73,Switchtype=0,Image=9,Used=1).Create()
        if 33 not in Devices:
            Domoticz.Device(Name="Chassis electric heating",Unit=33,Type=244,Subtype=73,Switchtype=0,Image=9,Used=0).Create()
        if 34 not in Devices:
            Domoticz.Device(Name="Crankshaft electric heating",Unit=34,Type=244,Subtype=73,Switchtype=0,Image=9,Used=0).Create()
        if 35 not in Devices:
            Domoticz.Device(Name="Error state",Unit=35,Type=243,Subtype=22,Used=1).Create()
        if 36 not in Devices:
            Opt = {"LevelNames": "|| ||","LevelNames": "Off|Smart|Powerfull|Silent|Holiday","LevelOffHidden": "true","SelectorStyle": "1"}
            Domoticz.Device(Name="Frequency mode", Unit=36,Type=244,Subtype=62,Switchtype=18,Options=Opt,Used=1).Create()

    def onStop(self):
        Domoticz.Log("PowerWorld-Modbus plugin stop")

    def onHeartbeat(self):
        self.runInterval -=1;    # Success so call again in 1x10 seconds.
        if self.runInterval <= 0:
            Unit_State = 0
            Operation_Mode = 0
            Water_Inlet_Temperature = 0 #  Declare these to keep the debug section at the bottom from complaining.
            Water_Outlet_Temperature = 0
            Ambient_Temperature = 0
            Boiler_Temperature = 0
            Suction_Gas_Temperature = 0
            Evaporator_Coil_Temperature = 0
            Internal_Coil_Temperature = 0
            Discharge_Gas_Temperature = 0
            Low_Pressure_Conversion_Temperature = 0
            Hot_Water_SetPoint_Temperature = 0
            Heating_Setpoint_Temperature = 0
            Fan_1_Speed = 0
            Fan_2_Speed = 0
            COP = 0
            Water_Pump_Speed = 0
            Three_Way_Valve = 0
            Electric_Boiler_Heater = 0
            DC_Bus_Voltage = 0
            Compressor_Frequency = 0
            Compressor_Current = 0
            Compressor_Power = 0
            Low_Pressure_Value = 0
            Defrosting = 0
            Anti_Freezing = 0
            Mains_Voltage = 0
            Consumed_Current_Device = 0
            Consumed_Power_Device = 0
            Waterflow = 0
            Pump_At_Target_Temp = 0
            Pump_On_Off_Cycle = 0
            Water_Pump = 0
            Chassis_Electric_Heating = 0
            Crankshaft_Electric_Heating = 0
            Fault_Sign_1 = 0
            Fault_Sign_2 = 0
            Fault_Sign_3 = 0
            Fault_Sign_4 = 0
            Fault_Sign_5 = 0
            Fault_Sign_6 = 0
            Fault_Sign_7 = 0
            Frequency_Mode = 0
            
            Error_Level = 1      # 0=gray, 1=green, 2=yellow, 3=orange, 4=red
            Error_Text = 'None'
            FrequencyModeText = ''
            PumpAtTargetTempText = ''
            Data = ''  

            DevID = Parameters["Mode1"].zfill(2)

            try:
                Data1 = GetDataRangeFromHeatPump (DevID +'0300000078')
                Data2 = GetDataRangeFromHeatPump (DevID +'0300780078')
                Data3 = GetDataRangeFromHeatPump (DevID +'0300F00078')
                Data4 = GetDataRangeFromHeatPump (DevID +'0301680007')
                Data = Data1 + Data2 + Data3 + Data4
                Data = Data.hex().upper()

                Unit_State =                        GetBitValue(GetSingleData(Data, '003F', 0), 0)
                Operation_Mode =                                GetSingleData(Data, '0043', 0)
                Water_Inlet_Temperature =                 round(GetSingleData(Data, '000E', 0.10), 1)
                Water_Outlet_Temperature =                round(GetSingleData(Data, '0012', 0.10), 1)
                Ambient_Temperature =                     round(GetSingleData(Data, '0011', 0.50), 1)
                Boiler_Temperature =                      round(GetSingleData(Data, '000F', 0.10), 1)
                Suction_Gas_Temperature =                       GetSingleData(Data, '0015', 0)
                Evaporator_Coil_Temperature =                   GetSingleData(Data, '0016', 0)
                Internal_Coil_Temperature =                     GetSingleData(Data, '001A', 0)
                Discharge_Gas_Temperature =                     GetSingleData(Data, '001B', 0)
                Low_Pressure_Conversion_Temperature =     round(GetSingleData(Data, '0028', 0.10), 1)
                Hot_Water_SetPoint_Temperature =                GetSingleData(Data, '00BE', 0)
                Heating_Setpoint_Temperature =                  GetSingleData(Data, '00C0', 0)
                Fan_1_Speed =                                   GetSingleData(Data, '0026', 0)
                Fan_2_Speed =                                   GetSingleData(Data, '0027', 0)
                COP =                                     round(GetSingleData(Data, '0037', 0.10), 1)
                Water_Pump_Speed =                        round(GetSingleData(Data, '002A', 0.10), 1)
                Three_Way_Valve =                   GetBitValue(GetSingleData(Data, '0005', 0), 6)
                Electric_Boiler_Heater =            GetBitValue(GetSingleData(Data, '0005', 0), 7)
                DC_Bus_Voltage =                                GetSingleData(Data, '0021', 0)
                Compressor_Frequency =                          GetSingleData(Data, '001E', 0)
                Compressor_Current =                            GetSingleData(Data, '0023', 0)
                Compressor_Power =                              GetSingleData(Data, '002E', 0)
                Low_Pressure_Value =                      round(GetSingleData(Data, '002B', 0.01), 2)
                Defrosting =                        GetBitValue(GetSingleData(Data, '0003', 0), 7)
                Mains_Voltage =                                 GetSingleData(Data, '0031', 0)
                Consumed_Current_Device =                 round(GetSingleData(Data, '0032', 0.10), 1)
                Consumed_Power_Device =                         GetSingleData(Data, '0035', 0)
                Waterflow =                               round(GetSingleData(Data, '0030', 0.01), 2)
                Pump_At_Target_Temp =                           GetSingleData(Data, '015B', 0)
                Pump_On_Off_Cycle =                             GetSingleData(Data, '015C', 0)
                Chassis_Electric_Heating =          GetBitValue(GetSingleData(Data, '0005', 0), 0)
                Crankshaft_Electric_Heating =       GetBitValue(GetSingleData(Data, '0006', 0), 1)
                Fault_Sign_1 =                                  GetSingleData(Data, '0007', 0)
                Fault_Sign_2 =                                  GetSingleData(Data, '0008', 0)
                Fault_Sign_3 =                                  GetSingleData(Data, '0009', 0)
                Fault_Sign_4 =                                  GetSingleData(Data, '000A', 0)
                Fault_Sign_5 =                                  GetSingleData(Data, '000B', 0)
                Fault_Sign_6 =                                  GetSingleData(Data, '000C', 0)
                Fault_Sign_7 =                                  GetSingleData(Data, '000D', 0)
                Frequency_Mode =                                CalculateFrequencyMode(Data)

                Domoticz.Log(Frequency_Mode)

                if Crankshaft_Electric_Heating == '1':
                    Anti_Freezing = 1

                if Water_Pump_Speed > 0:
                    Water_Pump = 1

                if Suction_Gas_Temperature > 65000:
                    Suction_Gas_Temperature = Suction_Gas_Temperature - 65535

                if Evaporator_Coil_Temperature > 65000:
                    Evaporator_Coil_Temperature = Evaporator_Coil_Temperature - 65535

                if Ambient_Temperature * 2 > 65000:
                    Ambient_Temperature = round(((Ambient_Temperature * 2) - 65535) * 0.50, 1)

                if Low_Pressure_Conversion_Temperature * 10 > 65000:
                    Low_Pressure_Conversion_Temperature = round(((Low_Pressure_Conversion_Temperature * 10) - 65535) * 0.10, 1)

                # Convert Frequency_Mode to Text
                if Frequency_Mode == 10:
                    FrequencyModeText = 'Smart'
                elif Frequency_Mode == 20:
                    FrequencyModeText = 'Powerfull'
                elif Frequency_Mode == 30:
                    FrequencyModeText = 'Silent'
                elif Frequency_Mode == 40:
                    FrequencyModeText = 'Holiday'
                else:
                    FrequencyModeText = 'Unknown'

                # Convert Pump_At_Target_Temp to Text
                if Pump_At_Target_Temp == 0:
                    PumpAtTargetTempText = 'Intermitting'
                elif Pump_At_Target_Temp == 1:
                    PumpAtTargetTempText = 'Always run'
                elif Pump_At_Target_Temp == 2:
                    PumpAtTargetTempText = 'Stop after reaching target temperature'
                else:
                    PumpAtTargetTempText = 'Unknown'

                if Fault_Sign_1 !=0:
                    Error_Level = 4
                    if GetBitValue(Fault_Sign_1, 0) == '1':
                        Error_Text = 'Er 14 Water tank temperature failure'
                    elif GetBitValue(Fault_Sign_1, 1) == '1':
                        Error_Text = 'Er 21 Ambient temperature failure'
                    elif GetBitValue(Fault_Sign_1, 2) == '1':
                        Error_Text = 'Er 16 Evaporator coil temperature failure'
                    elif GetBitValue(Fault_Sign_1, 4) == '1':
                        Error_Text = 'Er 27 Water outlet temperature failure'
                    elif GetBitValue(Fault_Sign_1, 5) == '1':
                        Error_Text = 'Er 05 High pressure fault'
                    elif GetBitValue(Fault_Sign_1, 6) == '1':
                        Error_Text = 'Er 06 Low pressure fault'
                    else:
                        Error_Level = 3
                        Error_Text = 'Unknown error'

                if Fault_Sign_2 !=0:
                    Error_Level = 4
                    if GetBitValue(Fault_Sign_2, 0) == '1':
                        Error_Text = 'Er 03 Water flow fault'
                    elif GetBitValue(Fault_Sign_2, 2) == '1':
                        Error_Text = 'Er 32 Heating outlet water temperature to high protection'
                    else:
                        Error_Level = 3
                        Error_Text = 'Unknown error'

                if Fault_Sign_3 !=0:
                    Error_Level = 4
                    if GetBitValue(Fault_Sign_3, 1) == '1':
                        Error_Text = 'Er 18 Exhaust gas temperature failure'

                if Fault_Sign_4 !=0:
                    Error_Level = 4
                    if GetBitValue(Fault_Sign_4, 0) == '1':
                        Error_Text = 'Er 15 Water inlet temperature failure'
                    elif GetBitValue(Fault_Sign_4, 1) == '1':
                        Error_Text = 'Er 12 Exhaust gas to high protection'
                    elif GetBitValue(Fault_Sign_4, 5) == '1':
                        Error_Text = 'Er 23 Cooling outlet water temperature overcooling protection'
                    elif GetBitValue(Fault_Sign_4, 6) == '1':
                        Error_Text = 'Er 29 Suction gas temperature failure'
                    else:
                        Error_Level = 3
                        Error_Text = 'Unknown error'

                if Fault_Sign_5 !=0:
                    Error_Level = 4
                    if GetBitValue(Fault_Sign_5, 0) == '1':
                        Error_Text = 'Er 69 Pressure too low protection'
                    elif GetBitValue(Fault_Sign_5, 2) == '1':
                        Error_Text = 'Er 33 Evaporator coil temperature too high'
                    elif GetBitValue(Fault_Sign_5, 3) == '1':
                        Error_Text = 'Er 42 Cooling pipe temperature sensor (after EV during cooling) fault'
                    elif GetBitValue(Fault_Sign_5, 5) == '1':
                        Error_Text = 'Er 72 DC fan communication fault'
                    elif GetBitValue(Fault_Sign_5, 7) == '1':
                        Error_Text = 'Er 67 Low pressure sensor fault'
                    else:
                        Error_Level = 3
                        Error_Text = 'Unknown error'

                if Fault_Sign_6 !=0:
                    Error_Level = 2
                    if GetBitValue(Fault_Sign_6, 4) == '1':
                        Error_Text = 'Secondary anti-freezing'
                        Anti_Freezing = 1
                    elif GetBitValue(Fault_Sign_6, 5) == '1':
                        Error_Text = 'Level 1 anti-freezing'
                        Anti_Freezing = 1
                    else:
                        Error_Level = 3
                        Error_Text = 'Unknown error'

                if Fault_Sign_7 !=0:
                    Error_Level = 4
                    if GetBitValue(Fault_Sign_7, 4) == '1':
                        Error_Text = 'Er 10 communication fault with frequency conversion module'
                    elif GetBitValue(Fault_Sign_7, 5) == '1':
                        Error_Text = 'Er 66 DC fan 2 fault'
                    elif GetBitValue(Fault_Sign_7, 6) == '1':
                        Error_Text = 'Er 64 DC fan 1 fault'
                    else:
                        Error_Level = 3
                        Error_Text = 'Unknown error'

            except Exception as err:
                Domoticz.Log(f"Unexpected {err=}, {type(err)=}")
                Domoticz.Heartbeat(5)   # set Heartbeat to 1 second to get us back here for quick retry.
                self.runInterval = 3    # Success so call again in 1x10 seconds.
            else:
                #Update devices
                if Unit_State == '0':
                    Devices[1].Update(nValue=0,sValue='0')
                else:
                    Devices[1].Update(nValue=int(Unit_State),sValue=str((Operation_Mode+1)*10))

                Devices[2].Update(0,str(Water_Inlet_Temperature))
                Devices[3].Update(0,str(Water_Outlet_Temperature))
                Devices[4].Update(0,str(Ambient_Temperature))
                Devices[5].Update(0,str(Boiler_Temperature))
                Devices[6].Update(0,str(Suction_Gas_Temperature))
                Devices[7].Update(0,str(Evaporator_Coil_Temperature))
                Devices[8].Update(0,str(Internal_Coil_Temperature))
                Devices[9].Update(0,str(Discharge_Gas_Temperature))
                Devices[10].Update(0,str(Low_Pressure_Conversion_Temperature))
                Devices[11].Update(nValue=int(Hot_Water_SetPoint_Temperature),sValue=str(Hot_Water_SetPoint_Temperature))
                Devices[12].Update(nValue=int(Heating_Setpoint_Temperature),sValue=str(Heating_Setpoint_Temperature))
                Devices[13].Update(0,str(Fan_1_Speed))
                Devices[14].Update(0,str(Fan_2_Speed))
                Devices[15].Update(nValue=int(COP),sValue=str(COP))
                Devices[16].Update(0,str(Water_Pump_Speed))
                Devices[17].Update(int(Three_Way_Valve),"")
                Devices[18].Update(int(Electric_Boiler_Heater),"")
                Devices[19].Update(0,str(DC_Bus_Voltage))
                Devices[20].Update(0,str(Compressor_Frequency))
                Devices[21].Update(0,str(Compressor_Current))
                Devices[22].Update(nValue=0,sValue=str(int(Compressor_Power)) + ';0')
                Devices[23].Update(0,str(Low_Pressure_Value))
                Devices[24].Update(int(Defrosting),"")
                Devices[25].Update(int(Anti_Freezing),"")
                Devices[26].Update(0,str(Mains_Voltage))
                Devices[27].Update(0,str(Consumed_Current_Device))
                Devices[28].Update(nValue=0,sValue=str(int(Consumed_Power_Device)) + ';0')
                Devices[29].Update(0,str(Waterflow))
                Devices[30].Update(nValue=1,sValue=str((Pump_At_Target_Temp+1)*10))
                Devices[31].Update(nValue=int(Pump_On_Off_Cycle),sValue=str(Pump_On_Off_Cycle))
                Devices[32].Update(int(Water_Pump),"")
                Devices[33].Update(int(Chassis_Electric_Heating),"")
                Devices[34].Update(int(Crankshaft_Electric_Heating),"")
                Devices[35].Update(nValue=int(Error_Level),sValue=Error_Text)

                Devices[36].Update(nValue=1,sValue=str(Frequency_Mode))

                self.runInterval = 3    # Success so call again in 1x10 seconds.
                Domoticz.Heartbeat(10)  # Sucesss so set Heartbeat to 10 second intervals.

            if Parameters['Mode2'] == 'Debug':
                Domoticz.Log('PowerWorld Modbus Data ########################################')
                Domoticz.Log('Unit : {0}'.format(GetOnOffState(Unit_State)))
                Domoticz.Log('Operation mode: {0}'.format(SetOperationModeText(Operation_Mode)))
                Domoticz.Log('Water inlet temp.: {0:.1f} C'.format(Water_Inlet_Temperature))
                Domoticz.Log('Water outlet temp.: {0:.1f} C'.format(Water_Outlet_Temperature))
                Domoticz.Log('Ambient temp.: {0:.1f} C'.format(Ambient_Temperature))
                Domoticz.Log('Boiler temp.: {0:.1f} C'.format(Boiler_Temperature))
                Domoticz.Log('Suction gas temp.: {0:.1f} C'.format(Suction_Gas_Temperature))
                Domoticz.Log('Evaporator coil temp.: {0:.1f} C'.format(Evaporator_Coil_Temperature))
                Domoticz.Log('Internal coil temp.: {0:.1f} C'.format(Internal_Coil_Temperature))
                Domoticz.Log('Discharge gas temp.: {0} C'.format(Discharge_Gas_Temperature))
                Domoticz.Log('Low pressure conversion temp.: {0} C'.format(Low_Pressure_Conversion_Temperature))
                Domoticz.Log('Hot water setpoint: {0:.1f} C'.format(Hot_Water_SetPoint_Temperature))
                Domoticz.Log('Heating setpoint: {0:.1f} C'.format(Heating_Setpoint_Temperature))
                Domoticz.Log('Fan 1 speed: {0} rpm'.format(Fan_1_Speed))
                Domoticz.Log('Fan 2 speed: {0} rpm'.format(Fan_2_Speed))
                Domoticz.Log('COP: {0:.1f}'.format(COP))
                Domoticz.Log('Water pump Speed: {0} %'.format(Water_Pump_Speed))
                Domoticz.Log('Three-way valve: {0}'.format(GetOnOffState(Three_Way_Valve)))
                Domoticz.Log('Electric boiler heater: {0}'.format(GetOnOffState(Electric_Boiler_Heater)))
                Domoticz.Log('DC bus voltage: {0} V'.format(DC_Bus_Voltage))
                Domoticz.Log('Compressor frequency: {0} Hz'.format(Compressor_Frequency))
                Domoticz.Log('Compressor current: {0} A'.format(Compressor_Current))
                Domoticz.Log('Compressor power: {0} W'.format(Compressor_Power))
                Domoticz.Log('Low pressure value: {0} Bar'.format(Low_Pressure_Value))
                Domoticz.Log('Defrosting: {0}'.format(GetOnOffState(Defrosting)))
                Domoticz.Log('Anti freezing: {0}'.format(GetOnOffState(Anti_Freezing)))
                Domoticz.Log('Mains voltage: {0} V'.format(Mains_Voltage))
                Domoticz.Log('Consumed current device: {0} A'.format(Consumed_Current_Device))
                Domoticz.Log('Consumed power device: {0} W'.format(Consumed_Power_Device))
                Domoticz.Log('Waterflow: {0} m3/h'.format(Waterflow))
                Domoticz.Log('Pump_At_Target_Temp: {0}'.format(PumpAtTargetTempText))
                Domoticz.Log('Pump on-off cycle: {0} min'.format(Pump_On_Off_Cycle))
                Domoticz.Log('Water Pump: {0}'.format(GetOnOffState(Water_Pump)))
                Domoticz.Log('Chassis electric heating: {0}'.format(GetOnOffState(Chassis_Electric_Heating)))
                Domoticz.Log('Crankshaft electric heating: {0}'.format(GetOnOffState(Crankshaft_Electric_Heating)))
                Domoticz.Log('Error text: {0}'.format(Error_Text))
                Domoticz.Log('Frequency mode: {0}'.format(FrequencyModeText))
                Domoticz.Log('PowerWorld Modbus Data ########################################')
                Domoticz.Log('')

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("Something changed for " + Devices[Unit].Name + ", DeviceID = " + str(Unit) + ". New setpoint: " + str(Level) + ". New Command: " + Command)

        Unit_State = 0
        Unit_State_Bit = 0
        Operation_Mode = 0

        sValue=str(Level)
        nValue=int(Level)

        if Unit == 1:
            #  1.1 = 0x003F   Bit 0     (Switch on/off machine)
            #  1.2 = 0x0043             (Operation mode)
            #  0: hot water, 1: heating, 2: cooling, 3: hot water + heating, 4: hot water + cooling

            Unit_State = GetDataFromHeatPump ('3F')
            Unit_State_Bit = int(GetBitValue(GetDataFromHeatPump ('3F'), 0))
            Operation_Mode = GetDataFromHeatPump ('43')
            
            if Level == 0:     # 0 = Machine off
                if Unit_State_Bit == 1:
                    Domoticz.Log('Operation mode: 0')
                WriteDataToHeatPump ('3F', clear_bit(0, Unit_State))
            elif Level == 10:  # 10 = Hot water
                if Unit_State_Bit == 0:
                    Domoticz.Log('Operation mode: 10')
                    WriteDataToHeatPump ('3F', set_bit(0, Unit_State))
                WriteDataToHeatPump ('43', 0)
            elif Level == 20:  # 10 = Heatin
                if Unit_State_Bit == 0:
                    Domoticz.Log('Operation mode: 20')
                    WriteDataToHeatPump ('3F', set_bit(0, Unit_State))
                WriteDataToHeatPump ('43', 1)
            elif Level == 30:  # 20 = Cooling
                if Unit_State_Bit == 0:
                    Domoticz.Log('Operation mode: 30')
                    WriteDataToHeatPump ('3F', set_bit(0, Unit_State))
                WriteDataToHeatPump ('43', 2)
            elif Level == 40:  # 30 = Hot water + heating
                if Unit_State_Bit == 0:
                    WriteDataToHeatPump ('3F', set_bit(0, Unit_State))
                    Domoticz.Log('Operation mode: 40')
                WriteDataToHeatPump ('43', 3)
            elif Level == 50:  # 40 = Hot water + cooling
                if Unit_State_Bit == 0:
                    Domoticz.Log('Operation mode: 50')
                    WriteDataToHeatPump ('3F', set_bit(0, Unit_State))
                WriteDataToHeatPump ('43', 4)

        if Unit == 11:
            # P03 Setpoint hot water
            nValue=int(Level)
            WriteDataToHeatPump ('BE', Level)

        if Unit == 12:
            # P05 Setpoint heating
            nValue=int(Level)
            WriteDataToHeatPump ('C0', Level)

        if Unit == 30:
            if Level == 10:
                Domoticz.Log('Pump after reaching target temp: Run Intervally')
                WriteDataToHeatPump ('015B', 0)
            elif Level == 20:
                Domoticz.Log('Pump after reaching target temp: Always run')
                WriteDataToHeatPump ('015B', 1)
            elif Level == 30:
                Domoticz.Log('Pump after reaching target temp: Stop')
                WriteDataToHeatPump ('015B', 2)

        if Unit == 36:
            # Frequency mode
            Value40 = GetDataFromHeatPump ('0040')
            Value41 = GetDataFromHeatPump ('0041')
            PowerfullBit = GetBitValue(Value40, 4)
            SilentBit = GetBitValue(Value40, 5)
            HolidayBit = GetBitValue(Value41, 1)

            if Level == 10:
                Domoticz.Log('Frequency mode: smart')
                if PowerfullBit == '1':
                    Value40 = Value40 - 16
                if SilentBit == '1':
                    Value40 = Value40 - 32
                if HolidayBit == '1':
                    Value41 = Value41 - 2
            elif Level == 20:
                Domoticz.Log('Frequency mode: powerfull')
                if PowerfullBit == '0':
                    Value40 = Value40 + 16
                if SilentBit == '1':
                    Value40 = Value40 - 32
                if HolidayBit == '1':
                    Value41 = Value41 - 2                 
            elif Level == 30:
                Domoticz.Log('Frequency mode: silent')
                if PowerfullBit == '1':
                    Value40 = Value40 - 16
                if SilentBit == '0':
                    Value40 = Value40 + 32
                if HolidayBit == '1':
                    Value41 = Value41 - 2
            elif Level == 40:
                Domoticz.Log('Frequency mode: holiday')
                if PowerfullBit == '1':
                    Value40 = Value40 - 16
                if SilentBit == '1':
                    Value40 = Value40 - 32
                if HolidayBit == '0':
                    Value41 = Value41 + 2
            WriteDataToHeatPump ('0040', Value40)
            WriteDataToHeatPump ('0041', Value41)

        Devices[Unit].Update(nValue=nValue, sValue=sValue)
        Devices[Unit].Refresh()

def left(s, amount):
    return s[:amount]

def right(s, amount):
    return s[-amount:]

def mid(s, offset, amount):
    return s[offset:offset+amount]

def GetDataFromHeatPump (DeviceAddress):
    received_package = -1
    receiveddata = ''
    output = ''
    hostAddress = Parameters["Address"]
    port = int(Parameters["Port"])
    DevID = Parameters["Mode1"].zfill(2)
    DeviceAddress = DevID + '03' + DeviceAddress.zfill(4) + '0001'

    while received_package == -1:
        time.sleep(0.100)
        tcp_socket = socket.create_connection((hostAddress, port)) # IP address and port number
        tcp_socket.send(add_crc(binascii.unhexlify(DeviceAddress)))
        receiveddata = tcp_socket.recv(23)
        tcp_socket.close()

        if str(DeviceAddress[1]) == str(receiveddata[0]) and str(DeviceAddress[3]) == str(receiveddata[1]):
            if check_crc(receiveddata):
                received_package = 1
                if receiveddata[2] == 1:
                    output = receiveddata[3]
                if receiveddata[2] == 2:
                    output = ((receiveddata[3] * 256) + (receiveddata[4]))
    return output

def GetDataRangeFromHeatPump (DeviceAddress):
    received_package = -1
    receiveddata = ''
    output = ''
    hostAddress = Parameters["Address"]
    port = int(Parameters["Port"])

    while received_package == -1:
        time.sleep(0.200)
        tcp_socket = socket.create_connection((hostAddress, port)) # IP address and port number
        tcp_socket.send(add_crc(binascii.unhexlify(DeviceAddress)))
        receiveddata = tcp_socket.recv(256)
        tcp_socket.close()

        if str(DeviceAddress[1]) == str(receiveddata[0]) and str(DeviceAddress[3]) == str(receiveddata[1]):
            if check_crc(receiveddata):
                output = receiveddata
                received_package = 1            
    return mid(output, 3, len(output) -5)

def GetSingleData (inputstring, startaddress, factor):
    start = int(startaddress, 16) * 4
    end  = start + 4
    output = inputstring[start:end]
    if factor > 0 :
        output = round ((int(output, 16) * factor), 1)
    else:
        output = int(output, 16)
    if output > 65280:
        output = output - 65535
    return output

def WriteDataToHeatPump (DeviceAddress, Value):
    hostAddress = Parameters["Address"]
    port = int(Parameters["Port"])
    DevID = str(Parameters["Mode1"].zfill(2))
    output = DevID + '06' + str(DeviceAddress).zfill(4) + str(hex(int(Value))[2:]).zfill(4)
    Domoticz.Log(output)

    time.sleep(0.200)
    tcp_socket = socket.create_connection((hostAddress, port)) # IP address and port number
    tcp_socket.send(add_crc(binascii.unhexlify(output)))
    #receiveddata = tcp_socket.recv(23)
    tcp_socket.close()

def GetBitValue(x, BitNumber):
    if x == 'None':
        x = 0
    StrBin = '{:0>8b}'.format(x)
    return StrBin[7 - BitNumber]

def set_bit(value, bit):
    return value | (1<<bit)

def clear_bit(value, bit):
    return value & ~(1<<bit)

def GetOnOffState(x):
    if int(x) == 0:
        x = 'Off'
    else:
        x = 'On'
    return x

def SetOperationModeText(Level):
    # Convert Operation_Mode to Text
    if Level == 0:
        return 'Hot water'
    elif Level == 1:
        return 'Heating'     
    elif Level == 2:
        return 'Cooling'
    elif Level == 3:
        return 'Hot water + heating'
    elif Level == 4:
        return 'Hot water + cooling'
    else:
        return 'Unknown'

def CalculateFrequencyMode(inputstring):
    output = 10 # Smart mode
    if GetBitValue(GetSingleData (inputstring ,'0040', 0), 4) == '1': # Powerfull mode
        output = 20
    if GetBitValue(GetSingleData (inputstring ,'0040', 0), 5) == '1': # Silent mode
        output = 30
    if GetBitValue(GetSingleData (inputstring ,'0041', 0), 1) == '1' :# Holiday mode
        output = 40        
    return output

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
