"""Explicit model download. Session transcription itself has no network access."""
from pathlib import Path
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--model',choices=['base.en','small.en'],default='small.en')
args=parser.parse_args()
from huggingface_hub import snapshot_download
destination=Path(__file__).resolve().parents[1]/'models'/('faster-whisper-'+args.model)
snapshot_download('Systran/faster-whisper-'+args.model,local_dir=str(destination),
                  allow_patterns=['model.bin','config.json','tokenizer.json','vocabulary.*'])
print(destination)
