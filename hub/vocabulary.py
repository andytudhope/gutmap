"""Discovery labels used by the paper importer and map."""
import json
from .db import ROOT
TOPICS=json.loads((ROOT/'content/vocabulary.json').read_text())
