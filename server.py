import os
import wget
import logging
from uuid import uuid4
from datetime import datetime
from flask import Flask, request, jsonify
from inference import HatefulMemesInference

DATA_DIR = "ServerRequests"

app = Flask(__name__)
model = HatefulMemesInference()

logger = logging.getLogger('werkzeug') # grabs underlying WSGI logger
handler = logging.FileHandler('server.log') # creates handler for the log file
logger.addHandler(handler) # adds handler to the werkzeug WSGI logger

'''
*CALLING THE SERVER IN BROWSER*
Template: http://turing4.stanford.edu:8080/?text=<ADD_TEXT_HERE>&image=<ADD_IMAGE_URL_HERE>
Sample: http://turing4.stanford.edu:8080/?text=you can't be racist if there is no other race&image=http://turing4.stanford.edu:8081/img/01247.png

*CALLING THE SERVER PROGRAMMATICALLY FROM PYTHON*
import requests

text = "you can't be racist if there is no other race"
image_path = "http://turing4.stanford.edu:8081/img/01247.png"

query_to_server = f"http://turing4.stanford.edu:8080/?text={text}&image={image_path}"
output = requests.get(query_to_server).json()
print(output)
'''

@app.route('/')
def infer():
    text = request.args.get('text')
    image_url = request.args.get('image')
    event_id = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-') + str(uuid4())
    image_path = os.path.join(DATA_DIR, f"{event_id}.png")
    wget.download(image_url, image_path)
    prob = model.infer(image_path, text)
    # Logging
    logger.info("-"*100)
    logger.info(f"Text: {text}")
    logger.info(f"Image URL: {image_url}")
    logger.info(f"Image Path: {image_path}")
    logger.info(f"Probability of Hateful: {prob:.2f}")
    logger.info("-"*100)
    return jsonify({"Hateful": prob})

if __name__ == '__main__':
    # run() method of Flask class runs the application on the local development server.
    app.run(host='0.0.0.0', port=8080, debug=True)