#!/usr/bin/env python3
import os
import sys
import time
import datetime
import threading
import copy
import glob
from busio import SPI
from board import SCK, MOSI, MISO, D8, D18, D23, D24, D2, D3
from digitalio import DigitalInOut, Direction
from adafruit_rgb_display.rgb import color565
from adafruit_rgb_display.ili9341 import ILI9341
from PIL import Image, ImageDraw
import cv2

from bs4 import BeautifulSoup
from urllib import request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome import service as fs
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

CS_PIN    = DigitalInOut(D8)
LED_PIN   = DigitalInOut(D18)
RESET_PIN = DigitalInOut(D23)
DC_PIN    = DigitalInOut(D24)
LED_PIN.direction = Direction.OUTPUT

SWITCH_PIN = DigitalInOut(D3)
SWITCH_PIN.direction = Direction.INPUT

LED_OFF_MINUTE=30
CLEANUP_MINUTE=10

spi = SPI(clock=SCK, MOSI=MOSI, MISO=MISO)
display = ILI9341(
    spi,
    cs = CS_PIN,
    dc = DC_PIN,
    rst = RESET_PIN,
    width = 240,
    height = 320,
    rotation = 90,
    baudrate=24000000)

browser = None
URL_HP = 'https://tenki.jp/radar/3/15/'
URL_IMG = 'https://imageflux.tenki.jp/large/static-images/radar/{0:04}/{1:02}/{2:02}/{3:02}/{4:02}/00/pref-15-large.jpg'
IN_PREPARATION_PNG = 'img/in_preparation.png'
ERROR_PNG = 'img/error.png'
CHROMEDRIVER = "/usr/lib/chromium-browser/chromedriver"
CHROME_SERVICE = fs.Service(executable_path=CHROMEDRIVER)




filenames = []
lock_filenames = threading.Lock()

class DownloaderThread(threading.Thread):
    def __init__(self):
        super(DownloaderThread, self).__init__()
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        delta_next = datetime.timedelta(seconds=90)
        dt_next = datetime.datetime.now() + delta_next
        while True:
            dt_now = datetime.datetime.now()
            if dt_next < dt_now:
                download_radar_images()
                dt_next = dt_now + delta_next
            time.sleep(1)
            if self.stop_event.is_set():
                break

def display_img(filename):
    if not (os.path.isfile(filename)):
        filename = ERROR_PNG
    img = cv2.imread(filename, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (320, 240),  interpolation = cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    frame = Image.fromarray(img)
    display.image(frame)

def download_radar_images():
    global filenames
    try:
        print(datetime.datetime.now(), "get started ...")
        browser.get(URL_HP)
        print(datetime.datetime.now(), "get finished")
        soup = BeautifulSoup(str(browser.page_source),  'html.parser')
        elem_radar_source = soup.find(id='radar-source')
        elem_srcset = elem_radar_source['srcset']
        split_srcset = elem_srcset.split('/')
        elem_year   = int(split_srcset[6])
        elem_month  = int(split_srcset[7])
        elem_day    = int(split_srcset[8])
        elem_hour   = int(split_srcset[9])
        elem_minute = int(split_srcset[10])
        dt_latest = datetime.datetime(elem_year , elem_month , elem_day , elem_hour , elem_minute , 0)
        print('dt_latest', dt_latest)

        temp_filenames = []
        for i in range(int(60/5)):
            offset_min = i * 5
            dt_temp = dt_latest - datetime.timedelta(minutes=offset_min)
            filename = "tmp/{0:04}{1:02}{2:02}_{3:02}{4:02}00.png".format(
                dt_temp.year, dt_temp.month, dt_temp.day, dt_temp.hour, dt_temp.minute)
            temp_filenames.insert(0, filename)
            if not(os.path.isfile(filename)):
                url = URL_IMG.format(dt_temp.year, dt_temp.month, dt_temp.day, dt_temp.hour, dt_temp.minute)
                print('downloading ', url)
                browser.get(url)
                element = browser.find_element(By.TAG_NAME, "img")
                with open(filename, 'wb') as f:
                    f.write(element.screenshot_as_png)
        lock_filenames.acquire()
        filenames = copy.deepcopy(temp_filenames)
        lock_filenames.release()
    except Exception as e:
        print(e)
        display_img(ERROR_PNG)
        return

def display_radar_images(latest_only = False):
    global filenames
    lock_filenames.acquire()
    temp_filenames = copy.deepcopy(filenames)
    lock_filenames.release()
    file_count = len(temp_filenames)
    if not latest_only:
        for i in range(file_count):
            filename = temp_filenames[i]
            if not(os.path.isfile(filename)):
                filename = ERROR_PNG
            img = cv2.imread(filename, cv2.IMREAD_COLOR)
            img = cv2.resize(img, (320, 240),  interpolation = cv2.INTER_AREA)
            bar_height = 5
            bar_width = 280
            cv2.rectangle(img, (0, 239-bar_height), (bar_width, 239), (0, 0, 0), thickness=-1)
            cv2.rectangle(img, (0, 239-bar_height), (int(bar_width*(i+1)/file_count), 239), (255, 255, 255), thickness=-1)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(img)
            display.image(frame)
            time.sleep(0.2)
    display_img(temp_filenames[file_count-1])

def cleanup_unused_images():
    global filenames

    lock_filenames.acquire()
    temp_filenames = copy.deepcopy(filenames)
    lock_filenames.release()

    actual_filenames = sorted(glob.glob('tmp/*.png'))

    for filename in actual_filenames:
        if filename not in temp_filenames:
            print("Delete  ", filename)
            os.remove(filename)

def get_latest_filename():
    lock_filenames.acquire()
    latest_filename = filenames[-1]
    lock_filenames.release()
    return latest_filename



def main():
    global browser
    display_img(IN_PREPARATION_PNG)
    LED_PIN.value = True

    options = Options()
    options.add_argument('--headless')
    browser = webdriver.Chrome(service=CHROME_SERVICE, options=options)

    download_radar_images()
    display_radar_images(latest_only = True)

    download_th = DownloaderThread()
    download_th.daemon = True
    download_th.start()

    led_off_time = datetime.datetime.now() + datetime.timedelta(minutes=LED_OFF_MINUTE)
    cleanup_time = datetime.datetime.now() + datetime.timedelta(minutes=CLEANUP_MINUTE)
    latest_filename_prev = ''
    switch_value_prev = False
    while True:
        if switch_value_prev != SWITCH_PIN.value:
            switch_value_prev = SWITCH_PIN.value
            if SWITCH_PIN.value:
                LED_PIN.value = True
                display_radar_images()
                led_off_time = datetime.datetime.now() + datetime.timedelta(minutes=LED_OFF_MINUTE)
        time.sleep(0.1)
        if led_off_time < datetime.datetime.now():
            LED_PIN.value = False
        if cleanup_time < datetime.datetime.now():
            cleanup_unused_images()
            cleanup_time = datetime.datetime.now() + datetime.timedelta(minutes=CLEANUP_MINUTE)
        latest_filename = get_latest_filename()
        if latest_filename_prev != latest_filename:
            latest_filename_prev = latest_filename
            display_radar_images(latest_only = True)

if __name__ == '__main__':
    sys.exit(main())

