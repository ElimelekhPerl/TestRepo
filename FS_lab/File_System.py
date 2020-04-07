# FAT32 File System Utility

# Eli Perl <eperl@mail.yu.edu, UID 800431807>
# Zechariah Rosenthal <zresont1@mail.yu.edu, UID 800449055>

import sys
import os

# helper functions


def read_bytes(fd, start, end):  # [start, end)
    fd.seek(start)
    byte_string = fd.read(end - start)
    return byte_string

# utility functions


class FileSystem:
    def __init__(self, img_file):
        self.fs_file = open(img_file, 'rb+')  # You may NOT reuse kernel file system code

        self.b_p_sec = int.from_bytes(read_bytes(self.fs_file, 11, 13), 'little')
        self.sec_p_clus = int.from_bytes(read_bytes(self.fs_file, 13, 14), 'little')
        self.rsec_count = int.from_bytes(read_bytes(self.fs_file, 14, 16), 'little')
        self.num_fats = int.from_bytes(read_bytes(self.fs_file, 16, 17), 'little')
        self.sec_p_fat = int.from_bytes(read_bytes(self.fs_file, 36, 40), 'little')
        # self.data_offset = 90 + self.rsec_count + (self.num_fats * self.sec_p_fat * 32)
        # self.root_dir = self.data_offset
        # cluster num of root dir * b_p_sec * sec_p_clus = byte offset of root dir
        # self.pwd = self.root_dir  # set init pwd to root

    def info(self):
        fields = ["BPB_BytesPerSec", "BPB_SecPerClus", "BPB_RsvdSecCnt", "BPB_NumFATS", "BPB_FATSz32"]

        print("info:   field              hex       dec")
        print('        %s %7s %8d' % (fields[0].ljust(15), hex(self.b_p_sec), self.b_p_sec))
        print('        %s %7s %8d' % (fields[1].ljust(15), hex(self.sec_p_clus), self.sec_p_clus))
        print('        %s %7s %8d' % (fields[2].ljust(15), hex(self.rsec_count), self.rsec_count))
        print('        %s %7s %8d' % (fields[3].ljust(15), hex(self.num_fats), self.num_fats))
        print('        %s %7s %8d' % (fields[4].ljust(15), hex(self.sec_p_fat), self.sec_p_fat))

    def stat(self, param):
        """
        Description: prints the sizeof the file or directory name, the attributes of the file or
        directory name, and the first cluster number of the file or directory name if it is in
        the present working directory.  Return an error if FILE_NAME/DIR_NAME does ot exist. (Note:
        The size of a directory will always be zero.)
         """

    def size(self, param):
        """
        Description: prints the size of file FILE_NAME in the present working directory. Log an
        error if FILE_NAME does not exist.
        """

    def cd(self, param):
        """
        Description: changes the present working directory to DIR_NAME.  Log an error if the directory
        does not exist.   DIR_NAME may be “.” (here) and “..” (up one directory).  You don't have to
        handle a path longer than one directory.
        """

    def ls(self, param):
        """
        Description: lists the contents of DIR_NAME, including “.” and “..”.
        """

    def read_file(self, param):
        """
        Description: reads from a file named FILE_NAME, starting at POSITION, and prints NUM_BYTES.
        Return an error when trying to read an unopened file.
        """

    def volume(self):
        """
        Description: Prints the volume name of the file system image.  If there is a volume name it
        will be found in the root directory.  If there is no volume name, print “Error: volume name
        not found.”
        """

    def mkdir(self, param):
        """
        Description: make a new subdirectory in the current directory.  This may require the allocation
        of additional space if the current directory has all entries full in all sectors. It is acceptable
        for you to only add the subdirectory if there is space to do so without allocating an additional
        sector.  If you are unable to create the subdirectory for any reason, you must print an error
        message on stderr (fd 2).
        """

    def rmdir(self, param):
        """
        Description: delete a subdirectory in the current directory, but only if it is empty!  If you
        are unable to delete the subdirectory for any reason, you must print an error message on stderr
        (fd 2).  Follow the FAT32 rules for deleting stuff; do not do a full overwrite or zero anything
        out!
        """


# main routine


argv = sys.argv

if argv[1] != "fat32.img":
    print("Usage: > File_System.py fat32.img")  # may want to flesh out usage info
    exit()

else:
    fs = FileSystem("fat32.img")

    while True:
        full_command = (input("> ")).split(" ")
        command = full_command[0]
        if len(full_command) > 1:
            arg_list = full_command[1:]

        if command == "info":
            fs.info()
        elif command == "stat":
            fs.stat(arg_list)  # need to error-check for bad input (ie too many args)
        elif command == "size":
            fs.size(arg_list)
        elif command == "cd":
            fs.cd(arg_list)
        elif command == "ls":
            fs.ls(arg_list)
        elif command == "read":
            fs.read_file(arg_list)
        elif command == "volume":
            fs.volume()
        elif command == "mkdir":
            fs.mkdir(arg_list)
        elif command == "rmdir":
            fs.rmdir(arg_list)
        elif command == "quit":
            break
        else:
            continue
    fs.fs_file.close()
    sys.exit()


