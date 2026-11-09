#!/bin/bash
#SBATCH -J pa4-task1
#SBATCH -p RM-shared
#SBATCH -N 1
#SBATCH --ntasks-per-node=16
#SBATCH -t 00:15:00
#SBATCH -o task1-%j.out

# Correctness runs. The driver checks y against a sequential product on
# rank 0 and prints one "discrepancy" line per wrong element.
source ./common.sh
for n in 8 32 1024 32000; do
  for np in 1 2 4 8; do
    echo "=== n=$n np=$np"
    mpirun -n $np ./mvm $n > run.tmp
    echo "discrepancies: $(grep -c discrepancy run.tmp || true)"
    grep -v discrepancy run.tmp
  done
done
rm -f run.tmp
