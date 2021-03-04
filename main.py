import multiprocess as mp
import math
import os
from generate_dataset import generate_dataset

if __name__ == '__main__':
    in_path = "C:\\Users\\karthik chandra\\Downloads\\Dataset\\C_extracted2"
    numOfProcesses = 8

    totalFiles = len(os.listdir(in_path))
    filesPerProcess = math.floor(totalFiles / 8)
    leftOver = totalFiles % 8

    processFileIndices = []
    for ProcessIndex in range(numOfProcesses):
        startIndex = filesPerProcess * ProcessIndex
        endIndex = startIndex + filesPerProcess - 1
        if ProcessIndex == numOfProcesses - 1:
            endIndex += leftOver
        processFileIndices.append([startIndex, endIndex])

    with mp.Manager() as manager:
        token_count = manager.Value('i', 1)
        path_count = manager.Value('i', 1)
        i = manager.Value('i', 0)
        ilock = manager.Lock()
        count_lock = manager.Lock()
        
        ProcessArguments = ([in_path] + FileIndices + [token_count, path_count, i, ilock, count_lock] for FileIndices in processFileIndices)
        with mp.Pool(processes=numOfProcesses) as pool:
            pool.map(generate_dataset, ProcessArguments)
        
        print("Token count : ", token_count.value)
        print("Path count : ", path_count.value)