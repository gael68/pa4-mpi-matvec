/* mvm.c with the allgather and the local product timed separately on every
 * rank. Same algorithm; used only to measure the two terms of the model.
 * Build: mpicc -O2 -o mvm-timed mvm_timed.c mvm-driver.c
 */
#include <mpi.h>
#include <stdlib.h>
#include <stdio.h>

void MatrixVectorMultiply(int n, double *a, double *x, double *y, MPI_Comm comm)
{
    int i, j;
    int nlocal;
    double *xbuf;
    int npes, myrank;

    MPI_Comm_size(comm, &npes);
    MPI_Comm_rank(comm, &myrank);

    xbuf = (double *) malloc(n*sizeof(double));
    nlocal = n/npes;

    double t0 = MPI_Wtime();
    MPI_Allgather(x, nlocal, MPI_DOUBLE, xbuf, nlocal, MPI_DOUBLE, comm);
    double t1 = MPI_Wtime();

    for (i=0; i<nlocal; i++) {
      y[i] = 0;
      for (j=0; j<n; j++)
         y[i] += a[i*n+j]*xbuf[j];
    }
    double t2 = MPI_Wtime();

    double mine[2] = {t1 - t0, t2 - t1};
    double *all = myrank == 0 ? malloc(2 * npes * sizeof(double)) : NULL;
    MPI_Gather(mine, 2, MPI_DOUBLE, all, 2, MPI_DOUBLE, 0, comm);
    if (myrank == 0) {
      for (int r = 0; r < npes; r++)
        printf("rank %d allgather_s %.6f compute_s %.6f GBps %.2f\n", r,
               all[2*r], all[2*r+1], 8.0 * nlocal * n / all[2*r+1] / 1e9);
      free(all);
    }
    free(xbuf);
}
