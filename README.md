# Running Hooknet TLS Pipeline on CHPC (University of Utah)

Snakemake workflow for running HookNet-TLS inference on whole-slide pathology images (SVS) using the University of Utah CHPC environment.

This guide walks you through cloning and running this pipeline on the University of Utah's CHPC cluster, using the Open OnDemand VS Code Server. 

Read the "Storage" section before you start so that you do not accidentally run out of space in your home directory.

## Storage 

CHPC enforces several storage limits that this pipeline will hit if you don't plan around them up front:
- **Home directory: 50 GB soft quota, 75 GB hard quota.** Once you cross 50 GB you have 7 days to clean up before write access is cut off. At 75 GB, writes stop immediately, including the ability to launch a new OnDemand session, since OnDemand itself writes to your home directory on startup.
- **Scratch (/scratch/general/vast): 50 TB per-user quota, but files are auto-deleted after a period of inactivity and there is not backup.** This is where intermediate files such as converted/ and masks/ are created.
- **Group RAI scratch (/scratch/rai/vast1/stewartp/...): 1 TB shared capacity.** This holds the shared container and box data -- be mindful that this is shared with other group members, not yours alone.

Because of this, the repo itself should be small (code + config only). All large data -- slides, converted TIFFs, masks, the container, and results are stored in scratch, never in your home directory.

