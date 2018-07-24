# -*- coding: utf-8 -*-
#!/usr/bin/python


from TwitterAPI import TwitterAPI
from hcsr04sensor import sensor
import RPi.GPIO as GPIO

import sys
import Adafruit_DHT
import time
import random
import smbus
from ctypes import c_short
from ctypes import c_byte
from ctypes import c_ubyte

DEVICE = 0x76 # Default device I2C address


bus = smbus.SMBus(1) # Rev 2 Pi, Pi 2 & Pi 3 uses bus 1
                     # Rev 1 Pi uses bus 0

def getShort(data, index):
  # return two bytes from data as a signed 16-bit value
  return c_short((data[index+1] << 8) + data[index]).value

def getUShort(data, index):
  # return two bytes from data as an unsigned 16-bit value
  return (data[index+1] << 8) + data[index]

def getChar(data,index):
  # return one byte from data as a signed char
  result = data[index]
  if result > 127:
    result -= 256
  return result

def getUChar(data,index):
  # return one byte from data as an unsigned char
  result =  data[index] & 0xFF
  return result

def readBME280ID(addr=DEVICE):
  # Chip ID Register Address
  REG_ID     = 0xD0
  (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
  return (chip_id, chip_version)

def readBME280All(addr=DEVICE):
  # Register Addresses
  REG_DATA = 0xF7
  REG_CONTROL = 0xF4
  REG_CONFIG  = 0xF5

  REG_CONTROL_HUM = 0xF2
  REG_HUM_MSB = 0xFD
  REG_HUM_LSB = 0xFE

  # Oversample setting - page 27
  OVERSAMPLE_TEMP = 2
  OVERSAMPLE_PRES = 2
  MODE = 1

  # Oversample setting for humidity register - page 26
  OVERSAMPLE_HUM = 2
  bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)

  control = OVERSAMPLE_TEMP<<5 | OVERSAMPLE_PRES<<2 | MODE
  bus.write_byte_data(addr, REG_CONTROL, control)

  # Read blocks of calibration data from EEPROM
  # See Page 22 data sheet
  cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
  cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
  cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)

  # Convert byte data to word values
  dig_T1 = getUShort(cal1, 0)
  dig_T2 = getShort(cal1, 2)
  dig_T3 = getShort(cal1, 4)

  dig_P1 = getUShort(cal1, 6)
  dig_P2 = getShort(cal1, 8)
  dig_P3 = getShort(cal1, 10)
  dig_P4 = getShort(cal1, 12)
  dig_P5 = getShort(cal1, 14)
  dig_P6 = getShort(cal1, 16)
  dig_P7 = getShort(cal1, 18)
  dig_P8 = getShort(cal1, 20)
  dig_P9 = getShort(cal1, 22)

  dig_H1 = getUChar(cal2, 0)
  dig_H2 = getShort(cal3, 0)
  dig_H3 = getUChar(cal3, 2)

  dig_H4 = getChar(cal3, 3)
  dig_H4 = (dig_H4 << 24) >> 20
  dig_H4 = dig_H4 | (getChar(cal3, 4) & 0x0F)

  dig_H5 = getChar(cal3, 5)
  dig_H5 = (dig_H5 << 24) >> 20
  dig_H5 = dig_H5 | (getUChar(cal3, 4) >> 4 & 0x0F)

  dig_H6 = getChar(cal3, 6)

  # Wait in ms (Datasheet Appendix B: Measurement time and current calculation)
  wait_time = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM)+0.575)
  time.sleep(wait_time/1000)  # Wait the required time  

  # Read temperature/pressure/humidity
  data = bus.read_i2c_block_data(addr, REG_DATA, 8)
  pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
  temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
  hum_raw = (data[6] << 8) | data[7]

  #Refine temperature
  var1 = ((((temp_raw>>3)-(dig_T1<<1)))*(dig_T2)) >> 11
  var2 = (((((temp_raw>>4) - (dig_T1)) * ((temp_raw>>4) - (dig_T1))) >> 12) * (dig_T3)) >> 14
  t_fine = var1+var2
  temperature = float(((t_fine * 5) + 128) >> 8);

  # Refine pressure and adjust for temperature
  var1 = t_fine / 2.0 - 64000.0
  var2 = var1 * var1 * dig_P6 / 32768.0
  var2 = var2 + var1 * dig_P5 * 2.0
  var2 = var2 / 4.0 + dig_P4 * 65536.0
  var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
  var1 = (1.0 + var1 / 32768.0) * dig_P1
  if var1 == 0:
    pressure=0
  else:
    pressure = 1048576.0 - pres_raw
    pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
    var1 = dig_P9 * pressure * pressure / 2147483648.0
    var2 = pressure * dig_P8 / 32768.0
    pressure = pressure + (var1 + var2 + dig_P7) / 16.0

  # Refine humidity
  humidity = t_fine - 76800.0
  humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity)))
  humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
  if humidity > 100:
    humidity = 100
  elif humidity < 0:
    humidity = 0

  return temperature/100.0,pressure/100.0,humidity

