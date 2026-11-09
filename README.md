# CS 4475 PA4: Parallel matrix operations with MPI

Gael Sustaita · gsustaita4@miners.utep.edu

The report is **[PA4 Report.pdf](PA4%20Report.pdf)** (Word source: `PA4 Report.docx`).

| Task | Where |
|---|---|
| 1. MPI communication | `mvm.c` (the `MPI_Allgather` at line 26); correctness runs in `results/task1-*.out` |
| 2. Sequential timings | `task2.sbatch`, `results/task2-*.out` |
| 3. Analytical model | report; t_s/t_w measured with `commbench.c` |
| 4. Batch job | `mpi_submit`, output `results/task4-50358720.out` |
| 5. Speedup | report; `figures/task5_speedup.png` |
| Extra credit: transpose | `transpose.c`, `transpose.sbatch`, `results/transpose-50358804.out` |

Supporting experiments: `mvm_timed.c` + `deep.sbatch` (allgather vs compute per rank),
`extras.sbatch` (hardware, ping-pong, scaling to 64), `placement.sbatch` (rank placement).
All runs: Bridges-2 RM / RM-shared, Open MPI 5.0.8, gcc 13.3.1.

`python3 analyze.py` rebuilds `figures/` and `pa4-data.xlsx` from `results/`.

Build and run:

```
make mvm && mpirun -n 4 ./mvm 1024
mpicc -O2 -o transpose transpose.c && mpirun -n 4 ./transpose 8 1
```
