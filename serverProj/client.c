/* Generic */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <semaphore.h>
#include "csapp.h" //contains headers for error wrapper functions


/* Network */
#include <netdb.h>
#include <sys/socket.h>

#define BUF_SIZE 250

/* Globals */
pthread_barrier_t bar;
sem_t mutex;
int twoFiles;

/* NETWORK API */

// Get host information (used to establishConnection)
struct addrinfo *getHostInfo(char *host, char *port)
{
  int r;
  struct addrinfo hints, *getaddrinfo_res;
  // Setup hints
  memset(&hints, 0, sizeof(hints));
  hints.ai_family = AF_INET;
  hints.ai_socktype = SOCK_STREAM;
  if ((r = getaddrinfo(host, port, &hints, &getaddrinfo_res))) //ERRORCHECK done
  {
    fprintf(stderr, "[getHostInfo:21:getaddrinfo] %s\n", gai_strerror(r));
    return NULL;
  }

  return getaddrinfo_res;
}

// Establish connection with host
int establishConnection(struct addrinfo *info)
{
  if (info == NULL)
    return -1;

  int clientfd;
  for (; info != NULL; info = info->ai_next)
  {
    if ((clientfd = socket(info->ai_family,
                           info->ai_socktype,
                           info->ai_protocol)) < 0) //ERRORCHECK done
    {
      perror("[establishConnection:35:socket]");
      continue;
    }

    if (connect(clientfd, info->ai_addr, info->ai_addrlen) < 0) //ERRORCHECK done
    {
      Close(clientfd); //ERRORCHECK done
      perror("[establishConnection:42:connect]");
      continue;
    }

    freeaddrinfo(info);
    return clientfd;
  }

  freeaddrinfo(info);
  return -1;
}

// Send GET request
void GET(int clientfd, char *path)
{
  char req[1000] = {0};
  sprintf(req, "GET %s HTTP/1.0\r\n\r\n", path);
  Send(clientfd, req, strlen(req), 0); //ERRORCHECK done
}

/* WORKER THREAD FUNCTIONS */

//worker function called for CONCUR groups
void *runCONCUR(void *arg)
{
  char **argv = (char **)arg;
  int clientfd;
  char buf[BUF_SIZE];
  char *file;
  int file1 = 1;

  while (1)
  {
    if (twoFiles)
    {
      if (file1)
      {
        file = argv[5];
      }
      else
      {
        file = argv[6];
      }
      file1 = !file1;
    }
    else
    {
      file = argv[5];
    }

    // Establish connection with <hostname>:<port>
    clientfd = establishConnection(getHostInfo(argv[1], argv[2]));
    if (clientfd == -1)
    {
      fprintf(stderr,
              "[main:73] Failed to connect to: %s:%s%s \n",
              argv[1], argv[2], file);
      return (void *)3;
    }
    pthread_barrier_wait(&bar); //wait until all threads have connected to server //ERRORCHECK done

    GET(clientfd, file);
    pthread_barrier_wait(&bar); //wait until all threads have sent request //ERRORCHECK done

    while (recv(clientfd, buf, BUF_SIZE, 0) > 0) //ERRORCHECK done
    {
      fputs(buf, stdout);
      memset(buf, 0, BUF_SIZE);
    }
    pthread_barrier_wait(&bar); //wait until all threads have received requests //ERRORCHECK done
    Close(clientfd);            //ERRORCHECK done
  }
}

//worker function called for FIFO groups
void *runFIFO(void *arg)
{
  char **argv = (char **)arg;
  int clientfd;
  char buf[BUF_SIZE];
  char *file;
  int file1 = 1;

  while (1)
  {
    if (twoFiles)
    {
      if (file1)
      {
        file = argv[5];
      }
      else
      {
        file = argv[6];
      }
      file1 = !file1;
    }
    else
    {
      file = argv[5];
    }

    P(&mutex); //lock mutex ahead of connection establishment to ensure FIFO behavior //ERRORCHECK done

    // Establish connection with <hostname>:<port>
    clientfd = establishConnection(getHostInfo(argv[1], argv[2]));
    if (clientfd == -1)
    {
      fprintf(stderr,
              "[main:73] Failed to connect to: %s:%s%s \n",
              argv[1], argv[2], file);
      return (void *)3;
    }

    GET(clientfd, file);
    V(&mutex); //unlock mutex, allow next request //ERRORCHECK done

    while (recv(clientfd, buf, BUF_SIZE, 0) > 0) //ERRORCHECK done
    {                                            //wait to receive concurrently
      fputs(buf, stdout);
      memset(buf, 0, BUF_SIZE);
    }
    pthread_barrier_wait(&bar); //wait until all threads have received requests - ruins FIFO //ERRORCHECK done
    Close(clientfd);            //ERRORCHECK done
  }
}

