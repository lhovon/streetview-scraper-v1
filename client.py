import math
import os
import json
import time
import IPython
import psycopg2
import argparse
import traceback
import psycopg2.extras

from tqdm import tqdm
from pathlib import Path
from random import randrange
from dotenv import dotenv_values

from multiprocessing import Pool
from selenium.webdriver import chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException

# Read in the database configuration from a .env file
ENV = dotenv_values(".env")

JS_MOVE_RIGHT = """
    const links = document.querySelector('div.gmnoprint.SLHIdE-sv-links-control').firstChild.querySelectorAll('[role="button"]');
    var index = 0;
    if (links.length === 2 || links.length === 3)
        index = 0;
    else if (links.length === 4)
        index = 1;
    links[index].dispatchEvent(new Event('click', {bubbles: true}));
"""
JS_MOVE_LEFT = """
    const links = document.querySelector('div.gmnoprint.SLHIdE-sv-links-control').firstChild.querySelectorAll('[role="button"]');
    var index = 0;
    if (links.length === 2)
        index = 1;
    else if (links.length === 3 || links.length === 4)
        index = 2;
    links[index].dispatchEvent(new Event('click', {bubbles: true}));
"""
JS_ADJUST_HEADING = """
    window.sv.setPov({
        heading: window.computeHeading(window.sv.getPosition().toJSON(), window.coordinates), 
        pitch: %s
    });
"""
JS_CHANGE_ZOOM = """
    window.sv.setZoom({zoom});
"""
JS_RESET_INITIAL_POSITION = """
    window.sv.setPano(document.getElementById('initial-pano').innerText);
"""

# Change the date of streetview panos
JS_CHANGE_DATE = """
    window.sv.setPano('%(pano)s');
    document.getElementById('initial-pano').innerText = '%(pano)s';
    document.getElementById('current-date').innerText = '%(date)s';
"""

class NoPanoramaException(Exception):
    pass

class StreetviewScreenshotClient():

    def __init__(self, window_size="1920,1080", show_browser=False):
        chrome_opts = chrome.options.Options()
        if not show_browser: 
            chrome_opts.add_argument('--headless') # for debugging
        chrome_opts.add_argument(f"window-size={window_size}")
        chrome_opts.add_argument("--log-level=3")
        chrome_svc = chrome.service.Service(log_output=os.devnull)
        self.driver = chrome.webdriver.WebDriver(service = chrome_svc, options=chrome_opts)
        self.wait = WebDriverWait(self.driver, 10)
    
    def take_screenshot(self):
        self.driver.find_element(By.ID, 'btn-screenshot').click()
        self.wait.until(EC.alert_is_present())
        self.driver.switch_to.alert.accept()
        time.sleep(.5)

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
        # print(pano, date)
        self.driver.execute_script(JS_CHANGE_DATE % {'pano': pano, 'date': date})
        time.sleep(1)


    def screenshot(self, id, lat=None, lng=None, additional_pano_selector=None):
        """
        additional_pano_selector is a function taking list of all available panos and a set 
        of the selected panos as arguments and returning additional panoramas to scrape.
        If none, it defaults to choosing the two earliest available panos.
        """

        if additional_pano_selector is None:
            # Default to taking 2 other available panos
            additional_pano_selector = lambda panos, _: panos[:2]
        
        driver = self.driver
        wait = self.wait
        
        # The below can be added as arguments for extra control
        # Option: give a list of zooms to toggle through
        zooms = None
        # Option: adjust the camera pitch
        pitch_mod = 0

        try:
            if lat and lng:
                driver.get(f"http://127.0.0.1:5000/?id={id}&lat={lat}&lng={lng}")
            else:
                driver.get(f"http://127.0.0.1:5000/?id={id}")

            # This is a proxy to know when the streetview is visible
            wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'gm-iv-address-link')))
            time.sleep(.5)

        # We throw an error alert if we can't load the streetview
        # AttributeError is also theown sometimes when selenium can't find
        # an element matching '.gm-iv-address-link'
        except (UnexpectedAlertPresentException, AttributeError):
            raise NoPanoramaException()
        except KeyboardInterrupt:
            raise KeyboardInterrupt()
        except:
            print(traceback.format_exc())
            return

        # Get some important info from the webpage
        current_pano = driver.find_element(By.ID, 'initial-pano').text
        current_date = driver.find_element(By.ID, 'current-date').text
        additional_panos = []
        panos_picked = set([current_pano])
        
        if other_panos_text := driver.find_element(By.ID, 'other-panos').text:
            other_panos = json.loads(other_panos_text)
            additional_panos = additional_pano_selector(other_panos, panos_picked)
            
        all_dates = [{'pano': current_pano, 'date': current_date}] + additional_panos

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



