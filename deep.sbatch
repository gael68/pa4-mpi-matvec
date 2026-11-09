#!/bin/bash
#SBATCH -J pa4-deep
#SBATCH -p RM-shared
#SBATCH -N 1
#SBATCH --ntasks-per-node=16
#SBATCH -t 00:30:00
#SBATCH -o deep-%j.out

# Same partition and size as the graded runs, so these explain those numbers.
cd "$SLURM_SUBMIT_DIR"
export HOSTNAME=${HOSTNAME:-$(hostname -s)}
module load openmpi
echo "host: $(hostname)  job: $SLURM_JOB_ID  date: $(date)"

echo "##### environment"
module list 2>&1
mpicc --showme
ompi_info | grep -E "Open MPI:|Configured architecture|C compiler absolute"
lscpu | grep -E "Model name|Socket|Core|Thread|NUMA|L1d|L2|L3|MHz"
echo "cpus this job may use: $(grep Cpus_allowed_list /proc/self/status | cut -f2)"
numactl --show
free -g | head -2

mpicc -O2 -o mvm-timed mvm_timed.c mvm-driver.c

echo "##### where the ranks run (default mapping)"
for np in 2 4 8; do
  echo "=== np=$np"
  mpirun -n $np --report-bindings ./mvm 8 2>&1 | grep -iE "bound|rank"
done

echo "##### allgather vs compute, per rank"
for n in 1000 4000 16000 32000; do
  for np in 1 2 4 8; do
    for r in 1 2 3; do
      echo "=== n=$n np=$np run=$r"
      mpirun -n $np ./mvm-timed $n | grep -v discrepancy
    done
  done
done

echo "##### sequential fine sweep"
for n in 250 500 750 1000 1500 2000 3000 4000 6000 8000 12000 16000 24000 32000; do
  for r in 1 2 3; do
    echo "=== n=$n run=$r"
    mpirun -n 1 ./mvm $n | grep time
  done
done

echo "##### accounting for this lab's jobs"
sacct -u sustaita -S 2026-11-09 --format=JobID,JobName%15,Partition,AllocCPUS,Elapsed,State,NodeList -X
echo "done"
