#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <sys/time.h>
#include <semaphore.h>
#include <stdarg.h>
#include <netdb.h>
#include <sys/stat.h>
#include <syslog.h>
#include "csapp.h"

#define VERSION 5
#define BUFSIZE 8096
#define ERROR 42
#define LOG 44
#define FORBIDDEN 403
#define NOTFOUND 404

struct
{
	char *ext;
	char *filetype;
} extensions[] = {
	{"gif", "image/gif"},
	{"jpg", "image/jpg"},
	{"jpeg", "image/jpeg"},
	{"png", "image/png"},
	{"ico", "image/ico"},
	{"zip", "image/zip"},
	{"gz", "image/gz"},
	{"tar", "image/tar"},
	{"htm", "text/html"},
	{"html", "text/html"},
	{0, 0}};

static const char *HDRS_FORBIDDEN = "HTTP/1.1 403 Forbidden\nContent-Length: 185\nConnection: close\nContent-Type: text/html\n\n<html><head>\n<title>403 Forbidden</title>\n</head><body>\n<h1>Forbidden</h1>\nThe requested URL, file type or operation is not allowed on this simple static file webserver.\n</body></html>\n";
static const char *HDRS_NOTFOUND = "HTTP/1.1 404 Not Found\nContent-Length: 136\nConnection: close\nContent-Type: text/html\n\n<html><head>\n<title>404 Not Found</title>\n</head><body>\n<h1>Not Found</h1>\nThe requested URL was not found on this server.\n</body></html>\n";
static const char *HDRS_OK = "HTTP/1.1 200 OK\nServer: perlweb/%d.0\nContent-Length: %ld\nConnection: close\nContent-Type: %s\nX-stat-req-arrival-count: %d\nX-stat-req-arrival-time: %ld\nX-stat-req-dispatch-count: %d\nX-stat-req-dispatch-time: %ld\nX-stat-req-complete-count: %d\nX-stat-req-complete-time: %ld\nX-stat-req-age: %d\nX-stat-thread-id: %d\nX-stat-thread-count: %d\nX-stat-thread-html: %d\nX-stat-thread-image: %d\n\n";

/* 
	GLOBALS 
	Declare structs, mutexes, condition vars
*/

typedef struct Job Job;
typedef struct Buffer Buffer;
typedef struct FIFOBuf FIFOBuf;
typedef struct HPBuf HPBuf;
typedef struct ServerStats ServerStats;
typedef struct ThreadStats ThreadStats;

struct ServerStats
{
	long startTime;
	int arrivalCount;
	int dispatchCount;
	int completedCount;
};

struct Job
{
	int socketfd;
	int job_id;
	int arrivalCount;
	int dispatchCount;
	int completedCount;
	long arrivalTime;
	long dispatchTime;
	long completedTime;
	char readBuf[BUFSIZE + 1];
	char contentType;
};

struct ThreadStats
{
	int thread_id;
	int count;
	int hTMLCount;
	int imageCount;
};

struct FIFOBuf
{
	struct Job *jobs; //unitialized job buffer
	int front;
};

struct HPBuf
{
	struct Job *pJobs; //unitialized priority job buffer
	int pFront;
	int pWaiting;

	struct Job *npJobs; //unitialized non-priority job buffer
	int npFront;
	int npWaiting;
};

struct Buffer
{
	int capacity;
	int waiting;
	union {
		FIFOBuf fifoBuf;
		HPBuf hpBuf;
	};
};

static Buffer buf;
static ServerStats stats; /* static = initialised to zeros */
static char *schedAlg;	//default schedAlg -> ANY
pthread_mutex_t bufMutex;
pthread_cond_t prodCond, consCond;
sem_t statMutex;
void web(Job *job, ThreadStats *tStats);
void Gettimeofday(struct timeval *tv);
static int dummy;

/* HELPER FUNCTIONS */

