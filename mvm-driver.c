/* test driver program for 1D matrix-vector multiplication */
#include "mpi.h"
#include <stdio.h>
#include <stdlib.h>

extern void MatrixVectorMultiply(int n, double *a, double *x, double *y, MPI_Comm comm);

int main (int argc, char *argv[])
{
int   numtasks, taskid;
int i, j, N, n, nlocal;
double *a, *x, *y, *ycheck, *alocal, *xlocal, *ylocal;
int proc;
double start, end;

MPI_Init(&argc, &argv);
MPI_Comm_size(MPI_COMM_WORLD, &numtasks);
MPI_Comm_rank(MPI_COMM_WORLD,&taskid);

if (argc != 2) {
   if (taskid == 0) {
     fprintf(stderr, "Usage: %s <n>\n", argv[0]);
     fprintf(stderr, "where n is a multiple of the number of tasks.\n");
   }
   MPI_Finalize();
   exit(0);
}

/* Read row/column dimension from command line */
n = atoi(argv[1]);

N=n*n; //size of matrix n x n
nlocal = n/numtasks;

if (taskid == 0) {
  a = (double *) malloc(N*sizeof(double));
  x = (double *) malloc(n*sizeof(double));
  y = (double *) malloc(n*sizeof(double));
  ycheck = (double *) malloc(n*sizeof(double));

  /* Initialize a and x */
  for (i = 0;i < n;i++) {
    for (j = 0;j < n; j++)
      a[i*n +j] = 2*i+j;
    x[i] = i;
  }
}

    alocal = (double *) malloc(n*nlocal*sizeof(double));
    xlocal = (double *) malloc(nlocal*sizeof(double));
    ylocal = (double *) malloc(nlocal*sizeof(double));

    /* Distribute a and x in 1D row distribution */
    /*********************************************/
    MPI_Scatter(a,n*nlocal,MPI_DOUBLE,alocal,n*nlocal,MPI_DOUBLE,0,MPI_COMM_WORLD);
    MPI_Scatter(x,nlocal,MPI_DOUBLE,xlocal,nlocal,MPI_DOUBLE,0,MPI_COMM_WORLD);
    /*********************************************/

    /* Each process calls MatrixVectorMultiply */

    start = MPI_Wtime();
    MatrixVectorMultiply(n, alocal, xlocal, ylocal, MPI_COMM_WORLD);
    end = MPI_Wtime();

    /* Gather results back to root process */
    /***************************************/
    MPI_Gather(ylocal, nlocal, MPI_DOUBLE,y, nlocal, MPI_DOUBLE,0,MPI_COMM_WORLD);
    /***************************************/

    /* Check results */

    if (taskid == 0) {
      for (i = 0; i<n; i++) {
         ycheck[i] = 0;
         for (j=0; j<n; j++)
            ycheck[i] += a[i*n+j]*x[j];
         if (ycheck[i] != y[i])
            printf("discrepancy: ycheck[%d]=%f, y[%d]=%f\n", i, ycheck[i], i, y[i]);
      }
      printf("Done with mvm, y[%d] = %f\n", n-1, y[n-1]);
      printf("Parallel matrix vector multiplication time: %f sec\n", end-start);
    }

    MPI_Finalize();

}
