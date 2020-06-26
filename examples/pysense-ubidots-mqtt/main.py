#!/usr/bin/python
''' 
  Project: weather-station-pysense-ubidots-mqtt
  Description: Reads the different variables sensed by the Pysense board and publishes them to Ubidots using WiFi over the MQTT protocol.
  Author: Maria Carlina Hernández <mariacarlinahernandez@gmail.com>
  Date: 24/06/2020 
'''
# Include Libraries
from umqtt.robust import MQTTClient
import machine
import time
import pycom
import json
import ubinascii
from network import WLAN
from pysense import Pysense
from LIS2HH12 import LIS2HH12
from SI7006A20 import SI7006A20
from LTR329ALS01 import LTR329ALS01
from MPL3115A2 import MPL3115A2,ALTITUDE,PRESSURE
import gc
gc.collect()

# Define network constants
wifi_ssid = "xxxx" # Set Network's SSID
wifi_password = "xxxx" # Set Network password

# Define Ubidots constants
mqtt_server = "industrial.api.ubidots.com" # 169.55.61.243
mqtt_clientID = ubinascii.hexlify(machine.unique_id(),'').decode() 
mqtt_username = "BBFF-xxxx" # Set your Ubidots TOKEN
ubidots_dev_label = "weather-station" # ubinascii.hexlify(machine.unique_id(),':').decode() # Set a device labe

# Constants to manage data rate
last_message = 0
message_interval = 5 

'''
Establishes connection with the MQTT server defined
'''
def connect_mqtt():
  global mqtt_clientID, mqtt_server
  client = MQTTClient(mqtt_clientID, mqtt_server, user=mqtt_username, password=mqtt_username)
  client.connect()
  print("\nConnected to {} MQTT broker".format(mqtt_server))
  return client


'''
Reset the device to restore the connection with the MQTT Server
'''
def restart_and_reconnect():
  print("\nFailed to connect to MQTT broker. Reconnecting...")
  time.sleep(10)
  machine.reset()


'''
Establish network connection
 @arg ssid [Mandatory] Network SSID 
 @arg psw [Mandatory] Network Password
'''
def wifi_connect(ssid, psw):
  attempts = 0

  print("Starting attempt to connect to WiFi.", end="")
  wlan.connect(ssid, auth=(WLAN.WPA2, psw), timeout=5000) # Connect to the WiFi AP provided

  # Check network status
  while not wlan.isconnected():
    time.sleep(0.5)
    print(".", end="")
    attempts += 1
    machine.idle() # Safe power while waiting
 
    if attempts >= 10:
      print("\nssid: {}, psw: {}".format(wifi_ssid, wifi_password))
      print("\nCould not establish connection with the network provided. Please check the network crendentials or status, and try again.");
      time.sleep(0.5)
      attempts = 0
      machine.reset()

  # Network interface parameteres logs
  network_settings =  wlan.ifconfig()
  print("\nWLAN connection succeeded!")
  print("IP address: {}".format(network_settings[0]))
  print("Subnet: {}".format(network_settings[1]))
  print("Gateway: {}".format(network_settings[2]))
  print("DNS: {}".format(network_settings[3]))
  
  return True

'''
Reads temperature, humidity, pressure, altitude, and light sensors
 @return data, JSON object with sensors readings
'''
def read_sensors():
  # Barometric sensor constructor (Pressure (Pascals), Altitud (meters), Temperature (celsius ))
  mpl_pressure = MPL3115A2(py, mode=PRESSURE)
  mpl_altitude = MPL3115A2(py,mode=ALTITUDE) 
  # Humidity & Temperature sensor constructor (Humidity (relative humidity), Temperature (celsius))
  si = SI7006A20(py)
  # Ambient light sensor consturctor (Light levels(luxes))
  ltr = LTR329ALS01(py)
  # Sensors readings
  pressure = mpl_pressure.pressure()
  altitude = mpl_altitude.altitude()
  temperature_mpl = mpl_altitude.temperature()
  temperature_si = si.temperature()
  relative_humidity = si.humidity()
  ambient_humidty = si.humid_ambient(temperature_si)
  dewpoint = si.dew_point()
  light = ltr.light()

  # Readings logs
  print("\nMPL3115A2 | Pressure: {} Pa, Altitude: {} m, Temperature: {} ºC".format(pressure, altitude, temperature_mpl))
  print("SI7006A20 | Temperature: {} ºC, Relative Humidity: {} %RH, Ambient Humidity: {} %RH, Dew point: {}".format(temperature_si, relative_humidity, ambient_humidty, dewpoint))
  print("LTR329ALS01 | Light (channel Blue lux, channel Red lux): {}\n".format(light))
  # JSON build
  data = b'{ "pressure" : %s,"altitude" : %s, "temp_mpl" : %s, "temp_si" : %s, "rel_hum" : %s, "amb_hum" : %s, "dew_point" : %s, "lux_blue" : %s, "lux_red" : %s }' % (pressure, altitude, temperature_mpl, temperature_si, relative_humidity, ambient_humidty, dewpoint, light[0], light[1])

  return data


'''
RUN ON BOOT FILE
'''
# Network's inizalitation
wlan = WLAN(mode=WLAN.STA) # Set STA (Station Aka Client, connects to an AP) as WLAN network interface 'STA_IF' (Station aka client, connects to upstream WiFi Access points)
wlan.antenna(WLAN.EXT_ANT) # Set antenna type (INT_ANT: Internal, EXT_ANT: External)
wifi_connect(wifi_ssid, wifi_password)

# Sensors' inizalitation
py = Pysense()

# Establishes connection with the MQTT server
try:
  client = connect_mqtt()
except OSError as e:
  restart_and_reconnect()

# Main function
while True:
  try:
    # Network reconnection
    if wlan.isconnected() != True:
      wifi_connect(wifi_ssid, wifi_password)

    # Publish sensor data every 5 seconds
    if (time.time() - last_message) > message_interval:
      data = read_sensors()
      client.publish(b"/v1.6/devices/%s" % (ubidots_dev_label), data)
      last_message = time.time()

  except OSError as e:
    restart_and_reconnect()