long getServerTime()
{
	struct timeval tv;
	Gettimeofday(&tv); //ERRORCHECK done
	long time_in_mill = (tv.tv_sec) * 1000 + (tv.tv_usec) / 1000;
	P(&statMutex); //ERRORCHECK done
	time_in_mill -= stats.startTime;
	V(&statMutex); //ERRORCHECK done
	return time_in_mill;
}

/* writes info to perlweb.log */
void logger(int type, char *s1, char *s2, int socket_fd)
{
	int fd;
	char logbuffer[BUFSIZE * 2];

	switch (type)
	{
	case ERROR:
		sprintf(logbuffer, "ERROR: %s:%s Errno=%d exiting pid=%d", s1, s2, errno, getpid());
		break;
	case FORBIDDEN:
		dummy = Write(socket_fd, HDRS_FORBIDDEN, 271); //ERRORCHECK done
		sprintf(logbuffer, "FORBIDDEN: %s:%s", s1, s2);
		break;
	case NOTFOUND:
		dummy = Write(socket_fd, HDRS_NOTFOUND, 224); //ERRORCHECK done.
		sprintf(logbuffer, "NOT FOUND: %s:%s", s1, s2);
		break;
	case LOG:
		sprintf(logbuffer, " INFO: %s:%s:%d", s1, s2, socket_fd);
		break;
	}

	if ((fd = open("perlweb.log", O_CREAT | O_WRONLY | O_APPEND, 0644)) >= 0) //ERRORCHECK done. if fails, oh well
	{
		int len = strlen(logbuffer);
		logbuffer[len] = '\n';
		dummy = Write(fd, logbuffer, len + 1); /*Do it in a single thread-safe write*/ //ERRORCHECK done. 
		Close(fd);															   //ERRORCHECK done
	}
}

static void daemonize()
{
    pid_t pid;

    /* Fork off the parent process */
    pid = fork();

    /* An error occurred */
    if (pid < 0)
        exit(EXIT_FAILURE);

    /* Success: Let the parent terminate */
    if (pid > 0)
        exit(EXIT_SUCCESS);

    /* On success: The child process becomes session leader */
    if (setsid() < 0)
        exit(EXIT_FAILURE);

    /* Catch, ignore and handle signals */
    //TODO: Implement a working signal handler */
    if(signal(SIGCHLD, SIG_IGN) == SIG_ERR)
		unix_error("sig_err");
    if(signal(SIGHUP, SIG_IGN) == SIG_ERR)
		unix_error("sig_err");

    /* Fork off for the second time*/
    pid = fork();

    /* An error occurred */
    if (pid < 0)
        exit(EXIT_FAILURE);

    /* Success: Let the parent terminate */
    if (pid > 0)
        exit(EXIT_SUCCESS);

    /* Set new file permissions */
    umask(0);

    /* Change the working directory to the root directory
    or another appropriated directory 
    chdir("/"); */

    /* Close all open file descriptors */
    int x;
    for (x = sysconf(_SC_OPEN_MAX); x>=0; x--)
    {
        close (x);
    }

    /* Open the log file */
    logger(LOG, "daemon", "success", 0);
}


/* BUFFER API */

void initBuf(int size)
{
	buf.capacity = size;
	buf.waiting = 0;

	if (!strcmp(schedAlg, "ANY") || !strcmp(schedAlg, "FIFO"))
	{
		buf.fifoBuf.jobs = (Job *)Calloc(size, sizeof(Job)); //ERRORCHECK done
		buf.fifoBuf.front = 0;
	}
	else if (!strcmp(schedAlg, "HPIC") || !strcmp(schedAlg, "HPHC"))
	{
		buf.hpBuf.pJobs = (Job *)Calloc(size, sizeof(Job));  //ERRORCHECK done
		buf.hpBuf.npJobs = (Job *)Calloc(size, sizeof(Job)); //ERRORCHECK done
		buf.hpBuf.pFront = 0;
		buf.hpBuf.pWaiting = 0;
		buf.hpBuf.npFront = 0;
		buf.hpBuf.npWaiting = 0;
	}
}

