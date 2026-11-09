#!/bin/bash
#SBATCH -J pa4-task2
#SBATCH -p RM-shared
#SBATCH -N 1
#SBATCH --ntasks-per-node=16
#SBATCH -t 00:15:00
#SBATCH -o task2-%j.out

# Sequential timings: one task, increasing n, several runs each.
source ./common.sh
RUNS=${RUNS:-5}
for n in 1000 2000 4000 8000 16000 32000; do
  for r in $(seq 1 $RUNS); do
    echo "=== n=$n run=$r"
    mpirun -n 1 ./mvm $n
  done
done
