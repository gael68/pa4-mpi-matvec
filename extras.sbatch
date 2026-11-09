#!/bin/bash
#SBATCH -J pa4-extras
#SBATCH -p RM
#SBATCH -N 1
#SBATCH --ntasks-per-node=128
#SBATCH -t 00:45:00
#SBATCH -o extras-%j.out

# Supporting measurements on an exclusive node: hardware, t_s/t_w,
# process placement, and scaling past p=8.
cd "$SLURM_SUBMIT_DIR"
export HOSTNAME=${HOSTNAME:-$(hostname -s)}
module load openmpi
echo "host: $(hostname)  job: $SLURM_JOB_ID  date: $(date)"

echo "##### hardware"
lscpu | grep -E "Model name|Socket|Core|Thread|NUMA|L1d|L2|L3|MHz"
numactl -H | grep -E "available|size|distances" -A0
free -g | head -2

mpicc -O2 -o commbench commbench.c
mpicc -O2 -o transpose transpose.c

echo "##### pingpong, same socket (cores 0,1)"
mpirun -n 2 --map-by core --bind-to core ./commbench 32000
echo "##### pingpong, different sockets"
mpirun -n 2 --map-by package --bind-to core ./commbench 32000

echo "##### allgather for mvm, n=32000"
for np in 2 4 8 16 32 64; do
  mpirun -n $np --bind-to core ./commbench 32000 | grep allgather
done

echo "##### mvm n=32000, default placement, p up to 64"
for np in 1 2 4 8 16 32 64; do
  for r in 1 2 3; do
    echo "=== np=$np run=$r"
    mpirun -n $np ./mvm 32000 | grep -v discrepancy
  done
done

echo "##### mvm n=32000, placement: pack on one socket vs spread across sockets"
for map in core package numa; do
  for np in 2 4 8; do
    for r in 1 2 3; do
      echo "=== map=$map np=$np run=$r"
      mpirun -n $np --map-by $map --bind-to core ./mvm 32000 | grep time
    done
  done
done

echo "##### transpose n=32000 (8 GB per matrix)"
for np in 1 2 4 8 16 32 64; do
  echo "=== p=$np"
  mpirun -n $np ./transpose 32000 3
done
echo "##### transpose n=16000, placement spread across sockets"
for np in 2 4 8; do
  echo "=== map=numa p=$np"
  mpirun -n $np --map-by numa --bind-to core ./transpose 16000 5
done
echo "done"
