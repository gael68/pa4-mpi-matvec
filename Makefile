CC = mpicc
CFLAGS = -O2

%.o: %.c
	$(CC) -c $^ $(CFLAGS)

mvm: mvm.o mvm-driver.o
	$(CC) -o $@ $^ $(CFLAGS)
