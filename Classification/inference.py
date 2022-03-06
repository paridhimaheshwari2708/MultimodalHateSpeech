'''
./miniserve HatefulMemesDataset/ --port 8081
'''

import os
import sys
import torch
import shutil
import requests
import pytesseract
from PIL import Image
from uuid import uuid4
from datetime import datetime
from omegaconf import OmegaConf
import torch.nn.functional as F

from mmf.common.registry import registry
from mmf.common.sample import Sample, SampleList
from mmf.datasets.processors.bert_processors import BertTokenizer
from mmf.datasets.processors.image_processors import TorchvisionTransforms

class HatefulMemesInference:
    def __init__(self, relative_dir):
        self.model = None
        self.text_processor = None
        self.image_processor = None
        self._get_model()
        self._get_processers(relative_dir=relative_dir)
        self.data_dir = os.path.join(relative_dir, 'ServerRequests')

    def _get_model(self):
        # model_cls = registry.get_model_class("concat_bert")
        # self.model_concat_bert = model_cls.from_pretrained("concat_bert.hateful_memes")
        # self.model_concat_bert.eval()

        model_cls = registry.get_model_class("late_fusion")
        self.model_late_fusion = model_cls.from_pretrained("late_fusion.hateful_memes")
        self.model_late_fusion.eval()

        # model_cls = registry.get_model_class("unimodal_text")
        # self.model_unimodal_text = model_cls.from_pretrained("unimodal_text.hateful_memes.bert")
        # self.model_unimodal_text.eval()

        # model_cls = registry.get_model_class("unimodal_image")
        # self.model_unimodal_image = model_cls.from_pretrained("unimodal_image.hateful_memes.images")
        # self.model_unimodal_image.eval()
    
    def _prepare_sample(self, image_path, text):
        sample = Sample()
        assert os.path.exists(image_path)
        image = Image.open(image_path).convert("RGB")
        image_input = self.image_processor({"image": image})
        sample.image = image_input["image"]
        text_input = self.text_processor({"text" : text})
        sample.update(text_input)
        return SampleList([sample])

    def _get_processers(self, relative_dir):
        text_processor_config = OmegaConf.load(os.path.join(relative_dir, "text_processor_config.yaml"))
        self.text_processor = BertTokenizer(text_processor_config)
        image_processor_config = OmegaConf.load(os.path.join(relative_dir, "image_processor_config.yaml"))
        self.image_processor = TorchvisionTransforms(image_processor_config)

    def infer(self, image_url, text, model='late_fusion'):
        # Downloading image with unique file identifier
        event_id = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-') + str(uuid4())
        image_path = os.path.join(self.data_dir, f'{event_id}.png')
        r = requests.get(image_url, stream=True)
        if r.status_code == 200:
            with open(image_path, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)

        # Running OCR to fetch text
        if text is None:
            text = pytesseract.image_to_string(image_path)
            print("Inferring text using OCR")
            print(f"Text: {text}")

        # Passing data to model
        sample_list = self._prepare_sample(image_path, text)
        with torch.no_grad():
            if model == 'concat_bert':
                prob = F.softmax(self.model_concat_bert(sample_list)["scores"], dim=1)[0, 1]
            elif model == 'late_fusion':
                prob = F.softmax(self.model_late_fusion(sample_list)["scores"], dim=1)[0, 1]
            elif model == 'unimodal_text':
                prob = F.softmax(self.model_unimodal_text(sample_list)["scores"], dim=1)[0, 1]
            elif model == 'unimodal_image':
                prob = F.softmax(self.model_unimodal_image(sample_list)["scores"], dim=1)[0, 1]
        print(f"Hateful Meme Score: {prob.item()}")
        return prob.item()

# if __name__ == "__main__":
#     hm = HatefulMemesInference('./')
#     import pdb; pdb.set_trace()
#     score = hm.infer("https://cdn.discordapp.com/attachments/929994521545150494/949815976306835537/hateful-memes-skunk.png", "love the way you smell today")
#     print(score)
#     score = hm.infer("https://cdn.discordapp.com/attachments/929994521545150494/949815976306835537/hateful-memes-skunk.png", "")
#     print(score)
#     score = hm.infer("https://cdn.discordapp.com/attachments/929994521545150494/949815976306835537/hateful-memes-skunk.png", None)
#     print(score)
