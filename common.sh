# Sourced by the job scripts: load MPI and build from source in the submit dir.
cd "$SLURM_SUBMIT_DIR"
export HOSTNAME=${HOSTNAME:-$(hostname -s)}
module load openmpi
set -e
echo "host: $(hostname)  job: $SLURM_JOB_ID  date: $(date)"
mpicc --version | head -1
make -s mvm
