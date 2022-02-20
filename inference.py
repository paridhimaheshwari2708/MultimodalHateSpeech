import os
import sys
import torch
# import pytesseract
from PIL import Image
from omegaconf import OmegaConf
import torch.nn.functional as F

from mmf.common.registry import registry
from mmf.common.sample import Sample, SampleList
from mmf.datasets.processors.bert_processors import BertTokenizer
from mmf.datasets.processors.image_processors import TorchvisionTransforms

class HatefulMemesInference:
    def __init__(self):
        self.model = None
        self.text_processor = None
        self.image_processor = None
        self._get_model()
        self._get_processers()

    def _get_model(self):
        model_cls = registry.get_model_class("concat_bert")
        self.model = model_cls.from_pretrained("concat_bert.hateful_memes")
        self.model.eval()
    
    def _prepare_sample(self, image_path, text):
        sample = Sample()
        assert os.path.exists(image_path)
        image = Image.open(image_path).convert("RGB")
        image_input = self.image_processor({"image": image})
        sample.image = image_input["image"]
        text_input = self.text_processor({"text" : text})
        sample.update(text_input)
        return SampleList([sample])

    def _get_processers(self):
        text_processor_config = OmegaConf.load('text_processor_config.yaml')
        self.text_processor = BertTokenizer(text_processor_config)
        image_processor_config = OmegaConf.load('image_processor_config.yaml')
        self.image_processor = TorchvisionTransforms(image_processor_config)

    def infer(self, image_path, text):
        # if text is None:
        #     text = pytesseract.image_to_string(image_path)
        #     print("Inferring text using OCR")
        sample_list = self._prepare_sample(image_path, text)
        with torch.no_grad():
            prob = F.softmax(self.model(sample_list)["scores"], dim=1)[0, 1]
        return prob.item()

# if __name__ == "__main__":
#     hm = HatefulMemesInference()
#     hm.infer("tmp.png", "every life is precious")
#     hm.infer("tmp.png", None)
