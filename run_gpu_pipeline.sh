#!/bin/bash
#SBATCH --job-name=hooknet_pipeline
#SBATCH --account=stewartp
#SBATCH --partition=notchpeak-freecycle
#SBATCH --qos=notchpeak-freecycle
#SBATCH --time=72:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=logs/gpu/gpu_pipeline_%j.log
#SBATCH --error=logs/gpu/gpu_pipeline_%j.log
#SBATCH --mail-type=ALL
#SBATCH --mail-user=aw998@byu.edu

set -euo pipefail

module load snakemake

mkdir -p logs/gpu

snakemake \
    --snakefile Snakefile.gpu \
    --configfile config.yaml \
    --executor slurm \
    --default-resources \
        slurm_account=stewartp \
        slurm_partition=notchpeak-freecycle \
        slurm_extra="--qos=notchpeak-freecycle" \
        runtime=60 \
        mem_mb=16000 \
        cpus_per_task=4 \
    --jobs 20 \
    --latency-wait 60 \
    --rerun-incomplete \
    --printshellcmds