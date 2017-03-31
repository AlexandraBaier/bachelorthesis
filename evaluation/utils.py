import json
import logging
from typing import List, Tuple

import numpy as np

from evaluation.data_sample import MultiLabelSample


def load_config(config_path: str)->dict:
    with open(config_path) as f:
        config = json.load(f)
    return config


def load_training_data(training_data_path: str)->List[MultiLabelSample[str]]:
    training_samples = list()  # type: List[MultiLabelSample[str]]
    with open(training_data_path) as f:
        for idx, r in enumerate(f):
            if idx == 0:
                continue
            training_samples.append(MultiLabelSample.from_csv(r, col_sep=','))
    return training_samples


def load_test_data(test_data_path: str)->List[MultiLabelSample]:
    test_samples = list()  # type: List[MultiLabelSample]
    with open(test_data_path) as f:
        for idx, r in enumerate(f):
            if idx == 0:
                continue
            test_samples.append(MultiLabelSample.from_csv(r, col_sep=','))
    return test_samples


def load_test_inputs(test_data_path: str)->List[str]:
    return [sample.input_arg for sample in load_test_data(test_data_path)]


def load_embeddings_and_labels(embeddings_path: str)->Tuple[np.array, List[str]]:
    class_ids = list()
    embeddings = list()
    with open(embeddings_path) as f:
        for cid, embedding in map(lambda l: l.strip().split(';'), f):
            embedding = np.array(embedding.strip('[').strip(']').strip().split(), dtype=np.float32)
            class_ids.append(cid)
            embeddings.append(embedding)
    embeddings = np.array(embeddings)  # type: np.array
    return embeddings, class_ids


def algo2color(algo):
    colors = {
        'ts+kriknn(k=15&r=1)': '#3f9b0b',  # grass green
        'ts+distknn(k=15)': '#89fe05',  # lime green
        'ts+linproj': '#00ffff',  # cyan
        'ts+pwlinproj(c=30)': '#00035b',  # dark blue
    }
    default = '#e50000'  # red
    return colors.get(algo, default)
