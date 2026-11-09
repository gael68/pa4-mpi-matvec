#!/bin/bash
#SBATCH -J pa4-transpose
#SBATCH -p RM-shared
#SBATCH -N 1
#SBATCH --ntasks-per-node=16
#SBATCH -t 00:20:00
#SBATCH -o transpose-%j.out

# n=16000 is 2 GB per full matrix; p=1 holds four (A, send, recv, B) = 8 GB.
N=${N:-16000}
REPS=${REPS:-5}

cd "$SLURM_SUBMIT_DIR"
export HOSTNAME=${HOSTNAME:-$(hostname -s)}
module load openmpi
set -e
echo "host: $(hostname)  job: $SLURM_JOB_ID  date: $(date)"
mpicc -O2 -o transpose transpose.c

echo "=== correctness, n=8"
for p in 1 2 4 8; do mpirun -n $p ./transpose 8 1; done
echo "=== reject n not divisible by p"
mpirun -n 4 ./transpose 10 1 || echo "exit status $?"
for p in 1 2 4 8; do
  echo "=== p=$p"
  mpirun -n $p ./transpose $N $REPS
done
