#!/bin/bash
#SBATCH --job-name=hooknet_cpu
#SBATCH --partition=notchpeak-freecycle
#SBATCH --qos=notchpeak-freecycle
#SBATCH --account=stewartp
#SBATCH --time=06:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --output=logs/hooknet_%j.out
#SBATCH --error=logs/hooknet_%j.err

module load apptainer

# Paths
PROJECT=/uufs/chpc.utah.edu/common/home/$USER/hooknet_project
SIF=$PROJECT/containers/hooknet_tls.sif
WORK=/scratch/general/vast/$USER/hooknet_tls_test

# Ensure tmp/output dirs exist
mkdir -p $WORK/tmp $WORK/output/images

echo "Running on host: $(hostname)"
echo "Start time: $(date)"

time apptainer exec \
  --bind $WORK:/workspace \
  --bind $WORK/tmp:/home/user/tmp \
  "$SIF" \
  python -m hooknettls \
  hooknettls.default.image_path=/workspace/converted/C3L-00415-23.tif \
  hooknettls.default.mask_path=/workspace/masks/C3L-00415-23_mask.tif \
  hooknettls.default.model_weights=/home/user/pathology-hooknet-tls/weights/lung_weights.h5 \
  hooknettls.default.output_folder=/workspace/output/images/

echo "End time: $(date)"