import os
import sys
import math
import configparser
import multiprocess as mp
from store_paths import *
from generate_dataset import *

def getFileIndices(in_path, numOfProcesses):
    # Divide the work between processes.
    totalFiles = len(os.listdir(in_path))
    filesPerProcess = math.floor(totalFiles / numOfProcesses)
    leftOver = totalFiles % numOfProcesses

    # Calculate the start and end file indices for each process.
    processFileIndices = []
    for processIndex in range(numOfProcesses):
        startIndex = filesPerProcess * processIndex
        endIndex = startIndex + filesPerProcess - 1
        if processIndex == numOfProcesses - 1:
            endIndex += leftOver
        processFileIndices.append([startIndex, endIndex])

    return processFileIndices

if __name__ == '__main__':

    # Reading the configuration parameters from config.ini file.
    config = configparser.ConfigParser()
    config.read(os.path.join("..", "config.ini"))
    in_path = config['pathExtractor']['inputPath']
    numOfProcesses = config['pathExtractor'].getint('numOfProcesses')
    maxPathContexts = config['pathExtractor'].getint('maxPathContexts')
    maxLength = config['pathExtractor'].getint('maxLength')
    maxWidth = config['pathExtractor'].getint('maxWidth')
    maxTreeSize = config['pathExtractor'].getint('maxTreeSize')
    maxFileSize = config['pathExtractor'].getint('maxFileSize')
    separator = config['pathExtractor']['separator']
    splitToken = config['pathExtractor'].getboolean('splitToken')
    upSymbol = config['pathExtractor']['upSymbol']
    downSymbol = config['pathExtractor']['downSymbol']
    useParentheses = config['pathExtractor'].getboolean('useParentheses')
    useCheckpoint = config['pathExtractor'].getboolean('useCheckpoint')

    # Divide the work between processes.
    processFileIndices = getFileIndices(in_path, numOfProcesses)

    # This is used to track what files were processed already by each process. Used in checkpointing.
    initialCount = 0
    checkpointDict = {}
    for processIndex in range(numOfProcesses):
        checkpointDict[processIndex] = set()

    # If the output files already exist, either use it as a checkpoint or don't continue the execution.
    if os.path.isfile(os.path.join("..", "corpus.txt")) or os.path.isfile(os.path.join("..", "token_idxs.txt")) or os.path.isfile(os.path.join("..", "path_idxs.txt")):
        if useCheckpoint:
            print("corpus.txt file exists. Using it as a checkpoint ...")
            
            with open(os.path.join("..", "corpus.txt"), 'r') as f:
                for line in f:
                    if line.startswith("file:"):
                        fileIndex = int(line.strip('file:.c\n\t '))
                        for processIndex, filesRange in enumerate(processFileIndices):
                            if fileIndex >= filesRange[0] and fileIndex <= filesRange[1]:
                                checkpointDict[processIndex].add(fileIndex)
                                initialCount += 1
                                break
        else:
            print("corpus.txt or token_idxs.txt or path_idxs.txt files already exist. Exiting..")
            sys.exit()

    with mp.Manager() as manager:
        i = manager.Value('i', initialCount)
        ilock = manager.Lock()

        # Create the argument collection, where each element contains the array of parameters for each process.
        ProcessArguments = ([in_path] + FileIndices + [checkpointDict[processIndex]] + [i, ilock] \
                            + [maxPathContexts, maxLength, maxWidth, maxTreeSize, maxFileSize, splitToken, separator, upSymbol, downSymbol, useParentheses] for processIndex, FileIndices in enumerate(processFileIndices))

        # Start executing multiple processes.
        with mp.Pool(processes = numOfProcesses) as pool:
            pool.map(generate_dataset, ProcessArguments)