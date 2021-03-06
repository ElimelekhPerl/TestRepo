# FAT32 File System Utility

# Eli Perl <eperl@mail.yu.edu, UID 800431807>
# Zechariah Rosenthal <zrosent1@mail.yu.edu, UID 800449055>

import sys


class FileSystem:

    # helper functions

    def clus_to_offset(self, clus_num):
        """
        Returns absolute byte offset in img given cluster number.
        @Param clus_num: the cluster number within the img
        """

        data_offset = ((clus_num - 2) * self.b_p_clus)  # negate clus_num off-by-2, multiply in sec_p_clus and b_p_sec
        return data_offset + self.pre_data_offset  # return absolute offset by adding size of meta-data (boot + FATs) to offset within data

    def cache_clus(self, clus_num):
        start = self.clus_to_offset(clus_num)
        self.fs_file.seek(start)
        self.cached_clus_data = self.fs_file.read(self.b_p_clus)
        self.cached_clus_num = clus_num

    def read_bytes(self, start, end):  # [start, end)
        """
        Returns literal byte_string from [start, end).
        @Param start, end: the absolute byte offset within the img
        """
        current_clus = ((start - self.pre_data_offset) // self.b_p_clus) + 2
        if current_clus != self.cached_clus_num:
            self.cache_clus(current_clus)
        offset = self.clus_to_offset(current_clus)

        return self.cached_clus_data[(start - offset):(end - offset)]

    def write_bytes(self, start, buf):
        """
        Overwrites FS with literal buf from [start...start+len(buf)
        Returns true if successfully wrote all of buf
        @Param start the absolute byte offset within the img
        @Param buf the bytes to write, in byte-like-object form
        """
        self.fs_file.seek(start)
        status = self.fs_file.write(buf) == len(buf)

        if start > self.pre_data_offset:
            current_clus = ((start - self.pre_data_offset) // self.b_p_clus) + 2  # get current clus num
            self.cache_clus(current_clus)  # reload current clus in cache

        else:
            self.fs_file.seek(self.rsec_count * self.b_p_sec)  # jump to FAT table
            self.FAT = self.fs_file.read(self.sec_p_fat * self.b_p_sec)  # refresh FAT table

        return status

    def parse_attr(self, attr):
        result = []
        if attr & 1:
            result.append("ATTR_READ_ONLY")
        if attr & 2:
            result.append("ATTR_HIDDEN")
        if attr & 4:
            result.append("ATTR_SYSTEM")
        if attr & 8:
            result.append("ATTR_VOLUME_ID")
        if attr & 16:
            result.append("ATTR_DIRECTORY")
        if attr & 32:
            result.append("ATTR_ARCHIVE")
        if result == []:
            result.append("NONE")
        return result

    def dir_contents(self, cur_clus):
        """
        returns dictionary of files:info for DIR.
        @Param cur_clus: the cluster number of DIR
        """
        if cur_clus == 0:
            cur_clus = 2

        cur_offset = self.clus_to_offset(cur_clus)
        contents = dict()

        while int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 0:  # haven't reached end of dir marker
            attr = int.from_bytes(self.read_bytes(cur_offset + 11, cur_offset + 12), 'little')
            if attr != 15:  # short name entry
                if int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 229:  # not a free entry
                    attr = self.parse_attr(attr)  # use helper func to return ATTR list corresponding to attr number

                    name = (self.read_bytes(cur_offset, cur_offset + 8).decode()).strip()  # decode name with utf-8 from bytes, strip whitespace
                    if "ATTR_DIRECTORY" in attr:
                        full_name = name
                    else:
                        ext = (self.read_bytes(cur_offset + 8, cur_offset + 11).decode()).strip()  # ditto for ext
                        if ext != "":
                            full_name = name + "." + ext  # if file, concat name, period, and ext for full name
                        else:
                            full_name = name

                    hi_clus_bytes = int.from_bytes(self.read_bytes(cur_offset + 20, cur_offset + 22), 'little')
                    lo_clus_bytes = int.from_bytes(self.read_bytes(cur_offset + 26, cur_offset + 28), 'little')
                    clus_num = (hi_clus_bytes << 16) + lo_clus_bytes  # concatenate hi and lo words for starting clus_num of file

                    if "ATTR_DIRECTORY" in attr:
                        size = 0
                    else:
                        size = int.from_bytes(self.read_bytes(cur_offset + 28, cur_offset + 32), 'little')

                    contents[str(full_name)] = {'attr': attr, 'clus_num': clus_num, 'size': size}  # add dictionary entry to contents, with file name as key, list of meta-data as value

            cur_offset = cur_offset + 32  # advance to next dir entry
            if cur_offset == self.clus_to_offset(cur_clus) + self.b_p_clus:  # reached end of current cluster, check FAT
                FAT_offset = cur_clus * 4  # preceding FAT entries
                FAT_entry = int.from_bytes(self.FAT[FAT_offset: FAT_offset + 4], 'little')
                if FAT_entry != self.eoc_marker:  # dir continues into another cluster
                    cur_clus = FAT_entry
                    cur_offset = self.clus_to_offset(cur_clus)  # set offset to beginning of next data cluster
                else:  # eoc reached
                    break

        return contents

    # constructor

    def __init__(self, img_file):
        self.fs_file = open(img_file, 'r+b')

        self.fs_file.seek(11)
        self.b_p_sec = int.from_bytes(self.fs_file.read(2), 'little')  # 11-13
        self.sec_p_clus = int.from_bytes(self.fs_file.read(1), 'little')  # 13-14
        self.b_p_clus = self.b_p_sec * self.sec_p_clus
        self.rsec_count = int.from_bytes(self.fs_file.read(2), 'little')  # 14-16
        self.num_fats = int.from_bytes(self.fs_file.read(1), 'little')  # 16-17
        self.fs_file.seek(36)  # jump to 36
        self.sec_p_fat = int.from_bytes(self.fs_file.read(4), 'little')  # 36-40
        self.pre_data_offset = (self.rsec_count * self.b_p_sec) + (self.num_fats * self.sec_p_fat * self.b_p_sec)  # reserved sectors + FATs
        self.fs_file.seek(44)  # jump to 44
        self.root_clus = int.from_bytes(self.fs_file.read(4), 'little')  # 44-48
        self.pwd_clus = self.root_clus
        self.pwd_name = "i_am_root"
        self.fs_file.seek(self.rsec_count * self.b_p_sec)  # jump to FAT table
        self.FAT = self.fs_file.read(self.sec_p_fat * self.b_p_sec)  # read FAT table
        self.eoc_marker_bytes = self.FAT[4:8]
        self.eoc_marker = int.from_bytes(self.eoc_marker_bytes, 'little') 

        self.cached_clus_data = 0  # data from most recently accessed cluster
        self.cached_clus_num = 0  # clus_num of cached data
        self.cache_clus(self.root_clus)  # cache root clus
   
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
            print("attr: " + ', '.join(contents[file_name]["attr"]))
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
        dir_name = param[0]
        if dir_name == "":
            print("Usage: cd [DIR_NAME]")
            return
        contents = self.dir_contents(self.pwd_clus)
        if dir_name in contents and ("ATTR_DIRECTORY" in contents[dir_name]["attr"]):
            self.pwd_clus = contents[dir_name]["clus_num"]
            if self.pwd_clus == 0:
                self.pwd_clus = self.root_clus
            if dir_name != ".":
                if dir_name == "..":
                    self.pwd_name = self.pwd_name[:self.pwd_name.rfind("/")]
                else:
                    self.pwd_name = self.pwd_name + "/" + dir_name
        else:
            print("dir " + dir_name + " not found")

    def ls(self, param):
        """
        Lists the contents of DIR_NAME, including “.” and “..”
        @Param param: valid DIR_NAME within PWD
        """

        dir_name = param[0]
        contents = []

        if dir_name == "":
            dir_name = "."

        pwd_contents = self.dir_contents(self.pwd_clus)
        if dir_name == ".":  # root has no . dir, so this is only way to list its own contents
            for file_name in pwd_contents:
                if("ATTR_HIDDEN" not in pwd_contents[file_name]['attr'] and "ATTR_VOLUME_ID" not in pwd_contents[file_name]['attr']):
                    contents.append(str(file_name))
        else:
            if dir_name in pwd_contents and ("ATTR_DIRECTORY" in pwd_contents[dir_name]["attr"]):
                subdir_contents = self.dir_contents(pwd_contents[dir_name]["clus_num"])
                for file_name in subdir_contents:
                    if("ATTR_HIDDEN" not in subdir_contents[file_name]['attr'] and "ATTR_VOLUME_ID" not in subdir_contents[file_name]['attr']):
                        contents.append(str(file_name))
            else:
                contents.append("dir " + str(dir_name) + " not found")

        contents.sort()
        print('   '.join(contents))

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
            if len(param) == 1:
                offset = 0
                size = contents[file_name]["size"]
            elif len(param) == 3:
                offset = int(param[1])
                if int(param[2]) + offset <= contents[file_name]["size"]:
                    num_bytes = int(param[2])
                    size = num_bytes + offset
                else:
                    size = offset = 0  # range exceeds file size

            cur_clus = contents[file_name]["clus_num"]
            clus_size = self.b_p_clus
            output = ""

            if size == 0:
                output = "Exceeds file size of " + str(contents[file_name]["size"]) + " bytes"
            elif size <= clus_size:  # only takes up one cluster
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

            print(output[offset:])

        else:
            print(str(file_name) + " not found")

    def volume(self):
        """
        Prints the volume name of the file system image.  If there is a volume name it
        will be found in the root directory.  If there is no volume name, print “Error: volume name
        not found.”
        """
        root_contents = self.dir_contents(self.root_clus)
        for file_name in root_contents:
            if "ATTR_VOLUME_ID" in root_contents[file_name]['attr']:
                print("Volume ID: " + file_name)
                return
        print("Error: volume name not found")

    def validate_dir_name(self, dir_name):
        return len(dir_name) <= 8 and dir_name[0] != '.'    
    
    def mkdir(self, param):
        """
        Make a new subdirectory in the current directory.  This may require the allocation
        of additional space if the current directory has all entries full in all sectors. It is acceptable
        for you to only add the subdirectory if there is space to do so without allocating an additional
        sector.  If you are unable to create the subdirectory for any reason, you must print an error
        message on stderr (fd 2).
        """
        
        dir_to_mk = param[0]
        if dir_to_mk == "":
            print("Usage: / > mkdir DIR")
            return
        pwd_contents = self.dir_contents(self.pwd_clus)
        if dir_to_mk in pwd_contents:
            print("Error: \"" + dir_to_mk + "\" already in pwd.", file=sys.stderr)
            return
        if not self.validate_dir_name(dir_to_mk):
            print("Error: \"" + dir_to_mk + "\" invalid dir name.", file=sys.stderr)
            return

        # Find open FAT Entry
        open_FAT_entry = -1
        open_FAT_clus_num = 0
        open_FAT_offset = (self.rsec_count * self.b_p_sec) + (open_FAT_clus_num * 4)  # reserved sectors + preceding FAT entries
        while (open_FAT_entry & 0x0FFFFFFF) != 0: # find first open FAT entry
            open_FAT_clus_num += 1
            open_FAT_offset += 4
            open_FAT_entry = int.from_bytes(self.read_bytes(open_FAT_offset, open_FAT_offset + 4), 'little')
        
        # make byte buf of directory entry    
        byte_buf = bytearray(0)
        byte_buf.extend(map(ord, dir_to_mk))
        while len(byte_buf) < 11:
            byte_buf.extend(b' ')
        byte_buf.extend(bytes.fromhex('10 00 00 0000 0000 0000'))
        high_clus_bytes = ((open_FAT_clus_num & 0xFF000000) >> 24) | ((open_FAT_clus_num & 0x00FF0000) >> 8) & 0x0000FFFF
        lo_clus_bytes = ((open_FAT_clus_num & 0x000000FF) << 8) | ((open_FAT_clus_num & 0x0000FF00) >> 8)
        byte_buf.extend(int.to_bytes(high_clus_bytes, 2, 'big'))
        byte_buf.extend(bytes.fromhex('0000 0000'))
        byte_buf.extend(int.to_bytes(lo_clus_bytes, 2, 'big'))
        byte_buf.extend(bytes.fromhex('0000 0000'))
        if len(byte_buf) != 32:
            print("BYTE BUF ERROR: " + byte_buf, file=sys.stderr)
            return

        # Find open directory entry
        cur_clus = self.pwd_clus
        cur_offset = self.clus_to_offset(cur_clus)
        mk_status = False
        while int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 0: # while haven't reached end_of_dir marker
            if int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') == 229: # if free
                mk_status = self.write_bytes(cur_offset, byte_buf)
                break
            cur_offset = cur_offset + 32  # advance to next dir entry
            if cur_offset == self.clus_to_offset(cur_clus) + (self.sec_p_clus * self.b_p_sec):  # reached end of current cluster, check FAT
                FAT_offset = (self.rsec_count * self.b_p_sec) + (cur_clus * 4)  # reserved sectors + preceding FAT entries
                FAT_entry = int.from_bytes(self.read_bytes(FAT_offset, FAT_offset + 4), 'little') & 0x0FFFFFFF
                if FAT_entry != self.eoc_marker:  # dir continues into another cluster
                    cur_clus = FAT_entry
                    cur_offset = self.clus_to_offset(cur_clus)  # set offset to beginning of next data cluster
                else:  
                    print("Error: could not mkdir.", file=sys.stderr)
                    return
        if cur_offset == self.clus_to_offset(cur_clus) + (self.sec_p_clus * self.b_p_sec) - 32: # if no room in sector
            print("Error: could not mkdir.", file=sys.stderr)
            return
        mk_status = self.write_bytes(cur_offset, byte_buf)
        self.write_bytes(cur_offset + 32, bytes.fromhex('00')) # Write end of dir marker
        
        if not mk_status:
            print("Error: could not make " + dir_to_mk, file=sys.stderr)
            return
        mk_status = self.write_bytes(open_FAT_offset, self.eoc_marker_bytes)
        if not mk_status:
            print("Error: could not make " + dir_to_mk, file=sys.stderr)
            return
        
        # make . and .. in new dir
        dir_entry_buf = bytearray(0)
        dir_entry_buf.extend(b'.          ') # name
        dir_entry_buf.extend(bytes.fromhex('10 00 00 0000 0000 0000')) # attr
        dir_entry_buf.extend(int.to_bytes(high_clus_bytes, 2, 'big'))
        dir_entry_buf.extend(bytes.fromhex('0000 0000'))
        dir_entry_buf.extend(int.to_bytes(lo_clus_bytes, 2, 'big'))
        dir_entry_buf.extend(bytes.fromhex('0000 0000'))
        dir_entry_buf.extend(b'..         ') # name
        dir_entry_buf.extend(bytes.fromhex('10 00 00 0000 0000 0000')) # attr
        high_parent_clus_bytes = ((self.pwd_clus & 0xFF000000) >> 24) | ((self.pwd_clus & 0x00FF0000) >> 8) & 0x0000FFFF
        lo_parent_clus_bytes = ((self.pwd_clus & 0x000000FF) << 8) | ((self.pwd_clus & 0x0000FF00) >> 8)
        dir_entry_buf.extend(int.to_bytes(high_parent_clus_bytes, 2, 'big'))
        dir_entry_buf.extend(bytes.fromhex('0000 0000'))
        dir_entry_buf.extend(int.to_bytes(lo_parent_clus_bytes, 2, 'big'))
        dir_entry_buf.extend(bytes.fromhex('0000 0000 00'))
        if(len(dir_entry_buf) != 65):
            print(". and .. buffer ERROR: " + dir_entry_buf)
        mk_status = self.write_bytes(self.clus_to_offset(open_FAT_clus_num), dir_entry_buf)
        if not mk_status:
            print("Error: could not make . and .. for: " + dir_to_mk, file=sys.stderr)
        
    def check_dir_empty(self, dir_clus):
        dir_stuff = self.dir_contents(dir_clus)
        return len(dir_stuff) <= 2
    
    def rmdir(self, param):
        """
        Delete a subdirectory in the current directory, but only if it is empty!  If you
        are unable to delete the subdirectory for any reason, you must print an error message on stderr
        (fd 2).  Follow the FAT32 rules for deleting stuff; do not do a full overwrite or zero anything
        out!
        """
        # Error Check
        dir_to_rm = param[0]
        if dir_to_rm == "" or dir_to_rm == "." or dir_to_rm == "..":
            print("Usage: / > rmdir DIR")
            return
        pwd_contents = self.dir_contents(self.pwd_clus)
        if dir_to_rm not in pwd_contents:
            print("Error: " + dir_to_rm + " not found.", file=sys.stderr)
            return
        if "ATTR_DIRECTORY" not in pwd_contents[dir_to_rm]['attr']:
            print("Error: " + dir_to_rm + " not a directory.", file=sys.stderr)
            return
        dir_to_rm_clus = pwd_contents[dir_to_rm]['clus_num']
        if not self.check_dir_empty(dir_to_rm_clus):
            print("Error: DIR " + dir_to_rm + " not empty.", file=sys.stderr)
            return
        
        # Find directory entry, and set first byte to 0xE5
        cur_clus = self.pwd_clus
        cur_offset = self.clus_to_offset(cur_clus)

        while int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 0:  # while haven't reached end_of_dir marker
            if int.from_bytes(self.read_bytes(cur_offset, cur_offset + 1), 'little') != 229:  # not a free entry
                name = (self.read_bytes(cur_offset, cur_offset + 8).decode()).strip()  # decode name with utf-8 from bytes, strip whitespace
                if name == dir_to_rm:
                    rm_status = self.write_bytes(cur_offset, bytes.fromhex('E5'))
                    break
            cur_offset = cur_offset + 32  # advance to next dir entry
            if cur_offset == self.clus_to_offset(cur_clus) + (self.b_p_clus):  # reached end of current cluster, check FAT
                FAT_offset = (self.rsec_count * self.b_p_sec) + (cur_clus * 4)  # reserved sectors + preceding FAT entries
                FAT_entry = int.from_bytes(self.read_bytes(FAT_offset, FAT_offset + 4), 'little') & 0x0FFFFFFF
                if FAT_entry != self.eoc_marker:  # dir continues into another cluster
                    cur_clus = FAT_entry
                    cur_offset = self.clus_to_offset(cur_clus)  # set offset to beginning of next data cluster
                else:  # eoc reached without clearing dir_entry...
                    break
    
        # clear FAT Table Entry
        if rm_status:
            while (dir_to_rm_clus & 0x0FFFFFFF) != (self.eoc_marker & 0x0FFFFFFF):
                FAT_offset = (self.rsec_count * self.b_p_sec) + (dir_to_rm_clus * 4)  # reserved sectors + preceding FAT entries
                dir_to_rm_clus = int.from_bytes(self.read_bytes(FAT_offset, FAT_offset + 4), 'little')
                high_byte = 0xF0000000 & dir_to_rm_clus
                byte_buf = (high_byte).to_bytes(4, 'little')
                self.write_bytes(FAT_offset, byte_buf)
        if not rm_status:
            print("Error: Failed to remove " + dir_to_rm, file=sys.stderr)


# main routine


argv = sys.argv

if len(argv) < 1:
    print("Usage: > File_System.py FAT32IMG")
    exit()

else:
    fs = FileSystem(argv[1])

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
