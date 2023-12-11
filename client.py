import os
import csv
import sys
import json
import time
import IPython
import argparse
import traceback

from pathlib import Path
from datetime import datetime
from collections import Counter
from dotenv import dotenv_values

from selenium.webdriver import chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from server import DATASET

# Read in the database configuration from a .env file
ENV = dotenv_values(".env")
MAPS_API_KEY = ENV['MAPS_API_KEY']
SIGNING_SECRET = ENV['MAPS_SIGNING_SECRET']

JS_MOVE_RIGHT = """
    var links = document.querySelector('div.gmnoprint.SLHIdE-sv-links-control').firstChild.querySelectorAll('[role="button"]');
    var index = 0;
    if (links.length === 2) {
        index = 1;
    }
    else if (links.length === 3) {
        index = 2
    }
    else if (links.length === 4) {
        index = 2
    }
    links[index].dispatchEvent(new Event('click', {bubbles: true}));
"""
JS_MOVE_LEFT = """
    var links = document.querySelector('div.gmnoprint.SLHIdE-sv-links-control').firstChild.querySelectorAll('[role="button"]');
    var index = 0;
    if (links.length === 2) {
        index = 0;
    }
    else if (links.length === 3) {
        index = 0;
    }
    else if (links.length === 4) {
        index = 1;
    }
    links[index].dispatchEvent(new Event('click', {bubbles: true}));
"""
JS_ADJUST_HEADING = """
    window.sv.setPov({heading: google.maps.geometry.spherical.computeHeading(window.sv.getPosition().toJSON(), window.coordinates), pitch: %s})
"""
JS_CHANGE_ZOOM = """
    window.sv.setZoom({zoom})
"""
JS_RESET_INITIAL_POSITION = """
    window.sv.setPano(document.getElementById('initial-position-pano').innerText);
"""

# Change the date of streetview panos
JS_CHANGE_DATE = """
    window.sv.setPano('%(pano)s');
    document.getElementById('initial-position-pano').innerText = '%(pano)s';
    document.getElementById('current-date').innerText = '%(date)s';
"""

class StreetviewScreenshotClient():

    def __init__(self, show_browser=False):
        chrome_opts = chrome.options.Options()
        if not show_browser:
            chrome_opts.add_argument('--headless')
        chrome_opts.add_argument("window-size=1920,1080")
        chrome_opts.add_argument("--log-level=3")
        chrome_svc = chrome.service.Service(log_output=os.devnull)
        self.driver = chrome.webdriver.WebDriver(service = chrome_svc, options=chrome_opts)
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 10)

    def move(self, direction, num_times=1):
        """
        The move script will try to click on the appropriate link
        """
        if direction == 'left':
            move_script = JS_MOVE_LEFT 
        elif direction == 'right':
            move_script = JS_MOVE_RIGHT 
        else:
            raise Exception('Left or Right only')

        for _ in range(num_times):
            self.driver.execute_script(move_script)
            time.sleep(.3)

    def reset_intial_position(self):
        self.driver.execute_script(JS_RESET_INITIAL_POSITION)
        time.sleep(1)

    def readjust_heading(self, pitch=0):
        # Readjust the heading towards the building of interest
        self.driver.execute_script(JS_ADJUST_HEADING % str(pitch))
        time.sleep(.5)
    
    def take_screenshot(self):
        self.driver.find_element(By.ID, 'btn-screenshot').click()
        self.wait.until(EC.alert_is_present())
        self.driver.switch_to.alert.accept()
        time.sleep(.5)

    def change_zoom(self, zoom):
        self.driver.execute_script(JS_CHANGE_ZOOM.format(zoom=zoom))
        time.sleep(.1)

    def take_screenshots(self, zooms=None):
        if zooms:
            for zoom in zooms:
                self.change_zoom(zoom)
                self.take_screenshot()
        else:
            self.take_screenshot()

    def set_date(self, pano, date):
        print(pano, date)
        self.driver.execute_script(JS_CHANGE_DATE % {'pano': pano, 'date': date})
        time.sleep(1)

    def screenshot(self, id, capture_other_dates=False, num_other_dates=None):
        driver = self.driver
        wait = self.wait

        capture_other_dates = True
        num_other_dates = 2

        # Option: give a list of zooms to toggle through
        zooms = None
        # Option: adjust the camera pitch
        pitch_mod = 0

        driver.get(f"http://127.0.0.1:5000/?id={id}")

        # This is a proxy to know when the streetview is visible
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'gm-iv-address-link')))
        time.sleep(.5)

        current_pano = driver.find_element(By.ID, 'initial-position-pano').text
        current_date = driver.find_element(By.ID, 'current-date').text
        other_dates = []

        if capture_other_dates:
            # Get the other available times from the document
            # They were put there by the gmaps script
            other_dates_text = driver.find_element(By.ID, 'other-dates').text
            if other_dates_text:
                other_dates = json.loads(other_dates_text)

            if isinstance(num_other_dates, int) or num_other_dates.is_digit():
                num_other_dates = int(num_other_dates)
                if num_other_dates > len(other_dates):
                    num_other_dates = len(other_dates)
            
            elif num_other_dates == 'all':
                num_other_dates = len(other_dates)

            elif num_other_dates == 'winter':
                for date in other_dates:
                    print(date)
            else:
                raise Exception('num_other_dates must be an integer or "all"')
            
            other_dates = other_dates[:num_other_dates]
        exit()
            
        all_dates = [{'pano': current_pano, 'date': current_date}] + other_dates

        print(all_dates)

        for i, to_parse in enumerate(all_dates):
            pano, date = to_parse.values()
            if i > 0:
                self.set_date(pano, date)
            self.take_screenshots(zooms=zooms)

            self.move('right', num_times=1)
            self.readjust_heading(pitch = pitch_mod)
            self.take_screenshots(zooms=zooms)

            self.move('right', num_times=1)
            self.readjust_heading(pitch = pitch_mod)
            self.take_screenshots(zooms=zooms)

            self.reset_intial_position()

            self.move('left', num_times=1)
            self.readjust_heading(pitch = pitch_mod)
            self.take_screenshots(zooms=zooms)

            self.move('left', num_times=1)
            self.readjust_heading(pitch = pitch_mod)
            self.take_screenshots(zooms=zooms)


    def __del__(self):
        self.driver.close()


def get_screenshots_for_id(id, show_browser=False):
    print(f'Screenshotting id {id}')
    client = StreetviewScreenshotClient(show_browser=show_browser)
    client.screenshot(id)


def get_all_screenshots(show_browser=False):
    n_cases = len(DATASET)
    client = StreetviewScreenshotClient(show_browser=show_browser)

    for i, id in enumerate(DATASET):
        t0 = time.time()

        print(f'Processing {id} - {i}/{n_cases}')
        try:
            client.screenshot(id)
            print(f'\tTook {round(time.time() - t0, 2)}s')

        except KeyboardInterrupt:
            print('Interrupt received. Exiting.')
            exit()
        except:
            print(traceback.format_exc())
            continue


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ids', nargs='*')
    parser.add_argument('-b', '--show-browser', action='store_true')
    args = parser.parse_args()

    if args.ids:
        for id in args.ids:
            get_screenshots_for_id(id, show_browser=args.show_browser)
    else:
        get_all_screenshots(show_browser=args.show_browser)

