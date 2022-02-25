# Hate Detection in Memes

For the backend of our project, we work with the "Hateful Memes" dataset from Facebook with over 10,000 labeled examples of memes that combine multiple modalities. These memes were created in a way that intentionally circumvents unimodal classifiers. The dataset can be downloaded from this [link](https://hatefulmemeschallenge.com/).

For automated hate detection in memes, we employ a pretrained model from MMF, a modular framework developed for Multimodal research. We use a deep learning model called ConcatBERT, a state-of-the-art network which has proven useful in a variety of natural language processing applications. For text, it extracts features from a BERT model which has been trained on a large corpus of real-world text. For images, it uses the hidden layer representations of a ResNet-152 model pretrained on the large-scale ImageNet dataset. Both feature representations (786 dimensiona for text and 2048 dimension for image) are concatenated to form the input to the model. A 2-layer fully-connected neural network is trained on the binary classification task to predict whether a meme is hateful or not.

The model is multimodal and requires the image itself as well as the text overlaying that image as a separate input. For cases when we only have the image (and not the associated text), we have integrated OCR technology into our backend that pulls the text from the image automatically.

To run the code programmatically in python, use the following code snippet
```
import pytesseract
from PIL import Image
from inference import HatefulMemesInference

# Load the model
model = HatefulMemesInference()

# Define the local path to the image
image_path = 'MultimodalHateSpeech/HatefulMemesDataset/img/01247.png'

# Enter the assciated text caption
text = 'you can't be racist if there is no other race'
if text == '':
    text = pytesseract.image_to_string(Image.open(image_path))

# Get model prediction
prob = model.infer(image_path, text)
print({'Hateful': prob})
```
