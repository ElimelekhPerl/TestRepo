# FAT32 File System Utility

# Eli Perl <eperl@mail.yu.edu, UID 800431807>
# Zechariah Rosenthal <zresont1@mail.yu.edu, UID 800449055>

import sys


class FileSystem:

    # helper functions

    def read_bytes(self, start, end):  # [start, end)
        self.fs_file.seek(start)
        byte_string = self.fs_file.read(end - start)
        return byte_string

    def clus_to_offset(self, clus_num):
        data_offset = ((clus_num - 2) * self.sec_p_clus * self. b_p_sec)  # negate clus_num off-by-2, multiply in sec_p_clus and b_p_sec
        return data_offset + self.pre_data_offset  # return absolute offset by adding size of meta-data (boot + FATs) to offset within data

    def parse_attr(self, attr):
        if attr == 1:
            return "ATTR_READ_ONLY"
        elif attr == 2:
            return "ATTR_HIDDEN"
        elif attr == 4:
            return "ATTR_SYSTEM"
        elif attr == 8:
            return "ATTR_VOLUME_ID"
        elif attr == 16:
            return "ATTR_DIRECTORY"
        elif attr == 32:
            return "ATTR_ARCHIVE"

    def dir_contents(self, dir_offset):  # returns dictionary of files:info for PWD
        cur_offset = dir_offset  # change to offset of subsequent clus_num according to FAT if necessary
        contents = dict()

        while int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 0:  # haven't reached end of dir marker
            attr = int.from_bytes(self.read_bytes(cur_offset + 11, cur_offset + 12), 'little')
            if attr != 15:  # short name entry
                if int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 229:  # not a free entry
                    attr = self.parse_attr(attr)  # use helper func to return ATTR string corresponding to attr number
                    
                    name = (self.read_bytes(cur_offset, cur_offset + 8).decode()).strip()  # decode name with utf-8 from bytes, strip whitespace
                    if attr == "ATTR_DIRECTORY":
                        full_name = name + "/"  # if dir, concat '/'
                    else:
                        ext = (self.read_bytes(cur_offset + 8, cur_offset + 11).decode()).strip()  # ditto for ext
                        full_name = name + "." + ext  # if file, concat name, period, and ext for full name

                    hi_clus_bytes = int.from_bytes(self.read_bytes(cur_offset + 20, cur_offset + 22), 'little')
                    lo_clus_bytes = int.from_bytes(self.read_bytes(cur_offset + 26, cur_offset + 28), 'little')
                    clus_num = (hi_clus_bytes << 16) + lo_clus_bytes  # concatenate hi and lo words for starting clus_num of file

                    if attr == "ATTR_DIRECTORY":
                        size = 0
                    else:
                        size = int.from_bytes(self.read_bytes(28, 32), 'little')

                    contents[str(full_name)] = {'attr': attr, 'clus_num': clus_num, 'size': size}  # add dictionary entry to contents, with file name as key, list of meta-data as value

            cur_offset = cur_offset + 32  # advance to next dir entry
            if cur_offset == self.pwd_offset + (self.sec_p_clus + self.b_p_sec):  # reached end of current cluster, check FAT
                FAT_offset = (self.rsec_count * self.b_p_sec()) + (self.pwd_clus * 4)  # reserved sectors + preceding FAT entries
                FAT_entry = int.from_bytes(self.read_bytes(FAT_offset, FAT_offset + 4), 'little')
                if FAT_entry != self.eoc_marker:  # dir continues into another cluster
                    cur_offset == self.clus_to_offset(FAT_entry)  # set offset to beginning of next data cluster
                else:  # eoc reached
                    break

        return contents

    # constructor

    def __init__(self, img_file):
        self.fs_file = open(img_file, 'rb+')

        self.b_p_sec = int.from_bytes(self.read_bytes(11, 13), 'little')
        self.sec_p_clus = int.from_bytes(self.read_bytes(13, 14), 'little')
        self.rsec_count = int.from_bytes(self.read_bytes(14, 16), 'little')
        self.num_fats = int.from_bytes(self.read_bytes(16, 17), 'little')
        self.sec_p_fat = int.from_bytes(self.read_bytes(36, 40), 'little')
        self.eoc_marker = int.from_bytes(self.read_bytes(self.rsec_count * self.b_p_sec + 4, self.rsec_count * self.b_p_sec + 8), 'little')
        self.pre_data_offset = (self.rsec_count * self.b_p_sec) + (self.num_fats * self.sec_p_fat * self.b_p_sec)  # reserved sectors + FATs
        self.root_dir = self.clus_to_offset(int.from_bytes(self.read_bytes(44, 48), 'little'))
        self.pwd_name = "i_am_root"
        self.pwd_offset = self.root_dir  # set init pwd to root
        self.pwd_clus = int.from_bytes(self.read_bytes(44, 48), 'little')

    # utility functions

    def info(self):
        fields = ["BPB_BytesPerSec", "BPB_SecPerClus", "BPB_RsvdSecCnt", "BPB_NumFATS", "BPB_FATSz32"]

        print("info:   field              hex       dec")
        print('        %s %7s %8d' % (fields[0].ljust(15), hex(self.b_p_sec), self.b_p_sec))
        print('        %s %7s %8d' % (fields[1].ljust(15), hex(self.sec_p_clus), self.sec_p_clus))
        print('        %s %7s %8d' % (fields[2].ljust(15), hex(self.rsec_count), self.rsec_count))
        print('        %s %7s %8d' % (fields[3].ljust(15), hex(self.num_fats), self.num_fats))
        print('        %s %7s %8d' % (fields[4].ljust(15), hex(self.sec_p_fat), self.sec_p_fat))

    def stat(self, param):
        file_name = param[0]
        contents = self.dir_contents(self.pwd_offset)

        if file_name in contents:
            print("size: " + str(contents[file_name]["size"]))
            print("attr: " + str(contents[file_name]["attr"]))
            print("starting cluster: " + str(contents[file_name]["clus_num"]))

        else:
            print(str(file_name) + " not found")

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
        dir_name = param[0]
        if str(dir_name) == "root" and self.pwd_name == "i_am_root":  # root has no . dir, so this is only way to list its own contents
            for file in self.dir_contents(self.pwd_offset):
                print(str(file))
        else:
            pwd_contents = self.dir_contents(self.pwd_offset)
            if repr(param) in pwd_contents:
                for file in self.dir_contents(self.clus_to_offset(pwd_contents[repr(dir_name)]["clus_num"])):
                    print(str(file))
            else:
                print("dir " + str(dir_name) + " not found")

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
        full_command = (input(str(fs.pwd_name) + "/ > ")).split(" ")
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
    sys.exit(0)
