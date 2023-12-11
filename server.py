import io
import IPython
from PIL import Image
from pathlib import Path
from dotenv import dotenv_values
from w3lib.url import parse_data_uri
from flask import Flask, url_for, render_template, request, redirect, session, abort

ENV = dotenv_values(".env")

app = Flask(__name__)
app.secret_key = ENV['APP_SECRET_KEY']

IMG_OUTPUT_DIR = './screenshots'
MAPS_API_KEY = ENV['MAPS_API_KEY']

print(MAPS_API_KEY)

# This would normally be a database of some kind
DATASET = {
 '0': {'lat':  45.52716794325363, 'lng':  -73.6249246727188},
 '1': {'lat': 45.531776760335504, 'lng': -73.55924595184348},
 '2': {'lat':  45.51527378493745, 'lng': -73.69237796251304},
 '3': {'lat':  45.55818986570233, 'lng': -73.53686788966166},
 '4': {'lat':  45.49014183901352, 'lng': -73.57310636100624},
 '5': {'lat':  45.53124798085952, 'lng': -73.55641122672318},
 '6': {'lat':  45.63741713212602, 'lng': -73.60019103964953},
 '7': {'lat':  45.59124483325951, 'lng': -73.58352296185546},
 '8': {'lat':  45.60397513103254, 'lng':  -73.5582978141316},
 '9': {'lat':  45.46878193043551, 'lng': -73.64584833154453},
}

@app.route("/pano", methods=['GET', 'POST'])
def get_panos():

    if request.method == 'POST':
        session['data'] = request.json
        return redirect(url_for('panos'))

    pano_id = request.args.get('pano_id')
    lat, lng = request.args.get('lat'), request.args.get('lng')

    return render_template('index.html', pano_id=pano_id, lat=lat, lng=lng, key=MAPS_API_KEY)


@app.route("/upload", methods=['POST'])
def upload():
    """
    Saves an image locally.
    Could be modified to upload the image to a bucket.
    """
    data = request.json
    id = data['id']
    pano = data['pano']
    date = data['date']
    image = parse_data_uri(data['img'])
    image = Image.open(io.BytesIO(image.data))
    path = Path(f'{IMG_OUTPUT_DIR}/{id}')
    path.mkdir(exist_ok=True, parents=True)
    n_files = len(list(path.iterdir()))
    image.save(path / f'{id}_{n_files}_{date}_{pano}.jpg')
    return 'ok'


@app.route("/", methods=['GET'])
def screenshot():
    id = request.args.get('id')
    if not id:
        id = 0
    if id in DATASET:
        lat, lng = DATASET[id].values()

    return render_template('index.html', id=id, lat=lat, lng=lng, key=MAPS_API_KEY)


@app.route("/older_pano_links")
def get_older_pano_links():

    if request.method == 'POST':
        session['data'] = request.json
        return redirect(url_for('panos'))
    
    pano_id = request.args.get('pano_id')
    lat, lng = request.args.get('lat'), request.args.get('lng')


    return render_template('pano_links_by_id.html', pano_id=pano_id, lat=lat, lng=lng, key=MAPS_API_KEY)


@app.route("/result")
def panos():

    data = session['data']

    if data:
        return data
    else:
        return {}


