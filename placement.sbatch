#!/bin/bash
#SBATCH -J pa4-placement
#SBATCH -p RM-shared
#SBATCH -N 1
#SBATCH --ntasks-per-node=16
#SBATCH -t 00:15:00
#SBATCH -o placement-%j.out

# Same allocation as mpi_submit; only the rank placement changes.
cd "$SLURM_SUBMIT_DIR"
export HOSTNAME=${HOSTNAME:-$(hostname -s)}
module load openmpi
echo "host: $(hostname)  job: $SLURM_JOB_ID  date: $(date)"
echo "cpus this job may use: $(grep Cpus_allowed_list /proc/self/status | cut -f2)"
for map in core l3cache; do
  echo "##### --map-by $map"
  mpirun -n 8 --map-by $map --bind-to core --report-bindings ./mvm 8 2>&1 | grep -i bound
  for np in 1 2 4 8; do
    for r in 1 2 3; do
      echo "=== map=$map np=$np run=$r"
      mpirun -n $np --map-by $map --bind-to core ./mvm 32000 | grep -E "time|discrepancy" | head -3
    done
  done
  echo "=== transpose map=$map p=8"
  mpirun -n 8 --map-by $map --bind-to core ./transpose 16000 3
done
echo "##### accounting for this lab's jobs"
sacct -u sustaita -S 2026-11-09 --format=JobID,JobName%15,Partition,AllocCPUS,Elapsed,State,NodeList -X
