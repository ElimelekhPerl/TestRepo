PROGRAMMING ASSIGNMENT 2: WEB SERVERS AND SYNCHRONIZATION

March 13, 2020

Eli Perl <eperl@mail.yu.edu 800431807>
Zechariah Rosenthal <zrosent1@mail.yu.edu 800449055>

DIVISION OF LABOR:
    E. PERL: developed and implemented algs for server and client scheduling 
        policies, implemented and debugged stat-tracking tools, refactored for clarity, 
        developed tests for project functionality, deployed tests, authored write-up.
    
    Z. ROSENTHAL: engineered and implemented multi-threaded capability for server and client design, 
        implemented and debugged stat-tracking tools, built in error catches for all system calls, 
        integrated daemon function into server code, developed tests for project functionality.

DESIGN OVERVIEW:
    Multi-threaded client and server capable of fetching/retrieving html and image content.

    SERVER:
        Thread mechanics modeled as a fixed-size thread pool. Main serves as the master thread,
        parsing command-line args for server specs. After establishing a connection with the client,
        infinite loop continues to query the client for get requests, storing each incoming job in the
        globally accessible buffer struct. As jobs arrive in the buffer, the initialized worker
        threads awaken to process them. Job-flow order determined by the user-determined scheduling
        alg (ANY, FIFO, HPIC, or HPHC).
        All scheduling decisions are delegated to the buffer structure and the load/unload API.
        As such, there is no visible difference in processing within the worker thread between different
        scheduling algs. 
        Global statistics struct updated throughout server runtime. Per-request and per-thread stats
        updated throughout processing and outputted as part of request header logged by the server.

    CLIENT:
        Thread mechanics modeled as a fixed-size thread pool. Main serves as the master thread,
        parsing command-line args for client specs. Chosen scheduling algorithm (between CONCUR and FIFO) 
        determines worker function version. Once the worker threads are dispatched, each thread enters an  
        infinite loop to establish connection and query server with GET request. 

ADDITIONAL SPECIFICATIONS:
    Clarification for implementation of ambiguous requirements.

    SCHEDULING POLICIES:
        ANY - obeys FIFO behavior.
        FIFO - buffer designed as array-based queue.
        HPIC/HPHC - buffer modeled as two FIFO buffers, one for high-priority content, one for non-priority
            content. 
    
    SYNCHRONIZATION TOOLS:
        SERVER WORKER THREAD SHARED BUFFER ACCESS - pthread mutex + condition variables.
        SERVER WORKER THREAD SHARED STATS ACCESS - pthread semaphore lock.
        CLIENT WORKER THREAD 'CONCUR' POLICY - pthread barrier.
        CLIENT WORKER THREAD 'FIFO' POLICY - pthread semaphore lock for sequential GET requests, pthread barrier
            for concurrent response reception.

    STATISTICS:
        TIME - getServerTime() function subtracts current system time (gettimeofday()) from server start time.
        REQ-AGE - dispatch count minus arrival count (ie number of jobs that arrived later, dispatched earlier),
            0 if negative (given priority).

    ERROR HANDLING:
        SYSTEM CALLS - all system calls are diverted through the CSAPP wrapper functions and return value is
            checked. In a few cases (read, etc) exceptional return values are handled in the context of normal 
            control flow so as not to interrupt normal program behavior.
        SIGPIPE - killing a client (CTRL-C) may interrupt a server read/write call, but the resulting SIGPIPE is
            supressed to prevent the server from crashing. 

KNOWN BUGS:
    -When running on the class server, cannot exceed ~50 total threads between client and server.
    -FIFO client unexpectedly more efficient than CONCUR client when running ~150 threads.