from auth_talktomangotree import (
    consumer_key,
    consumer_secret,
    access_token,
    access_token_secret
)

stringToTrack = '#talktomangotree'

api = TwitterAPI(consumer_key, 
                 consumer_secret,
                 access_token,
                 access_token_secret)

trig_pin = 17
echo_pin = 27
distance_to_soil = 46.5
GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN)

value = sensor.Measurement(trig_pin, echo_pin)
raw_measurement = value.raw_distance()

ADJECTIVE2 = ("fine", "happy", "good", "cool", "nice", "alive")
COLOUR = ("red","blue","green","yellow","black","white","grey","pink","purple","rainbow")

def tweet_check():
    if "#temp" in tweet.split():

        tweet_temp = "Mangotree temp: " + str(temperature) + " C"
        r = api.request('statuses/update', {'status': tweet_temp})
        print(tweet_temp)

    if "#hight" in tweet.split():
        tweet_hight = "Mangotree hight: {0:0.1f} centimeters".format(growing)
        r = api.request('statuses/update', {'status': tweet_hight})
        print(tweet_hight)

    if "#soil" in tweet.split():
        tweet_soil = "Mangotree soil: " + str(soil)
        r = api.request('statuses/update', {'status': tweet_soil})
        print(tweet_soil)

    if "#status" in tweet.split():
        tweet_status = ("@" + str(user) + " Mangotree status -- " + "DHT sensor: Air " + str(temperature) + " C - Humitidy: "
                        + str(humidity) + " % - Hight: {0:0.1f} cm".format(growing) + " Soil: " + str(soil)
                        + " - I like to be " + random.choice(COLOUR) + " BME280 sensor: Air " + str(temperature2)
                        + " C - Humitidy: {0:0.1f} % ".format(humidity2) + "Pressure: {0:0.1f} hPa".format(pressure))
        r = api.request('statuses/update', {'status': tweet_status})
        print(tweet_status)
        
while True:
    r = api.request('statuses/filter', {'track':stringToTrack})

    humidity, temperature = Adafruit_DHT.read_retry(11, 4)
    value = sensor.Measurement(trig_pin, echo_pin)
    raw_measurement = value.raw_distance()

    (chip_id, chip_version) = readBME280ID()
    print("Chip ID     :", chip_id)
    print("Version     :", chip_version)

    temperature2,pressure,humidity2 = readBME280All()

    print("Temperature2 : ", temperature2, "C")
    print("Pressure : ", pressure, "hPa")
    print("Pressure {0:0.1f}".format(pressure), "hPa")
    print("Humidity2 : ", humidity2, "%")
    print("Humitidy {0:0.1f}".format(humidity2), "%")

    print("Temperature1 : ", temperature, "C")
    print("Humidity1 : ", humidity, "%")
    
    moisture_value = GPIO.input(21)
    if moisture_value == int(1):
        soil = str("Wet")
        print(soil)
    if moisture_value == int(0):
        soil = str("Dry")
        print(soil)

    metric_distance = value.distance_metric(raw_measurement)
    growing = distance_to_soil - metric_distance

    print(growing)
    
    
    print('Twitter ready!')
    
    for item in r:
        tweet = item['text']
        user = item['user']['screen_name']        
        print(tweet)
        print(user)
        tweet_check()
        












