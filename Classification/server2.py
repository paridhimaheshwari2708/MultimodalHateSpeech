import os
import logging
import pytesseract
from PIL import Image
from uuid import uuid4
from datetime import datetime
from flask import Flask, request, jsonify, render_template

from inference import HatefulMemesInference
model = HatefulMemesInference()

DATA_DIR = 'ServerRequests'

app = Flask(__name__, template_folder='/lfs/local/0/paridhi/MultimodalHateSpeech/Classification/')

logger = logging.getLogger('werkzeug') # grabs underlying WSGI logger
handler = logging.FileHandler('server2.log') # creates handler for the log file
logger.addHandler(handler) # adds handler to the werkzeug WSGI logger

@app.route('/')
def upload_file():
    return render_template('index.html')

@app.route('/infer', methods=['GET', 'POST'])
def infer():
    if request.method == 'POST':
        f = request.files['file']
        event_id = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-') + str(uuid4())
        image_path = os.path.join(DATA_DIR, f'{event_id}.png')
        f.save(image_path)
        text = request.form.get('caption', '')
        if text == '':
            text = pytesseract.image_to_string(Image.open(image_path))
        prob = model.infer(image_path, text)
        # Logging
        logger.info('-'*100)
        logger.info(f'Text: {text}')
        logger.info(f'Image Path: {image_path}')
        logger.info(f'Probability of Hateful: {prob:.3f}')
        logger.info('-'*100)
        return jsonify({'Hateful': prob})

if __name__ == '__main__':
    # run() method of Flask class runs the application on the local development server.
    app.run(host='0.0.0.0', port=8080, debug=True)