int loadBuf(struct Job *newJob)
{
	if (buf.waiting == buf.capacity)
	{
		return -1;
	} //buffer is full

	if (!strcmp(schedAlg, "ANY") || !strcmp(schedAlg, "FIFO"))
	{
		int back = (buf.fifoBuf.front + (buf.waiting++)) % buf.capacity;
		buf.fifoBuf.jobs[back] = *newJob;

		return newJob->job_id;
	}
	else if (!strcmp(schedAlg, "HPIC") || !strcmp(schedAlg, "HPHC"))
	{
		char pContent = schedAlg[2];
		if (newJob->contentType == pContent)
		{
			int back = (buf.hpBuf.pFront + ((buf.hpBuf.pWaiting)++)) % buf.capacity;
			buf.hpBuf.pJobs[back] = *newJob;
		}
		else
		{
			int back = (buf.hpBuf.npFront + (buf.hpBuf.npWaiting)++) % buf.capacity;
			buf.hpBuf.npJobs[back] = *newJob;
		}
		buf.waiting++;

		return newJob->job_id;
	}
	else
		return -1; //should never reach here
}

Job unloadBuf()
{
	Job nextJob;

	if (!strcmp(schedAlg, "ANY") || !strcmp(schedAlg, "FIFO"))
	{
		nextJob = buf.fifoBuf.jobs[buf.fifoBuf.front];
		buf.fifoBuf.front = (buf.fifoBuf.front + 1) % buf.capacity;
	}
	else if (!strcmp(schedAlg, "HPIC") || !strcmp(schedAlg, "HPHC"))
	{
		if (buf.hpBuf.pWaiting != 0) //if there are available high-priority requests
		{
			nextJob = buf.hpBuf.pJobs[buf.hpBuf.pFront];
			buf.hpBuf.pFront = (buf.hpBuf.pFront + 1) % buf.capacity;
			(buf.hpBuf.pWaiting)--;
		}
		else
		{
			nextJob = buf.hpBuf.npJobs[buf.hpBuf.npFront];
			buf.hpBuf.npFront = (buf.hpBuf.npFront + 1) % buf.capacity;
			(buf.hpBuf.npWaiting)--;
		}
	}
	(buf.waiting)--;

	return nextJob;
}

/* WORKER FUNCTIONS */

/* worker thread */
void *worker(void *arg)
{
	int threadID = (int)(long)arg;
	ThreadStats tStats = {threadID, 0, 0, 0};
	while (1)
	{
		Pthread_mutex_lock(&bufMutex);				 //ERRORCHECK done
		while (buf.waiting == 0)					 //if buffer is empty, block
			Pthread_cond_wait(&consCond, &bufMutex); //ERRORCHECK done

		Job nextJob = unloadBuf();

		nextJob.dispatchTime = getServerTime();
		P(&statMutex); //ERRORCHECK done
		stats.dispatchCount++;
		nextJob.dispatchCount = stats.dispatchCount;
		V(&statMutex); //ERRORCHECK done

		Pthread_cond_signal(&prodCond);  //Awaken the master thread - there's room in buf //ERRORCHECK done
		Pthread_mutex_unlock(&bufMutex); //ERRORCHECK done

		switch (nextJob.contentType)
		{
		case 'I':
			tStats.imageCount++;
			break;
		case 'H':
			tStats.hTMLCount++;
			break;
		}
		tStats.count++;

		web(&nextJob, &tStats);
	}
}