TESTING:
    Each of the following scenarios tests a particular feature of the project, with specific parameters aimed to 
    confirm expected behavior.
    Assume consistent [portnum], [folder], and [host] across server and client.

    SECTION         FEATURE         SERVER ARGS     CLIENT1 ARGS    CLIENT2 ARGS    BEHAVIOR/OUTPUT
    
    Part 1:
    Multi-Threaded  Working thread  10 100 ANY      10 CONCUR       n/a             Unique thread-id's 1-10
    Server          pool                            /index.html                     correspond to server's 10 threads.
    
                    Effective prod- 10 100 ANY      1 CONCUR        n/a             Server doesn't hang (ie no infinite
                    cons sharing                    /index.html                     waits in mutual-exclusion scenarios).
    Part 2:
    Scheduling      ANY             10 100 ANY      50 CONCUR       n/a             Server is operational.
    Policies                                        /index.html
           
                    FIFO            10 100 FIFO     50 CONCUR       50 FIFO         Despite influx of requests from
                                                    /index.html     /zubat.jpg      alternating html requests from client1
                                                    /test.html                      and jpg requests from client2, all requests
                                                                                    have identical arrival and dispatch counts
                                                                                    (ie are dispatched in the order they arrive,
                                                                                    a la FIFO).

                    HPIC            1 100 HPIC      10 CONCUR       10 CONCUR       Despite identical thread allocation to
                                                    /index.html     /zubat.jpg      both clients, thread-stats have a dramatically
                                                                                    higher image count than html count, image 
                                                                                    requests all have an age of zero, and html 
                                                                                    requests have a positive age (ie image requests
                                                                                    given priority to the point of html starvation).
                    
                    HPHC            1 100 HPHC      10 CONCUR       10 CONCUR       Despite identical thread allocation to
                                                    /index.html     /zubat.jpg      both clients, thread-stats have a dramatically
                                                                                    higher html count than image count, html 
                                                                                    requests all have an age of zero, and image 
                                                                                    requests have a positive age (ie html requests
                                                                                    given priority to the point of image starvation).
    Part 3: 
    Usage           req-stats       1 10 ANY        1 CONCUR        n/a             For vanilla single-threaded server and client,         
    Statistics      (basic)                         /index.html                     stats are consistent and accurate.
    

                    req-stats       15 500 ANY      50 CONCUR       n/a             For full-throttled mulit-threaded server and client, 
                    (advanced)                      /index.html                     stats are consistent and accurate.

                    thread-stats    10 100 ANY      50 CONCUR       n/a             For image requests, individual thread stats
                    (image)                         /zubat.jpg                      reflect steadily incrementing total and image
                                                                                    request counts.
                    
                    thread-stats    10 100 ANY      50 CONCUR       n/a             For html requests, individual thread stats
                    (html)                          /index.html                     reflect steadily incrementing total and html
                                                                                    request counts.
                    
                    thread-stats    10 100 ANY      50 CONCUR       n/a             Individual thread stats reflect steadily
                                                    /index.html                     incrementing total request counts. Alternating
                                                    /zubat.jpg                      request types reflected by alternating increments
                                                                                    for html and image counts.
    Part 4:
    Multi-Threaded  Working thread  50 500 ANY      10 CONCUR       n/a             Each thread batch consistently sends and receives          
    Client          pool                            /index.html                     10 requests of alternating file type.
                                                    /zubat.jpg

                    CONCUR          5 500 ANY       100 CONCUR      n/a             Difference in arrival time between the first
                                                    /index.html                     and last requests of a given batch much narrower
                                                    /zubat.jpg                      than FIFO, as requests are being handled 
                                                                                    concurrently. (Run on local machine to accomodate
                                                                                    larger thread count necessary to observe discrepancy).

                    FIFO            5 500 ANY       100 FIFO        n/a             Difference in arrival time between the first
                                                    /index.html                     and last requests of a given batch much broader
                                                    /zubat.jpg                      than CONCUR, as requests are being handled 
                                                                                    sequentially. (Run on local machine to accomodate
                                                                                    larger thread count necessary to observe discrepancy).
    Part 5:
    Daemonize       Effectively     10 100 ANY      50 CONCUR       n/a             Server is operational. Terminal shows no server process 
    the Server      spawn daemon                    /index.html                     when prompted with the <ps> command, but when prompted with
                    process                                                         <ps -xj> shows server process with TTY: ? .
                    