def select_one_winter_month(other_dates: list, panos_picked: set):
    additional_panos = []
    # Get one winter month panorama if available
    # We reverse the list because dates usually given from earliest
    # but we're more interested in a recent panorama
    for date in reversed(other_dates):
        month = date['date'].split(' ')[0]
        if month in ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']:
            # Avoid duplicate panos
            if date['pano'] in panos_picked:
                continue
            additional_panos.append(date)
            panos_picked.add(date['pano'])
            break
    return additional_panos
    

def get_screenshots_worker(split):
    cases, show_browser, worker_id = split
    n_cases = len(cases)
    client = StreetviewScreenshotClient(show_browser=show_browser)
    
    progress_bar = tqdm(total=n_cases, desc=f"Worker {worker_id}", position=worker_id, leave=False)

    for case in cases:
        (id, lat, lng) = case
        try:
            client.screenshot(id, lat=lat, lng=lng, additional_pano_selector=select_one_winter_month)
            progress_bar.update(1)
        except KeyboardInterrupt:
            progress_bar.close()
            return
        except:
            progress_bar.update(1)
            continue


def get_screenshots(cases, show_browser=False):

    n_cases = len(cases)
    client = StreetviewScreenshotClient(show_browser=show_browser)

    for i, case in enumerate(cases):
        t0 = time.time()
        id, lat, lng = case

        print(f'Processing {id} - {i}/{n_cases}')
        try:
            client.screenshot(id, lat=lat, lng=lng, additional_pano_selector=select_one_winter_month)
            print(f'\tTook {round(time.time() - t0, 2)}s')
        except KeyboardInterrupt:
            return
        except:
            print(traceback.format_exc())
            continue


def split_cases_between_workers(cases, num_workers=1):

    # Get all the cases that have already been processed
    already_processed = set([p.stem for p in Path('screenshots').iterdir()])

    remaining = []
    for c in cases:
        if c[0] not in already_processed:
            remaining.append(c)

    splits = []

    cases_per_worker = math.ceil(len(remaining) / num_workers)

    for i in range(num_workers):
        splits.append(
            remaining[i * cases_per_worker : (i+1) * cases_per_worker]
        )

    return splits


def launch_jobs(cases, num_workers: int, show_browser=False):

    # Split the XMLs evenly between the workers
    splits = split_cases_between_workers(cases, num_workers)

    # Add other arguments to the worker function
    splits = [[s, show_browser, i] for i, s in enumerate(splits)]

    try:
        with Pool(processes=num_workers) as pool:
            pool.map(get_screenshots_worker, splits)
    except KeyboardInterrupt:
        print('Interrupt received')
        exit()


def get_cases():
    # This would normally come from a database of some kind
    return [
        ('0', 45.531776760335504, -73.55924595184348),
        ('1', 45.51094139932104, -73.81638931311772),
        ('2',  45.51527378493745, -73.69237796251304),
        ('3',  45.55818986570233, -73.53686788966166),
        ('4',  45.49014183901352, -73.57310636100624),
        ('5',  45.53124798085952, -73.55641122672318),
        ('6',  45.63741713212602, -73.60019103964953),
        ('7',  45.59124483325951, -73.58352296185546),
        ('8',  45.60397513103254, -73.5582978141316),
        ('9',  45.46878193043551, -73.64584833154453),
    ]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('coords', nargs='*', help="(id, lat, lng) tuple (optional)")
    parser.add_argument('-n', '--num-workers', type=int, default=1)
    parser.add_argument('-b', '--show-browser', action='store_true')
    args = parser.parse_args()
    
    coords = args.coords
    num_workers = args.num_workers
    show_browser = args.show_browser

    if coords:
        if len(coords) != 3:
            print('Invalid format: Please enter a (id, lat, lng) tuple.')
            print(coords)
            exit()

        get_screenshots([coords], show_browser=show_browser)
    else:
        cases = get_cases()
        if num_workers == 1:
            get_screenshots(cases, show_browser=show_browser)
        else:
            launch_jobs(cases, num_workers, show_browser)

