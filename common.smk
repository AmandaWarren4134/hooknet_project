import os
import glob

configfile: "config.yaml"

debug = False

config["SVS_DIR"] = f"{config['SVS_DIR']}/{config['FOLDER']}"
SVS_DIR = config["SVS_DIR"]

SVS_FILES = glob.glob(os.path.join(SVS_DIR, "*.svs"))

def slide_id(path):
    return os.path.splitext(os.path.basename(path))[0]

SLIDES = [slide_id(p) for p in SVS_FILES]

SLIDE_TO_PATH = {slide_id(p): p for p in SVS_FILES}

if debug:
    print("SVS_DIR:", SVS_DIR)
    print("Found slides:")
    for f in SVS_FILES:
        print(f)