/* MASTER THREAD */

int main(int argc, char **argv)
{

  /*Validate args*/
  if (!(argc == 6 || argc == 7))
  {
    fprintf(stderr, "USAGE: %s <hostname> <port> <threads> <schedalg> <filename1> [filename2]\n", argv[0]);
    return 1;
  }
  if (atoi(argv[3]) < 1)
  {
    printf("ERROR: Number of threads must be > 1 %s\n", argv[3]);
    exit(4);
  }
  if (!strncmp(argv[4], "CONCUR", 7) && !strncmp(argv[4], "FIFO", 5))
  {
    printf("ERROR: Scheduling must be CONCUR or FIFO: %s\n", argv[4]);
    exit(5);
  }
  if (argc == 7)
  {
    twoFiles = 1;
  }
  else
  {
    twoFiles = 0;
  }

  int numThreads = atoi(argv[3]);
  pthread_t threads[numThreads];
  Pthread_barrier_init(&bar, NULL, numThreads); //ERRORCHECK done

  if (!strcmp(argv[4], "FIFO"))
  {
    Sem_init(&mutex, 0, 1); //ERRORCHECK done

    for (size_t i = 0; i < numThreads; i++)
    {
      Pthread_create(&threads[i], NULL, runFIFO, (void *)argv); //ERRORCHECK done
    }
  }
  else
  {
    for (size_t i = 0; i < numThreads; i++)
    {
      Pthread_create(&threads[i], NULL, runCONCUR, (void *)argv); //ERRORCHECK done
    }
  }

  for (size_t i = 0; i < numThreads; i++)
  {
    Pthread_join(threads[i], NULL); //ERRORCHECK done
  }

  return 0;
}

/**************************** 
 * Error-handling functions *
 ****************************/

void unix_error(char *msg) /* Unix-style error */
{
  fprintf(stderr, "%s: %s\n", msg, strerror(errno));
  exit(0);
}

void posix_error(int code, char *msg) /* Posix-style error */
{
  fprintf(stderr, "%s: %s\n", msg, strerror(code));
  exit(0);
}

/**********************************
 * Wrappers for Unix I/O routines *
 **********************************/
void Close(int fd)
{
  int rc;

  if ((rc = close(fd)) < 0)
    unix_error("Close error");
}

void Send(int fd, const void *buf, size_t n, int flags)
{
  int rc;
  if ((rc = send(fd, buf, n, flags)) < 0)
    unix_error("send error");
}

/**************************************************
 * Wrappers for Pthreads thread control functions *
 **************************************************/

void Pthread_create(pthread_t *tidp, pthread_attr_t *attrp,
                    void *(*routine)(void *), void *argp)
{
  int rc;
  if ((rc = pthread_create(tidp, attrp, routine, argp)) != 0)
    posix_error(rc, "Pthread_create error");
}

void Pthread_join (pthread_t th, void **thread_return)
{
  int rc;
  if ((rc = pthread_join(th, thread_return)) != 0)
    posix_error(rc, "Pthread_join error");
}

/*********************************
 * Wrappers for Posix semaphores *
 *********************************/

void Sem_init(sem_t *sem, int pshared, unsigned int value)
{
  if (sem_init(sem, pshared, value) < 0)
    unix_error("Sem_init error");
}

void P(sem_t *sem)
{
  if (sem_wait(sem) < 0)
    unix_error("P error");
}

void V(sem_t *sem)
{
  if (sem_post(sem) < 0)
    unix_error("V error");
}

/*********************************
 * Wrappers for Posix Barriers *
 *********************************/

void Pthread_barrier_init(pthread_barrier_t *barrier,
                          const pthread_barrierattr_t *attr, unsigned count)
{
  int rc;
  if ((rc = pthread_barrier_init(barrier,attr,count)) != 0)
    posix_error(rc, "Pthread_barrier_init error");
}
/* Causing errors for unknown reasons
void Pthread_barrier_wait(pthread_barrier_t *barrier)
{
  int rc;
  if ((rc = pthread_barrier_wait(barrier)) == -1)
    posix_error(rc, "Pthread_barrier_wait error");
}
*/