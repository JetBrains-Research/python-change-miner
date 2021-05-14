import csv
import json
import os
import pickle
from typing import List

from tqdm import tqdm
import settings

CHANGE_GRAPHS_STORAGE_DIR = settings.get("change_graphs_storage_dir")

PATTERNS_OUTPUT_DIR = settings.get("patterns_output_dir")

DOMAINS = {"Web": {"flask", "pyramid", "flexx", "websockets", "scrapy", "splinter", "werkzeug",
                   "mechanicalsoup", "httpie", "web2py", "sanic", "spotipy", "falcon",
                   "websockify", "dash"},
           "Data": {"scikit-learn", "matplotlib", "mlxtend", "scikit-multiflow", "tslearn", "tpot",
                    "hyperspy", "modin", "ibis", "agate", "bokeh", "tablib", "datasette",
                    "pyexcel", "orange3"},
           "Science": {"sage", "joblib", "dask", "golem", "stumpy", "numba", "autograd", "cupy",
                       "statsmodels", "mpmath", "pycuda", "numexpr", "sparse", "theano",
                       "biopython"},
           "NLP": {"spacy", "textacy", "gensim", "stanza", "allennlp", "rasa", "textblob",
                   "konlpy", "cltk", "ai-chatbot-framework", "rasa_nlu_chi", "pytorch-nlp",
                   "hanlp", "nlp-progress", "pattern"},
           "Media": {"musicbot", "musicbox", "librosa", "gmusicapi", "quodlibet", "feeluown",
                     "moviepy", "streamlink", "pytube", "openshot-qt", "imageio", "pyscenedetect",
                     "sms-tools", "mutagen", "exaile"},
           "DL": {"pysyft", "keras", "chainercv", "deepchem", "tensor2tensor", "ray", "niftynet",
                  "streamlit", "tensorlayer", "imgaug", "tensorpack", "deeppavlov", "opennmt-py",
                  "gpflow", "nni"}}


def cgs_to_csv() -> None:
    with open(os.path.join(CHANGE_GRAPHS_STORAGE_DIR, "cgs.csv"), "w+") as fout:
        csv_writer = csv.writer(fout, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(["Repository name", "Commit date", "Number of nodes"])
        for file in tqdm([file for file in os.listdir(CHANGE_GRAPHS_STORAGE_DIR)
                          if file.endswith(".pickle")]):
            with open(os.path.join(CHANGE_GRAPHS_STORAGE_DIR, file), "rb") as fin:
                graphs = pickle.load(fin)
                for graph in graphs:
                    cg = pickle.loads(graph)
                    csv_writer.writerow([cg.repo_info.repo_name,
                                         cg.repo_info.commit_dtm.strftime('%d.%m.%Y %H:%M:%S'),
                                         len(cg.nodes)])


def list_dirs(path: str) -> List[str]:
    return [os.path.join(path, d) for d in os.listdir(path)
            if os.path.isdir(os.path.join(path, d))]


def patterns_to_csv() -> None:
    with open(os.path.join(PATTERNS_OUTPUT_DIR, "patterns.csv"), "w+") as fout:
        csv_writer = csv.writer(fout, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(["Pattern size", "Pattern ID", "Pattern frequency", "Pattern repos",
                             "Pattern commits", "Sample ID", "Repository", "Datetime"])
        for pattern_size_dir in tqdm(list_dirs(PATTERNS_OUTPUT_DIR)):
            pattern_size = os.path.basename(pattern_size_dir)
            for pattern_id_dir in list_dirs(pattern_size_dir):
                pattern_csv_entries = []
                pattern_id = os.path.basename(pattern_id_dir)
                pattern_files = []
                datetimes = set()
                repos = set()
                for file in os.listdir(pattern_id_dir):
                    if file.endswith(".json"):
                        pattern_files.append(os.path.join(pattern_id_dir, file))
                frequency = len(pattern_files)
                for file in pattern_files:
                    with open(os.path.join(pattern_id_dir, file)) as fin:
                        sample_id = file.split(".")[0].split("-")[-1]
                        sample_data = json.load(fin)
                        repo = sample_data["repo"]["url"]
                        repos.add(repo)
                        datetime = sample_data["commit"]["dtm"]
                        datetimes.add(datetime)
                        pattern_csv_entries.append([pattern_size, pattern_id, frequency,
                                                    sample_id, repo, datetime])
                for entry in pattern_csv_entries:
                    csv_writer.writerow([entry[0], entry[1], entry[2], len(repos), len(datetimes),
                                         entry[3], entry[4], entry[5]])


if __name__ == '__main__':
    cgs_to_csv()
    patterns_to_csv()