import os
import json
from tqdm import tqdm
from sklearn.metrics import accuracy_score

from inference import HatefulMemesInference
model = HatefulMemesInference()

DATA_DIR = '/lfs/local/0/paridhi/MultimodalHateSpeech/HatefulMemesDataset'
DATA_FILES = {
	'train' : ['train.jsonl'],
	'val' : ['dev_seen.jsonl', 'dev_unseen.jsonl'],
	'test' : ['test_seen.jsonl', 'test_unseen.jsonl']
}

for subset, files in DATA_FILES.items():
	data = []
	for filename in files:
		with open(os.path.join(DATA_DIR, filename), 'r') as json_file:
			json_list = list(json_file)

		for json_str in json_list:
			result = json.loads(json_str)
			data.append(result)

	label, pred = [], []
	for row in tqdm(data):
		image_path, text = row['img'], row['text']
		image_path = os.path.join(DATA_DIR, image_path)
		prob = model.infer(image_path, text)
		label.append(row['label'])
		pred.append(prob > 0.5)

	accuracy = accuracy_score(label, pred)
	print(f'Number of memes in {subset} subset: {len(data)}')
	print(f'Accuracy on {subset} subset: {accuracy:.3f}')