/* function to read and log request */
void web(Job *job, ThreadStats *tStats)
{
	int fd = job->socketfd;
	int hit = job->job_id;
	char *buffer = job->readBuf;
	int j, file_fd, buflen;
	long i, ret, len;
	char *fstr;

	logger(LOG, "request", buffer, hit);
	if (strncmp(buffer, "GET ", 4) && strncmp(buffer, "get ", 4))
	{
		logger(FORBIDDEN, "Only simple GET operation supported", buffer, fd);
		goto endRequest;
	}

	for (i = 4; i < BUFSIZE; i++)
	{ /* null terminate after the second space to ignore extra stuff */
		if (buffer[i] == ' ')
		{ /* string is "GET URL " +lots of other stuff */
			buffer[i] = 0;
			break;
		}
	}
	for (j = 0; j < i - 1; j++)
	{ /* check for illegal parent directory use .. */
		if (buffer[j] == '.' && buffer[j + 1] == '.')
		{
			logger(FORBIDDEN, "Parent directory (..) path names not supported", buffer, fd);
			goto endRequest;
		}
	}
	if (!strncmp(&buffer[0], "GET /\0", 6) || !strncmp(&buffer[0], "get /\0", 6))
	{ /* convert no filename to index file */
		strcpy(buffer, "GET /index.html");
	}

	/* work out the file type and check we support it */
	buflen = strlen(buffer);
	fstr = (char *)0;
	for (i = 0; extensions[i].ext != 0; i++)
	{
		len = strlen(extensions[i].ext);
		if (!strncmp(&buffer[buflen - len], extensions[i].ext, len))
		{
			fstr = extensions[i].filetype;
			break;
		}
	}
	if (fstr == 0)
	{
		logger(FORBIDDEN, "file extension type not supported", buffer, fd);
	}
	if ((file_fd = open(&buffer[5], O_RDONLY)) == -1) //ERRORCHECK done in code
	{												  /* open the file for reading */
		logger(NOTFOUND, "failed to open file", &buffer[5], fd);
		goto endRequest;
	}

	job->completedTime = getServerTime();
	P(&statMutex); //ERRORCHECK done
	job->completedCount = stats.completedCount;
	stats.completedCount++; //Change here to prevent multiple requests having the same completedcount
	V(&statMutex);			//ERRORCHECK done

	logger(LOG, "SEND", &buffer[5], hit);
	len = (long)Lseek(file_fd, (off_t)0, SEEK_END); /* lseek to the file end to find the length */ //ERRORCHECK done
	Lseek(file_fd, (off_t)0, SEEK_SET); /* lseek back to the file start ready for reading */	   //ERRORCHECK done
	/* print out the response line, stock headers, and a blank line at the end. */
	int age = job->dispatchCount - job->arrivalCount;
	age = age < 1 ? 0 : age;
	P(&statMutex); //ERRORCHECK done
	sprintf(buffer, HDRS_OK, VERSION, len, fstr, job->arrivalCount, job->arrivalTime, job->dispatchCount, job->dispatchTime, job->completedCount, job->completedTime, age, tStats->thread_id, tStats->count, tStats->hTMLCount, tStats->imageCount);
	V(&statMutex); //ERRORCHECK done

	logger(LOG, "Header", buffer, hit);
	dummy = Write(fd, buffer, strlen(buffer)); //ERRORCHECK done? fd may be volatile, ok to fail

	/* send file in 8KB block - last block may be smaller */
	while ((ret = read(file_fd, buffer, BUFSIZE)) > 0) //ERRORCHECK done?
	{
		dummy = Write(fd, buffer, ret); //ERRORCHECK done? fd may be volatile, ok to fail
	}

	Close(file_fd); /*FIXED MEM LEAK*/ //ERRORCHECK done
endRequest:
	Sleep(1);  /* allow socket to drain before signalling the socket is closed */
	Close(fd); //ERRORCHECK done
}

/* MASTER THREAD FUNCTIONS*/

