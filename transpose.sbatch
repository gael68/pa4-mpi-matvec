#!/bin/bash
#SBATCH -J pa4-transpose
#SBATCH -p RM-shared
#SBATCH -N 1
#SBATCH --ntasks-per-node=16
#SBATCH -t 00:30:00
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

echo "##### correctness, n=8"
for p in 1 2 4 8; do mpirun -n $p ./transpose 8 1; done
echo "##### reject n not divisible by p"
mpirun -n 4 ./transpose 10 1 || echo "exit status $?"

echo "##### timing, tiled local transpose (default tile 64)"
for p in 1 2 4 8; do
  echo "=== p=$p"
  mpirun -n $p ./transpose $N $REPS
done
echo "##### timing, untiled local transpose"
for p in 1 2 4 8; do
  echo "=== p=$p"
  mpirun -n $p ./transpose $N $REPS 0
done
echo "##### tile size sweep, p=1 and p=8"
for p in 1 8; do
  for t in 8 16 32 64 128 256; do
    mpirun -n $p ./transpose $N 3 $t | sed -n '1p;3p'
  done
done
echo "done"
