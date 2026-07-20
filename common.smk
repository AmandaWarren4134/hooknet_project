import os
import glob

configfile: "config.yaml"

debug = False

config["SVS_DIR"] = f"{config['SVS_DIR']}/{config['FOLDER']}"
SVS_DIR = config["SVS_DIR"]

SVS_FILES = sorted(glob.glob(os.path.join(SVS_DIR, "**", "*.svs"), recursive=True))

def slide_id(path):
    return os.path.splitext(os.path.basename(path))[0]

SLIDE_TO_PATH = {}
for p in SVS_FILES:
    sid = slide_id(p)
    if sid in SLIDE_TO_PATH:
        raise ValueError(f"Duplicate slide ID found: {sid}")
    SLIDE_TO_PATH[sid] = p

SLIDES = sorted(SLIDE_TO_PATH)

if debug:
    print("SVS_DIR:", SVS_DIR)
    print("Found slides:")
    for sid in SLIDES:
        print(f" - {sid}: {SLIDE_TO_PATH[sid]}")