/* determine content type, store readBuf */
void parseJob(Job *newJob)
{
	//process fd to determine content type
	char contentType;
	memset(newJob->readBuf, 0, BUFSIZE + 1);
	long ret, i;
	ret = read(newJob->socketfd, newJob->readBuf, BUFSIZE); /* read Web request in one go */ //ERRORCHECK done

	if (ret == 0 || ret == -1)
	{ /* read failure stop now */
		logger(FORBIDDEN, "failed to read browser request", "", newJob->socketfd);
		//end request
		Sleep(1); /* allow socket to drain before signalling the socket is closed */ //ERRORCHECK done
		Close(newJob->socketfd);													 //ERRORCHECK done
		return;
	}
	if (ret > 0 && ret < BUFSIZE)
	{							  /* return code is valid chars */
		newJob->readBuf[ret] = 0; /* terminate the buffer */
	}
	else
	{
		newJob->readBuf[0] = 0;
	}
	for (i = 0; i < ret; i++)
	{ /* remove CF and LF characters */
		if (newJob->readBuf[i] == '\r' || newJob->readBuf[i] == '\n')
		{
			newJob->readBuf[i] = '*';
		}
	}

	if (strstr(newJob->readBuf, ".gif") != NULL ||
		strstr(newJob->readBuf, ".jpg") != NULL ||
		strstr(newJob->readBuf, ".jpeg") != NULL ||
		strstr(newJob->readBuf, ".png") != NULL ||
		strstr(newJob->readBuf, ".ico") != NULL ||
		strstr(newJob->readBuf, ".zip") != NULL ||
		strstr(newJob->readBuf, ".gz") != NULL ||
		strstr(newJob->readBuf, ".tar") != NULL)
	{
		contentType = 'I';
	}
	else if (strstr(newJob->readBuf, ".htm") != NULL || strstr(newJob->readBuf, ".html") != NULL)
	{
		contentType = 'H';
	}
	else
	{
		contentType = 'E';
	}
	newJob->contentType = contentType;
}

/* called by master thread to add job  to buffer*/
void addJob(Job *newJob)
{
	parseJob(newJob);

	Pthread_mutex_lock(&bufMutex);				 //ERRORCHECK done
	while (buf.waiting == buf.capacity)			 //if buffer is full, block
		Pthread_cond_wait(&prodCond, &bufMutex); //ERRORCHECK done

	//had to move inside buf lock - job was consumed before arrival count was updated
	P(&statMutex); //ERRORCHECK done
	stats.arrivalCount++;
	newJob->arrivalCount = stats.arrivalCount;
	V(&statMutex); //ERRORCHECK done

	if (loadBuf(newJob) == -1)
	{
		//mutex unlocked when buffer was full
		printf("ERROR: master thread attempted to access full buffer");
		exit(6);
	}

	Pthread_cond_broadcast(&consCond); //Awaken all workers, can't hurt//ERRORCHECK done
	Pthread_mutex_unlock(&bufMutex);   //ERRORCHECK done
}

