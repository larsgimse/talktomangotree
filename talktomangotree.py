# -*- coding: utf-8 -*-
#!/usr/bin/python


from TwitterAPI import TwitterAPI
from hcsr04sensor import sensor
import RPi.GPIO as GPIO

import sys
import Adafruit_DHT
import time
import random

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
        tweet_status = ("@" + str(user) + " Mangotree status -- " + "Air: " + str(temperature) + " C - Humitidy: "
                        + str(humidity) + " % - Hight: {0:0.1f} cm".format(growing) + " Soil: " + str(soil)
                        + " - I like to be " + random.choice(COLOUR))
        r = api.request('statuses/update', {'status': tweet_status})
        print(tweet_status)
        
while True:
    r = api.request('statuses/filter', {'track':stringToTrack})

    humidity, temperature = Adafruit_DHT.read_retry(11, 4)
    value = sensor.Measurement(trig_pin, echo_pin)
    raw_measurement = value.raw_distance()
    
    moisture_value = GPIO.input(21)
    if moisture_value == int(1):
        soil = str("Wet")
    if moisture_value == int(0):
        soil = str("Dry")

    metric_distance = value.distance_metric(raw_measurement)
    growing = distance_to_soil - metric_distance
    
    print('Twitter ready!')
    
    for item in r:
        tweet = item['text']
        user = item['user']['screen_name']        
        print(tweet)
        print(user)
        tweet_check()
