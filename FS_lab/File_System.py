# FAT32 File System Utility

#Eli Perl <eperl@mail.yu.edu, UID 800431807>
#Zechariah Rosenthal <zresont1@mail.yu.edu, UID 800449055>

import sys

#main routine starts here
args = sys.argv

if args[1] != "fat32.img":
    print "Usage: > File_System.py fat32.img" #may want to flesh out usage info
    exit()

else:
    with open(fat32.img, 'rb+') as fs:
        fs_bytes = fs.read()

    pwd = 0 #offset indicating PWD
    
    while(True)
        input = (raw_input(">")).split(" ")
        command = input[0]
        if len(input) > 1:
            args = input[1:]

        if command == "info":
            info()
        elif command == "stat":
            stat(args) #need to error-check for bad input (ie too many args)
        elif command == "size":
            size(args)
        elif command == "cd":
            cd(args)
        elif command == "ls":
            ls(args)
        elif command == "read":
            read_file(args)
        elif command == "volume":
            volume()
        elif command == "mkdir":
            mkdir(args)
        elif command == "rmdir":
            rmdir(args)
        elif command == "quit":
            quit()
        else:
            continue

    
#utility functions begin here
def info():
    ##Description: prints out information about the following fields in both hex and base 10: 
        # BPB_BytesPerSec
        # BPB_SecPerClus 
        # BPB_RsvdSecCnt 
        # BPB_NumFATS
        # BPB_FATSz32

def stat(args):
    ##Description: prints the sizeof the file or directory name, the attributes of the file or
    #  directory name, and the first cluster number of the file or directory name if it is in 
    # the present working directory.  Return an error if FILE_NAME/DIR_NAME does ot exist. (Note: 
    # The size of a directory will always be zero.)
        
def size(args):
    ##Description: prints the size of file FILE_NAME in the present working directory. Log an
    #  error if FILE_NAME does not exist.

def cd(args):
    ##Description: changes the present working directory to DIR_NAME.  Log an error if the directory 
    # does not exist.   DIR_NAME may be “.” (here) and “..” (up one directory).  You don't have to 
    # handle a path longer than one directory.

def ls(args):
    ##Description: lists the contents of DIR_NAME, including “.” and “..”.

def read(args):
    ##Description: reads from a file named FILE_NAME, starting at POSITION, and prints NUM_BYTES.
    # Return an error when trying to read an unopened file.

def volume():
    ##Description: Prints the volume name of the file system image.  If there is a volume name it
    # will be found in the root directory.  If there is no volume name, print “Error: volume name 
    # not found.”

def mkdir(args):
    ##Description: make a new subdirectory in the current directory.  This may require the allocation 
    # of additional space if the current directory has all entries full in all sectors. It is acceptable 
    # for you to only add the subdirectory if there is space to do so without allocating an additional 
    # sector.  If you are unable to create the subdirectory for any reason, you must print an error 
    # message on stderr (fd 2).

def rmdir(args):
    ##Description: delete a subdirectory in the current directory, but only if it is empty!  If you 
    # are unable to delete the subdirectory for any reason, you must print an error message on stderr 
    # (fd 2).  Follow the FAT32 rules for deleting stuff; do not do a full overwrite or zero anything 
    # out!

def quit():
    ##Quit the utility.