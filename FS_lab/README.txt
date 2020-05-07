PROGRAMMING ASSIGNMENT 3: FAT32 FILE SYSTEM UTILITY

May 8, 2020

Eli Perl <eperl@mail.yu.edu 800431807>
Zechariah Rosenthal <zrosent1@mail.yu.edu 800449055>

SUBMISSION CONTENTS:
    README.txt      *this document
    File_System.py  *Python source code for File System utility

EXECUTION:
    RUNNING:
        To run the utility program, enter the following command in a python-equipped shell environment:
        
        > python3.6 File_System.py <fat32.img>

        For the program to run, <fat32.img> must be a path to a valid .img file containing a FAT32 file system image.

    COMMANDS:
        Upon startup, the file system's present working directory (PWD) is set to the system's root directory.
        Once the program is running, the following commands are available for execution:
            
            > info                                        *outputs information inherent to the file system image
            > stat <FILE_NAME/DIR_NAME>                   *outputs size, attributes, and starting cluster of requested file/directory
            > size <FILE_NAME>                            *outputs size of requested file
            > cd <DIR_NAME>                               *changes PWD to requested directory
            > read <FILE_NAME> <POSITION> <NUM_BYTES>     *reads requested number of bytes from requested file starting at requested position
            > volume                                      *outputs volume name for file system image
            > mkdir <SUBDIR_NAME>                         *creates requested sub-directory in PWD
            > rmdir <SUBDIR_NAME>                         *deletes requested sub-directory in PWD
            > quit                                        *quit utility program

        Note: command functionality is dependent on PWD and its contents.

CHALLENGES:
    Thankfully, the Python library has a robust set of helper API for dealing with thornier sub-tasks such as endian-interpretation, encoding and
    decryption, and byte reading/writing. The most difficult aspect of this assignment for us was carefully reading the Microsoft FAT specification
    document and accurately integrating its conventions into our implementation of FAT32 File System Utility.

SOURCES:
    Python online documentation: https://docs.python.org/3.6/tutorial/
    Microsoft FAT specification document: https://www.cs.virginia.edu/~cr4bd/4414/F2018/files/fatspec.pdf