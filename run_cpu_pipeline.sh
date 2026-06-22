#!/bin/bash
#SBATCH --job-name=hooknet_cpu_pipeline
#SBATCH --account=stewartp
#SBATCH --partition=notchpeak-freecycle
#SBATCH --qos=notchpeak-freecycle
#SBATCH --time=36:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=logs/cpu/cpu_pipeline_%j.log
#SBATCH --error=logs/cpu/cpu_pipeline_%j.log
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=aw998@byu.edu

set -euo pipefail

# Load snakemake (ensure this module is v9+)
module load snakemake

# Create log directory
mkdir -p logs/cpu

# Run CPU pipeline (validate → convert → mask → cpu_complete)
snakemake \
    --snakefile Snakefile.cpu \
    --configfile config.yaml \
    --executor slurm \
    --default-resources \
        slurm_account=stewartp \
        slurm_partition=notchpeak-freecycle \
        slurm_extra="'--qos=notchpeak-freecycle'" \
        runtime=120 \
        mem_mb=16000 \
        cpus_per_task=4 \
    --jobs 20 \
    --latency-wait 60 \
    --rerun-incomplete \
    --printshellcmds