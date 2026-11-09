/*
 * Measures the communication parameters used by the analytical models.
 *
 *   pingpong:  ranks 0 and 1 bounce m doubles; half the round trip is the
 *              one-way time t_s + t_w * m
 *   allgather: the exact MPI_Allgather mvm.c does for a given n
 *
 * Usage: mpirun -n p ./commbench [n]      (p >= 2 for pingpong)
 */
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>

static int iters_for(long bytes) { return bytes < (1 << 16) ? 1000 : bytes < (1 << 22) ? 100 : 10; }

int main(int argc, char *argv[])
{
    int rank, p;
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &p);
    long n = argc > 1 ? atol(argv[1]) : 32000;
    if (n <= 0 || n % p != 0) {
        if (rank == 0)
            fprintf(stderr, "n must be positive and divisible by p=%d\n", p);
        MPI_Finalize();
        return 1;
    }

    long maxm = 1L << 22;
    double *buf = malloc(maxm * sizeof(double));
    if (!buf)
        MPI_Abort(MPI_COMM_WORLD, 1);
    for (long i = 0; i < maxm; i++)
        buf[i] = i;

    if (p >= 2) {
        if (rank == 0)
            printf("pingpong words bytes one_way_us\n");
        for (long m = 1; m <= maxm; m *= 4) {
            int it = iters_for(m * 8);
            MPI_Barrier(MPI_COMM_WORLD);
            double t0 = MPI_Wtime();
            for (int k = 0; k < it; k++) {
                if (rank == 0) {
                    MPI_Send(buf, (int)m, MPI_DOUBLE, 1, 0, MPI_COMM_WORLD);
                    MPI_Recv(buf, (int)m, MPI_DOUBLE, 1, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
                } else if (rank == 1) {
                    MPI_Recv(buf, (int)m, MPI_DOUBLE, 0, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
                    MPI_Send(buf, (int)m, MPI_DOUBLE, 0, 0, MPI_COMM_WORLD);
                }
            }
            double dt = (MPI_Wtime() - t0) / it / 2;
            if (rank == 0)
                printf("pingpong %ld %ld %.3f\n", m, m * 8, dt * 1e6);
        }
    }

    long nl = n / p;
    double *xbuf = malloc(n * sizeof(double));
    int it = 200;
    MPI_Barrier(MPI_COMM_WORLD);
    double t0 = MPI_Wtime();
    for (int k = 0; k < it; k++)
        MPI_Allgather(buf, (int)nl, MPI_DOUBLE, xbuf, (int)nl, MPI_DOUBLE, MPI_COMM_WORLD);
    double ag = (MPI_Wtime() - t0) / it, agmax;
    MPI_Reduce(&ag, &agmax, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
    if (rank == 0)
        printf("allgather n=%ld p=%d us=%.3f\n", n, p, agmax * 1e6);

    free(xbuf);
    free(buf);
    MPI_Finalize();
    return 0;
}
