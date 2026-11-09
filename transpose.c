/*
 * Distributed matrix transpose with a 1-D (block row) decomposition.
 *
 * Each of p processes owns b = n/p consecutive rows of the n x n matrix A
 * and ends up owning the same rows of B = A^T.
 *
 *   1. pack:      locally transpose each b x b block of the local rows into
 *                 a contiguous send buffer, ordered by destination process
 *   2. alltoall:  block k of every process goes to process k
 *   3. unpack:    lay the p received b x b blocks side by side as rows of B
 *
 * Usage: mpirun -np p ./transpose n [reps]
 */
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>

static double elem(long i, long j, long n) { return (double)(i * n + j); }

int main(int argc, char *argv[])
{
    int rank, p;
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &p);

    if (argc < 2) {
        if (rank == 0)
            fprintf(stderr, "usage: %s n [reps]\n", argv[0]);
        MPI_Finalize();
        return 1;
    }
    long n = atol(argv[1]);
    int reps = argc > 2 ? atoi(argv[2]) : 5;
    if (n <= 0 || n % p != 0 || reps <= 0) {
        if (rank == 0)
            fprintf(stderr, "n must be positive and divisible by p=%d; reps > 0\n", p);
        MPI_Finalize();
        return 1;
    }

    long b = n / p;
    long local = b * n;
    double *a = malloc(local * sizeof(double));
    double *sbuf = malloc(local * sizeof(double));
    double *rbuf = malloc(local * sizeof(double));
    double *t = malloc(local * sizeof(double));
    if (!a || !sbuf || !rbuf || !t) {
        fprintf(stderr, "rank %d: out of memory for n=%ld\n", rank, n);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    for (long i = 0; i < b; i++)
        for (long j = 0; j < n; j++)
            a[i * n + j] = elem(rank * b + i, j, n);

    /* MPI_Alltoall takes an int count */
    if (local / p > 2147483647L) {
        if (rank == 0)
            fprintf(stderr, "block too large for MPI int count\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    int blk = (int)(b * b);

    double best[4] = {1e30, 1e30, 1e30, 1e30}, sum[4] = {0, 0, 0, 0};
    for (int r = 0; r < reps; r++) {
        MPI_Barrier(MPI_COMM_WORLD);
        double t0 = MPI_Wtime();

        /* sbuf block k holds the transpose of a[:, k*b:(k+1)*b] */
        for (int k = 0; k < p; k++) {
            double *dst = sbuf + (long)k * blk;
            for (long i = 0; i < b; i++)
                for (long j = 0; j < b; j++)
                    dst[j * b + i] = a[i * n + k * b + j];
        }
        double t1 = MPI_Wtime();

        MPI_Alltoall(sbuf, blk, MPI_DOUBLE, rbuf, blk, MPI_DOUBLE, MPI_COMM_WORLD);
        double t2 = MPI_Wtime();

        /* row i of local B is row i of each received block, concatenated */
        for (int k = 0; k < p; k++) {
            double *src = rbuf + (long)k * blk;
            for (long i = 0; i < b; i++)
                for (long j = 0; j < b; j++)
                    t[i * n + k * b + j] = src[i * b + j];
        }
        double t3 = MPI_Wtime();

        /* a rank's phase times only matter as the slowest rank's */
        double mine[4] = {t1 - t0, t2 - t1, t3 - t2, t3 - t0}, mx[4];
        MPI_Reduce(mine, mx, 4, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
        if (rank == 0)
            for (int q = 0; q < 4; q++) {
                sum[q] += mx[q];
                if (mx[q] < best[q])
                    best[q] = mx[q];
            }
    }

    long bad = 0;
    for (long i = 0; i < b; i++)
        for (long j = 0; j < n; j++)
            if (t[i * n + j] != elem(j, rank * b + i, n))
                bad++;
    long totbad;
    MPI_Reduce(&bad, &totbad, 1, MPI_LONG, MPI_SUM, 0, MPI_COMM_WORLD);

    if (rank == 0) {
        printf("n=%ld p=%d reps=%d bytes/rank=%ld %s\n", n, p, reps,
               local * (long)sizeof(double), totbad ? "FAILED" : "correct");
        printf("        %10s %10s %10s %10s\n", "pack", "alltoall", "unpack", "total");
        printf("avg(s)  %10.6f %10.6f %10.6f %10.6f\n",
               sum[0] / reps, sum[1] / reps, sum[2] / reps, sum[3] / reps);
        printf("min(s)  %10.6f %10.6f %10.6f %10.6f\n", best[0], best[1], best[2], best[3]);
        if (n <= 8) {
            printf("B (rank 0 rows):\n");
            for (long i = 0; i < b; i++) {
                for (long j = 0; j < n; j++)
                    printf("%4.0f", t[i * n + j]);
                printf("\n");
            }
        }
    }

    free(a); free(sbuf); free(rbuf); free(t);
    MPI_Finalize();
    return totbad != 0 && rank == 0;
}
