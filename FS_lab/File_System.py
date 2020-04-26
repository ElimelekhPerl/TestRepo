# FAT32 File System Utility

# Eli Perl <eperl@mail.yu.edu, UID 800431807>
# Zechariah Rosenthal <zrosent1@mail.yu.edu, UID 800449055>

import sys


class FileSystem:

    # helper functions

    def read_bytes(self, start, end):  # [start, end)
        """ 
        Returns literal byte_string from [start, end). 
        @Param start, end: the absolute byte offset within the img 
        """
        
        self.fs_file.seek(start)
        byte_string = self.fs_file.read(end - start)
        return byte_string

    def clus_to_offset(self, clus_num):
        """ 
        Returns absolute byte offset in img given cluster number. 
        @Param clus_num: the cluster number within the img 
        """
        
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

    def dir_contents(self, cur_clus):  
        """ 
        returns dictionary of files:info for DIR. 
        @Param cur_clus: the cluster number of DIR 
        """
        
        cur_offset = self.clus_to_offset(cur_clus)
        contents = dict()

        while int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 0:  # haven't reached end of dir marker
            attr = int.from_bytes(self.read_bytes(cur_offset + 11, cur_offset + 12), 'little')
            if attr != 15:  # short name entry
                if int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 229:  # not a free entry
                    attr = self.parse_attr(attr)  # use helper func to return ATTR string corresponding to attr number
                    
                    name = (self.read_bytes(cur_offset, cur_offset + 8).decode()).strip()  # decode name with utf-8 from bytes, strip whitespace
                    if attr == "ATTR_DIRECTORY":
                        full_name = name
                    else:
                        ext = (self.read_bytes(cur_offset + 8, cur_offset + 11).decode()).strip()  # ditto for ext
                        full_name = name + "." + ext  # if file, concat name, period, and ext for full name

                    hi_clus_bytes = int.from_bytes(self.read_bytes(cur_offset + 20, cur_offset + 22), 'little')
                    lo_clus_bytes = int.from_bytes(self.read_bytes(cur_offset + 26, cur_offset + 28), 'little')
                    clus_num = (hi_clus_bytes << 16) + lo_clus_bytes  # concatenate hi and lo words for starting clus_num of file

                    if attr == "ATTR_DIRECTORY":
                        size = 0
                    else:
                        size = int.from_bytes(self.read_bytes(cur_offset + 28, cur_offset + 32), 'little')

                    contents[str(full_name)] = {'attr': attr, 'clus_num': clus_num, 'size': size}  # add dictionary entry to contents, with file name as key, list of meta-data as value

            cur_offset = cur_offset + 32  # advance to next dir entry
            if cur_offset == self.clus_to_offset(cur_clus) + (self.sec_p_clus * self.b_p_sec):  # reached end of current cluster, check FAT
                FAT_offset = (self.rsec_count * self.b_p_sec) + (cur_clus * 4)  # reserved sectors + preceding FAT entries
                FAT_entry = int.from_bytes(self.read_bytes(FAT_offset, FAT_offset + 4), 'little')
                if FAT_entry != self.eoc_marker:  # dir continues into another cluster
                    cur_clus = FAT_entry
                    cur_offset = self.clus_to_offset(cur_clus)  # set offset to beginning of next data cluster
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
        self.root_clus = int.from_bytes(self.read_bytes(44, 48), 'little')
        self.root_dir = self.clus_to_offset(self.root_clus)
        self.pwd_clus = self.root_clus
        self.pwd_offset = self.root_dir  # set init pwd to root
        self.pwd_name = "i_am_root"

    # utility functions

    def info(self):
        """ 
        Prints out information about the following fields in both hex and base 10: 
        BPB_BytesPerSec, BPB_SecPerClus, BPB_RsvdSecCnt, BPB_NumFATS, BPB_FATSz32 
        """
        
        fields = ["BPB_BytesPerSec", "BPB_SecPerClus", "BPB_RsvdSecCnt", "BPB_NumFATS", "BPB_FATSz32"]

        print("info:   field              hex       dec")
        print('        %s %7s %8d' % (fields[0].ljust(15), hex(self.b_p_sec), self.b_p_sec))
        print('        %s %7s %8d' % (fields[1].ljust(15), hex(self.sec_p_clus), self.sec_p_clus))
        print('        %s %7s %8d' % (fields[2].ljust(15), hex(self.rsec_count), self.rsec_count))
        print('        %s %7s %8d' % (fields[3].ljust(15), hex(self.num_fats), self.num_fats))
        print('        %s %7s %8d' % (fields[4].ljust(15), hex(self.sec_p_fat), self.sec_p_fat))

    def stat(self, param):
        """ 
        Prints the sizeof the file or directory name, the attributes of the file or directory name, 
        and the first cluster number of the file or directory name if it is in the present working directory. 
        Return an error if FILE_NAME/DIR_NAME does not exist. (Note: The size of a directory will always be zero.) 
        """
        
        file_name = param[0]
        if file_name == "":  
            print("Usage: stat [FILE_NAME/DIR_NAME]")
            return
        
        contents = self.dir_contents(self.pwd_clus)
        if file_name in contents:
            print("size: " + str(contents[file_name]["size"]))
            print("attr: " + str(contents[file_name]["attr"]))
            print("starting cluster: " + str(contents[file_name]["clus_num"]))

        else:
            print(str(file_name) + " not found")

    def size(self, param):
        """
        Prints the size of file FILE_NAME in the present working directory. Log an
        error if FILE_NAME does not exist.
        """

        file_name = param[0]
        if file_name == "":
            print("Usage: size [FILE_NAME/DIR_NAME]")
            return
        
        contents = self.dir_contents(self.pwd_clus)
        if file_name in contents:
            print("size: " + str(contents[file_name]["size"]))

        else:
            print(str(file_name) + " not found")

    def cd(self, param):
        """
        Changes the present working directory to DIR_NAME.  Log an error if the directory
        does not exist.   DIR_NAME may be “.” (here) and “..” (up one directory).  You don't have to
        handle a path longer than one directory.
        """

    def ls(self, param):
        """ 
        Lists the contents of DIR_NAME, including “.” and “..”
        @Param param: valid DIR_NAME within PWD 
        """
        
        dir_name = param[0]
        contents = []

        if dir_name == "":
            dir_name = "."
        
        if dir_name == ".":  # root has no . dir, so this is only way to list its own contents
            for file_name in self.dir_contents(self.pwd_clus):
                contents.append(str(file_name))
        else:
            pwd_contents = self.dir_contents(self.pwd_clus)
            if dir_name in pwd_contents:
                for file_name in self.dir_contents(pwd_contents[dir_name]["clus_num"]):
                    contents.append(str(file_name))
            else:
                contents.append("dir " + str(dir_name) + " not found")

        contents.sort()
        for string in contents:
            print(string)

    def read_file(self, param):
        """
        Reads from a file named FILE_NAME, starting at POSITION, and prints NUM_BYTES.
        """
        
        file_name = param[0]
        if file_name == "":
            print("Usage: read [FILE_NAME] <Start_Position> <Num_Bytes>")
            return
        
        contents = self.dir_contents(self.pwd_clus)
        if file_name in contents:
            cur_clus = contents[file_name]["clus_num"]
            size = contents[file_name]["size"]
            clus_size = self.b_p_sec * self.sec_p_clus
            output = ""

            if size <= clus_size:  # only takes up one cluster
                cur_offset = self.clus_to_offset(cur_clus)
                output = self.read_bytes(cur_offset, cur_offset + size).decode()
            else:
                full_secs = size // clus_size
                partial_sec_size = size % clus_size

                for i in range(0, full_secs):
                    cur_offset = self.clus_to_offset(cur_clus)
                    output = output + self.read_bytes(cur_offset, cur_offset + clus_size).decode()
                    FAT_offset = (self.rsec_count * self.b_p_sec) + (cur_clus * 4)  # reserved sectors + preceding FAT entries
                    cur_clus = int.from_bytes(self.read_bytes(FAT_offset, FAT_offset + 4), 'little')
                
                if partial_sec_size != 0:
                    cur_offset = self.clus_to_offset(cur_clus)
                    output = output + self.read_bytes(cur_offset, cur_offset + partial_sec_size).decode()
                
            print(output)
            print("NUM_BYTES: " + str(size))

        else:
            print(str(file_name) + " not found")

    def volume(self):
        """
        Prints the volume name of the file system image.  If there is a volume name it
        will be found in the root directory.  If there is no volume name, print “Error: volume name
        not found.”
        """

    def mkdir(self, param):
        """
        Make a new subdirectory in the current directory.  This may require the allocation
        of additional space if the current directory has all entries full in all sectors. It is acceptable
        for you to only add the subdirectory if there is space to do so without allocating an additional
        sector.  If you are unable to create the subdirectory for any reason, you must print an error
        message on stderr (fd 2).
        """

    def rmdir(self, param):
        """
        Delete a subdirectory in the current directory, but only if it is empty!  If you
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
            arg_list = [arg.upper() for arg in full_command[1:]]
        else:
            arg_list = [""]

        if command == "info":
            fs.info()
        elif command == "stat":
            fs.stat(arg_list)
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