## Initial Setup
1. Launch the OnDemand VS Code Server
If you are working interactively in the browser via Open OnDemand, request a GPU only if you intend to actually run the GPU pipeline interactively. If you're submitting both pipelines as batch jobs with ```sbatch``` (recommended for anything beyond a quick test), GPU is not necessary.
2. Open the terminal in VS Code (Ctrl+`) and clone the github repository into your home directory

```bash
pwd     # should show your home directory

git clone https://github.com/AmandaWarren4134/hooknet_project.git
cd hooknet_project
```

3. Set up Apptainer environment variables
**Note: The repo itself is NOT sufficient to run TLS inference. The actual runtime environment comes from the pre-built Apptainer container, not from anything in this repo.**
The apptainer is built from a .sif that is found in this location: /scratch/rai/vast1/stewartp/hooknet_project/containers/hooknet_tls.sif

Run these commands in the terminal to set up the apptainer environment variables:

```bash 
module load apptainer

# Project (shared group scratch): holds the container and raw image data
export PROJECT=/scratch/rai/vast1/stewartp/hooknet_project
export SIF="$PROJECT/containers/hooknet_tls.sif"

# Work (your personal scratch): holds your intermediate converted files and masks
export WORK=/scratch/general/vast/$USER/hooknet_tmp
```

4. Create Required Workspace Directories

```bash
mkdir -p "$WORK/svs"
mkdir -p "$WORK/converted"
mkdir -p "$WORK/masks"
mkdir -p logs/cpu logs/gpu
```

5. Verify Container Works
```bash
apptainer exec "$SIF" \
python3 -c "import hooknettls; print(hooknettls.__file__)"
```

**Expected output:** 

```bash
/home/user/pathology-hooknet-tls/hooknettls/__init__.py
```

6. Verify Model Weights

```bash
apptainer exec "$SIF" \
ls -lh /home/user/pathology-hooknet-tls/weights
```

**Expected important file:**
```bash
lung_weights.h5
```

7. GPU Verification

```bash
nvidia-smi
```

## Pipeline Overview

The workflow is split into two stages:

1. **CPU Pipeline** – converts SVS slides to TIFF and generates tissue masks.
2. **GPU Pipeline** – runs HookNet-TLS inference and exports QuPath-compatible GeoJSON annotations.

The GPU pipeline depends on the outputs of the CPU pipeline and should be run after the CPU stage completes. The GPU pipeline checks for a cpu_complete.done marker and will not start inference until it exists.

## Overview

### Pipeline 1 (CPU)

Input:

* `.svs` whole-slide images

Output:

* Pyramidal TIFF files
* Tissue masks
* Completion marker

Workflow:

```text
SVS → TIFF → Tissue Mask → cpu_complete.done
```

### Pipeline 2 (GPU)

Input:

* TIFF image
* Tissue mask
* Completion marker

Output:

* HookNet-TLS XML annotations
* QuPath GeoJSON annotations

Workflow:

```text
TIFF + Mask → HookNet-TLS Inference → XML → GeoJSON
```

---

## Repository Structure

The GitHub Repository contains the workflow code, Snakemake files, configuration, and helper scripts only.

Large data files, containers, and generated results are stored separately on CHPC scratch storage due to storage limitations. (Each annotation set is roughly 500MB-1GB)

Currently, intermediate data files such as masks/ and converted/ are being stored in /scratch/general/vast/u6073678, which will be stored only temporarily.

## Code Repository

```text
hooknet_project/
├── Snakefile.cpu
├── Snakefile.gpu
├── common.smk
├── config.yaml
├── run_cpu_pipeline.sh
├── run_gpu_pipeline.sh
├── scripts/
├── logs/
| ├── cpu/
│ └── gpu/
└── README.md
```

## External Data Locations

```text
Group RAI Scratch Space (1TB capacity)
/scratch/rai/vast1/stewartp/hooknet_project/
├── box_raw/
├── containers/
│ └── hooknet_tls.sif
└── results/
```

```text
General Scratch Space (Emptied after 60 days)
/scratch/general/vast/<your-uNID>/hooknet_tmp/
├── converted/
├── cpu_complete.done
└── masks/
```

## Data Flow

Box Uploads
    ↓
box_raw/
    ↓
CPU Pipeline
    ↓
converted/
    ↓
masks/
    ↓
cpu_complete.done
    ↓
GPU Pipeline
    ↓
results/inference/
    ↓
results/geojson/

---

## Input Data

Place SVS slides in:

```text
PROJECT/box_raw/svs/
```

Example:

```text
box_raw/svs/
├── C3L-00415-23.svs
├── C3L-00821-01.svs
└── ...
```

**In config.yaml, change SVS_DIR and FOLDER to point at your input slides.**

```yaml
FOLDER: "svs"
SVS_DIR: "/scratch/rai/vast1/stewartp/hooknet_project/box_raw"
```

In this example, the slides are found in `/scratch/rai/vast1/stewartp/hooknet_project/box_raw/svs`.

### Rclone

You can use rclone to copy files from Box directly to the HPC, with further documentation available here: https://rclone.org/docs/

---

## Running the Pipelines

There are two ways to run each stage: an **interactive** allocation (good for testing a small number of slides) or a **batch submission** via the provided sbatch scripts (recommended for full runs). Both are covered below.

### Interactive Allocation (small tests)

CPU Pipeline

```bash
salloc \
  --mem=64G \
  --time=04:00:00 \
  -p notchpeak-freecycle \
  --qos=notchpeak-freecycle \
  -A stewartp
```

### Dry Run First -- confirms what would execute, runs nothing

```bash
snakemake -s Snakefile.cpu --dry-run --cores 8
```

### Execute (the real run)

```bash
snakemake -s Snakefile.cpu --cores 8
```

CPU workflow:

1. Validate slide input
2. Convert SVS → TIFF
3. Generate tissue mask
4. Create completion marker

Output:

```text
$WORK/converted/*.tif
$WORK/masks/*_mask.tif
$WORK/cpu_complete.done
```

---

## GPU Pipeline

### Interactive Allocation

Example RTX3090 allocation:

```bash
salloc \
  --mem=32G \
  --time=02:00:00 \
  --nodes=1 \
  --ntasks=1 \
  --account=notchpeak-gpu \
  --partition=notchpeak-gpu \
  --gres=gpu:rtx3090:1
```

### Dry Run

```bash
snakemake -s Snakefile.gpu --dry-run --cores 8
```

### Execute

```bash
snakemake -s Snakefile.gpu --cores 8
```

GPU workflow:

1. Wait for `cpu_complete.done`
2. Run HookNet-TLS inference
3. Generate post-processed XML
4. Convert XML → QuPath GeoJSON

Output:

```text
results/
├── inference/
│   └── <run_folder>/
│       └── <slide>/
├── geojson/
│   └── <slide>.geojson
└── logs/
```

## Batch Submission (recommended for full runs)
Rather than holding an interactive allocation open in your terminal, you can submit each stage as its own Slurm job using the provided scripts. Snakemake itself runs the outer job and submits each individual rule as its own Slurm job.

### Run the CPU pipeline first:

```bash
sbatch run_cpu_pipeline.sh
```

Once it completes successfully (check logs/cpu/cpu_pipeline_<jobid>.log and confirm $WORK/cpu_complete.done exists), then submit the GPU pipeline:

```bash 
sbatch run_gpu_pipeline.sh
```

A few things worth understanding about how these scripts work, since they're
not immediately obvious from reading the `#SBATCH` headers alone:


- The outer job is lightweight, not the actual work. The #SBATCH
directives at the top of each script (`--mem=8G`, `--cpus-per-task=2`,
`--partition=notchpeak-freecycle`) describe the driver job — the Snakemake process itself — not the GPU inference job. Snakemake's `--executor slurm` mode submits each individual rule as its own separate Slurm job with its own resource request. You will see this driver job sitting in
`notchpeak-freecycle` in squeue even while running the GPU pipeline — that is expected, the actual inference jobs land on `notchpeak-gpu` because the inference rule in Snakefile.gpu specifies that explicitly.

- `--default-resources` in the script vs. per-rule resources in the Snakefile: the `sbatch` script sets `slurm_partition=notchpeak-freecycle`
as a default. This is only used as a fallback for rules that don't specify their own resources (like `xml_to_geojson`). Rules that set their own `resources:` block — like `inference`, which requests `notchpeak-gpu` and `--gres=gpu:1` override the default and run on the
GPU partition as intended.
- `--jobs 20` caps how many Slurm jobs Snakemake will have in flight atonce across all rules. Lower this if you want to be a better neighbor on shared partitions, or raise it if you have many independent slides queued and want more throughput.
- `--rerun-incomplete` means a resubmission after a partial failure willpick back up rather than refusing to touch files it considers incomplete.


Email notifications go to whatever address is set in --mail-user in each
script — update this to your own email.

---

## Output Files

### HookNet XML

```text
results/inference/<folder>/<slide>/post-processed/
```

Example:

```text
C3L-00415-23_hooknettls_post_processed.xml
```

The XML file can be opened with ASAP Viewer on top of the SVS image.

### QuPath GeoJSON

```text
results/geojson/<slide>.geojson
```

These files can be imported directly into QuPath.

---



## Troubleshooting

### Re-running after a failed or interrupted job

Snakemake tracks which outputs already exist, so the normal recovery path is just to re-run the same command (interactively) or resubmit the same `sbatch` script -- completed work will be skipped automatically with `--rerun-incomplete` set.

If Snakemake refuses to run and reports a locked working directory (usually after a job was killed abruptly), unlock it:

```bash 
snakemake -s Snakefile.gpu --configfile config.yaml --unlock
```

then resubmit or re-run as normal.

**Note on the GPU pipeline specifically:** the inference rule deletes its per-slide intermediate inputs (.svs, mask) after a successful run to manage scratch space. This means a successful slide is not "re-runnable" from its old intermediates. If you need to regenerate inference output for a slide that already finished, you'll need to re-run the CPU pipeline for that slide first to regenerate its TIFF/mask.

### GPU not visible inside the container

```bash 
apptainer exec --nv "$SIF" nvidia-smi
```

If this fails, confirm you're on a node with a GPU actually allocated.

### OpenSlide check

OpenSlide is baked into the current `hooknet_tls.sif` and has been verified to work correctly. 

```bash 
apptainer exec --no-home "$SIF" python3 -c "import openslide; print(openslide.__version__)"
```

If this ever fails, that means OpenSlide needs to be added to the apptainer definition file and the image rebuilt.

### Wrong model weights path

The pipeline's default config can point at a weights path that doesn't match
what's actually in the container. The GPU Snakefile already overrides this
correctly for you:

```bash
hooknettls.default.model_weights=/home/user/pathology-hooknet-tls/weights/lung_weights.h5
```

You shouldn't need to touch this, but if you ever see a "no such file"
error referencing a different weights path, this override line in
Snakefile.gpu is the first place to check.

## Key Scripts

| Script                        | Purpose                                        |
| ----------------------------- | ---------------------------------------------- |
| `save_image_at_spacing.py` | Convert SVS to pyramidal TIFF                  |
| `create_mask_tif.py`          | Generate tissue masks                          |
| `asap_to_qupath_geojson.py`   | Convert ASAP XML annotations to QuPath GeoJSON |

---

## References

### HookNet-TLS

https://github.com/DIAGNijmegen/pathology-hooknet-tls

### Original Mask Generation Reference

https://github.com/revantht-pixel/hci-tls-segmentation

### Repository

https://github.com/AmandaWarren4134/hooknet_project

---

## Author

Amanda Warren

University of Utah