/* master thread */
int main(int argc, char **argv)
{
	int i, port, listenfd, socketfd, hit;
	socklen_t length;
	static struct sockaddr_in cli_addr;  /* static = initialised to zeros */
	static struct sockaddr_in serv_addr; /* static = initialised to zeros */

	if (argc < 6 || argc > 7 || !strcmp(argv[1], "-?"))
	{
		printf("USAGE: %s <port-number> <top-directory> <threads> <buffers> <schedalg> -d\t\tversion %d\n\n"
					 "\tnweb is a small and very safe mini web server\n"
					 "\tnweb only servers out file/web pages with extensions named below\n"
					 "\t and only from the named directory or its sub-directories.\n"
					 "\tProvides multi-threaded functionality, based on user-determined\n"
					 "\t thread count, job queue size, and scheduling algorithm.\n"
					 "\t Optional -d argument runs server as a daemon process.\n"
					 "\tExample: perlweb 8181 /home/nwebdir 10 8 FIFO &\n\n"
					 "\tOnly Supports \"ANY\", \"FIFO\" (First In First Out), \"HPIC\"\n"
					 "\t (High Priority Image Content), and \"HPHC\" (High Priority HTML Content)\n"
					 "\t scheduling policies.\n"
					 "\tOnly Supports:",
					 argv[0], VERSION);
		for (i = 0; extensions[i].ext != 0; i++)
			printf(" %s", extensions[i].ext);

		printf("\n\tNot Supported: URLs including \"..\", Java, Javascript, CGI\n"
			   "\tNot Supported: directories / /etc /bin /lib /tmp /usr /dev /sbin \n"
			   "\tNo warranty given or implied\n\tZechariah Rosenthal and Eli Perl zrosent1@mail.yu.edu\n");
		exit(0);
	}
	if (!strncmp(argv[2], "/", 2) || !strncmp(argv[2], "/etc", 5) ||
		!strncmp(argv[2], "/bin", 5) || !strncmp(argv[2], "/lib", 5) ||
		!strncmp(argv[2], "/tmp", 5) || !strncmp(argv[2], "/usr", 5) ||
		!strncmp(argv[2], "/dev", 5) || !strncmp(argv[2], "/sbin", 6))
	{
		printf("ERROR: Bad top directory %s, see perlweb -?\n", argv[2]);
		exit(3);
	}
	if (chdir(argv[2]) == -1) //ERRORCHECK done
	{
		printf("ERROR: Can't Change to directory %s\n", argv[2]);
		exit(4);
	}
	if (atoi(argv[3]) < 1)
	{
		printf("ERROR: Number of worker threads must be > 1 %s\n", argv[3]);
		exit(4);
	}
	if (atoi(argv[4]) < 1)
	{
		printf("ERROR: buffer must be > 1 %s\n", argv[4]);
		exit(5);
	}

	if (argc == 7 && !strcmp(argv[6], "-d"))
	{
		daemonize();
	}
	
	logger(LOG, "perlweb starting", argv[1], getpid());
	
	/* setup the network socket */
	if ((listenfd = socket(AF_INET, SOCK_STREAM, 0)) < 0) //ERRORCHECK done
	{
		logger(ERROR, "system call", "socket", 0);
		exit(1);
	}
	port = atoi(argv[1]);
	if (port < 1025 || port > 65000)
	{
		logger(ERROR, "Invalid port number (try 1025->65000)", argv[1], 0);
		exit(1);
	}
	serv_addr.sin_family = AF_INET;
	serv_addr.sin_addr.s_addr = htonl(INADDR_ANY);
	serv_addr.sin_port = htons(port);
	if (bind(listenfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) //ERRORCHECK done
	{
		logger(ERROR, "system call", "bind", 0);
		exit(1);
	}
	if (listen(listenfd, 64) < 0) //ERRORCHECK done
	{
		logger(ERROR, "system call", "listen", 0);
		exit(1);
	}

	/* Set schedAlg */
	if (strcmp(argv[5], "ANY") && strcmp(argv[5], "FIFO") && strcmp(argv[5], "HPIC") && strcmp(argv[5], "HPHC"))
	{
		printf("ERROR: schedAlg must be one of \"ANY\", \"FIFO\", \"HPIC\", \"HPHC\", entered %s\n", argv[4]);
		exit(1);
	}
	else
	{
		schedAlg = argv[5];
	}

	//Avoid broken Pipes
	if(signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
		unix_error("Fixin pipes error");
	}

	/* Initialize Buffer */
	int bufferSize = atoi(argv[4]);
	initBuf(bufferSize);

	/*Initialize pThread stuff, stats struct*/
	Sem_init(&statMutex, 0, 1); //ERRORCHECK done
	stats.arrivalCount = 0;
	stats.completedCount = 0;
	stats.dispatchCount = 0;
	stats.startTime = getServerTime();

	Pthread_mutex_init(&bufMutex, NULL); //ERRORCHECK done
	Pthread_cond_init(&prodCond, NULL);  //ERRORCHECK done
	Pthread_cond_init(&consCond, NULL);  //ERRORCHECK done
	int numThreads = atoi(argv[3]);
	pthread_t threads[numThreads];
	for (long i = 1; i <= numThreads; i++)
	{
		Pthread_create(&threads[i], NULL, worker, (void *)i); //ERRORCHECK done
	}

	/* Master Thread Loop*/
	for (hit = 1;; hit++)
	{
		length = sizeof(cli_addr);
		if ((socketfd = accept(listenfd, (struct sockaddr *)&cli_addr, &length)) < 0) //ERRORCHECK done
		{
			logger(ERROR, "system call", "accept", 0);
			continue; //don't add a bad job
		}
		long arrivalTime = getServerTime();
		Job newJob = {socketfd, hit, 0, 0, 0, arrivalTime};
		addJob(&newJob);
	}
}

/**************************** 
 * Error-handling functions *
 ****************************/

void unix_error(char *msg) /* Unix-style error */
{
	logger(ERROR, msg, strerror(errno), 0);
	exit(0);
}

void posix_error(int code, char *msg) /* Posix-style error */
{
	logger(ERROR, msg, strerror(code), 0);
	exit(0);
}

/**********************************
 * Wrappers for assorted Unix functions  *
 **********************************/

unsigned int Sleep(unsigned int secs)
{
	unsigned int rc;

	if ((rc = sleep(secs)) < 0)
		unix_error("Sleep error");
	return rc;
}

void *Calloc(size_t nmemb, size_t size)
{
	void *p;

	if ((p = calloc(nmemb, size)) == NULL)
		unix_error("Calloc error");
	return p;
}

void Gettimeofday(struct timeval *tv)
{
	int rc;
	if ((rc = gettimeofday(tv, NULL)) < 0)
		unix_error("Gettimeofday error");
}

/**********************************
 * Wrappers for Unix I/O routines *
 **********************************/

int Open(const char *pathname, int flags, mode_t mode)
{
	int rc;

	if ((rc = open(pathname, flags, mode)) < 0)
		logger(ERROR, "Open Error", strerror(errno), 0);
	return rc;
}

ssize_t Read(int fd, void *buf, size_t count)
{
	ssize_t rc;

	if ((rc = read(fd, buf, count)) < 0)
		unix_error("Read error");
	return rc;
}

ssize_t Write(int fd, const void *buf, size_t count)
{
	ssize_t rc;

	if ((rc = write(fd, buf, count)) < 0)
		logger(ERROR, "Write Error", strerror(errno), 0);
	return rc;
}

off_t Lseek(int fildes, off_t offset, int whence)
{
	off_t rc;

	if ((rc = lseek(fildes, offset, whence)) < 0)
		logger(ERROR, "Lseek Error", strerror(errno), 0);
	return rc;
}

void Close(int fd)
{
	int rc;

	if ((rc = close(fd)) < 0)
		logger(ERROR, "Close Error", strerror(errno), 0);
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
 * Wrappers for Posix Mutexes *
 *********************************/
void Pthread_mutex_init(pthread_mutex_t *mutex,
						const pthread_mutexattr_t *mutexattr)
{
	int rc;
	if ((rc = pthread_mutex_init(mutex, mutexattr)) != 0)
		posix_error(rc, "Pthread_mutex_init error");
}

void Pthread_mutex_lock(pthread_mutex_t *mutex)
{
	int rc;
	if ((rc = pthread_mutex_lock(mutex)) != 0)
		posix_error(rc, "Pthread_mutex_lock error");
}

void Pthread_mutex_unlock(pthread_mutex_t *mutex)
{
	int rc;
	if ((rc = pthread_mutex_unlock(mutex)) != 0)
		posix_error(rc, "Pthread_mutex_unlock error");
}

/*********************************
 * Wrappers for Posix Condition Variables *
 *********************************/

void Pthread_cond_init(pthread_cond_t *cond,
					   const pthread_condattr_t *cond_attr)
{
	int rc;
	if ((rc = pthread_cond_init(cond, cond_attr)) != 0)
		posix_error(rc, "Pthread_cond_init error");
}

void Pthread_cond_wait(pthread_cond_t *cond, pthread_mutex_t *mutex)
{
	int rc;
	if ((rc = pthread_cond_wait(cond, mutex)) != 0)
		posix_error(rc, "Pthread_cond_wait error");
}

void Pthread_cond_signal(pthread_cond_t *cond)
{
	int rc;
	if ((rc = pthread_cond_signal(cond)) != 0)
		posix_error(rc, "Pthread_cond_signal error");
}

void Pthread_cond_broadcast(pthread_cond_t *cond)
{
	int rc;
	if ((rc = pthread_cond_broadcast(cond)) != 0)
		posix_error(rc, "Pthread_cond_broadcast error");
}