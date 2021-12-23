import os
import random
from pathExtractor.utils import *
from pathExtractor.store_paths import *
from pathExtractor.extract_paths import *
import psutil
import gc
import ray
import re
from shutil import copy, rmtree
import time


def repl(m):
    return "digraph " + ' ' * (len(m.group(1)) - 2) + " {"


def auto_garbage_collect(pct=15.0):
    if psutil.virtual_memory().percent >= pct:
        print("GARBAGE COLLECTED")
        gc.collect()


@ray.remote
def generate_dataset(params):
    in_path, datasetName, outputType, fileIndices, checkpointSet, \
    maxPathContexts, maxLength, maxWidth, maxTreeSize, maxFileSize, splitToken, separator, upSymbol, downSymbol, labelPlaceholder, useParentheses = params

    # Create temporary working directories.
    workingDir = os.path.abspath("_temp_dir_" + str(os.getpid()))
    if not os.path.exists(os.path.join(workingDir, "workspace")):
        os.makedirs(os.path.join(workingDir, "workspace"))

    if not os.path.exists(os.path.join(workingDir, "outdir")):
        os.mkdir(os.path.join(workingDir, "outdir"))
    time_in = None
    if len(fileIndices) < 1:
        return -1
    # Process each file in the dataset one-by-one.
    for fileIndex in fileIndices:
        if time_in is not None:
            with open('time.txt', 'a') as fileO:
                fileO.write(str(time.time() - time_in) + "\n")
            print("Timing each file(s) -> " + str(time.time() - time_in))

        time_in = time.time()
        # If it is already extracted, continue.
        if fileIndex in checkpointSet:
            continue
        # Create environment for joern.
        file_name = fileIndex
        in_file_path = os.path.join(in_path, datasetName, file_name)

        # # If the file is not in dataset as a c file, continue.
        # if not os.path.isfile(in_file_path):
        #     continue
        #
        # Filter files as per the max size requirement.
        statinfo = os.stat(in_file_path)
        if statinfo.st_size > maxFileSize:
            continue

        print("begin joern")
        copy(in_file_path, os.path.join(workingDir, "workspace"))
        os.chdir(workingDir)
        preventOut = " >/dev/null 2>&1"
        os.system("joern-parse workspace" + preventOut)
        os.system("joern-export --repr ast --out " + os.path.join("outdir", "ast") + preventOut)
        os.system("joern-export --repr cfg --out " + os.path.join("outdir", "cfg") + preventOut)
        os.system("joern-export --repr cdg --out " + os.path.join("outdir", "cdg") + preventOut)
        os.system("joern-export --repr ddg --out " + os.path.join("outdir", "ddg") + preventOut)
        # print("end joern")
        # print("begin dot cleanup")
        for dirpath, dirnames, filenames in os.walk(workingDir):
            for filename in [f for f in filenames if f.endswith(".dot")]:
                with open(os.path.join(dirpath, filename), "r+") as f:
                    line = next(f)
                    result = re.sub('digraph(.*){', repl, line)
                    f.seek(0)
                    f.write(result)
        os.chdir("..")
        # Extract paths from AST, CFG, DDG, CDG.
        label = None
        ast_paths = []
        # source_nodes = []
        # print("begin ast check")
        ast_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "ast"))
        for ast_file in os.listdir(ast_path_s):
            if ast_file.endswith(".dot"):
                auto_garbage_collect()
                # label, ast_path =
                ast_paths.extend(extract_ast_paths(os.path.join(ast_path_s, ast_file), maxLength,
                                                   maxWidth, maxTreeSize, splitToken, separator,
                                                   upSymbol, downSymbol, labelPlaceholder,
                                                   useParentheses))
                # source_nodes.extend(source_node)
        # print("end ast checks")
        # If no paths are generated, Reset and continue.
        if not ast_paths:
            print(workingDir, file_name, "no paths!!!")
            os.remove(os.path.join(workingDir, "workspace", file_name))
            for folder in os.listdir(os.path.join(workingDir, "outdir")):
                rmtree(os.path.join(workingDir, "outdir", folder))
            continue
        print("begin cfg cdg and ddg")
        cfg_paths, cdg_paths, ddg_paths = ([] for i in range(3))
        cfg_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "cfg"))
        cdg_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "cdg"))
        ddg_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "ddg"))
        source = "1000101"
        # for source in source_nodes:
        # print("begin cfg")
        for cfg_file in os.listdir(cfg_path_s):
            if cfg_file.endswith(".dot"):
                cfg_paths.extend(
                    extract_cfg_paths(os.path.join(cfg_path_s, cfg_file), source,
                                      splitToken, separator, upSymbol, downSymbol,
                                      labelPlaceholder,
                                      useParentheses)
                )
        auto_garbage_collect()
        # print("begin ddg")
        for ddg_file in os.listdir(ddg_path_s):
            if ddg_file.endswith(".dot"):
                ddg_paths.extend(extract_ddg_paths(os.path.join(ddg_path_s, ddg_file), source,
                                                   splitToken, separator, upSymbol, downSymbol,
                                                   labelPlaceholder,
                                                   useParentheses))
        auto_garbage_collect()
        # print("begin cdg")
        for cdg_file in os.listdir(cdg_path_s):
            if cdg_file.endswith(".dot"):
                cdg_paths.extend(extract_cdg_paths(os.path.join(cdg_path_s, cdg_file),
                                                   splitToken, separator, upSymbol, downSymbol,
                                                   labelPlaceholder,
                                                   useParentheses))
        auto_garbage_collect()
        # Select maxPathContexts number of path contexts randomly.
        print("begin sampling")
        if len(ast_paths) > maxPathContexts:
            ast_paths = random.sample(ast_paths, maxPathContexts)
        if len(cfg_paths) > maxPathContexts:
            cfg_paths = random.sample(cfg_paths, maxPathContexts)
        if len(cdg_paths) > maxPathContexts:
            cdg_paths = random.sample(cdg_paths, maxPathContexts)
        if len(ddg_paths) > maxPathContexts:
            ddg_paths = random.sample(ddg_paths, maxPathContexts)

        if time_in is not None:
            with open('time.txt', 'a+') as fileO:
                fileO.write(str(time.time() - time_in) + "\n")
            print("Timing each file(s) -> " + str(time.time() - time_in))

        # If CDG, DDG paths are empty, then add a dummy path
        # if not cdg_paths:
        #     cdg_paths.append(("<NULL/>", "<NULL/>", "<NULL/>"))
        # if not ddg_paths:
        #     ddg_paths.append(("<NULL/>", "<NULL/>", "<NULL/>"))

        # Storing the extracted paths in files.
        if outputType == "file":
            label = datasetName
        print("SUCESS PATH SAVED TO C2V FILE")
        store_paths(label, file_name, datasetName, ast_paths, cfg_paths, cdg_paths, ddg_paths)

        # Remove the current file, and ast, cfg, pdg folder after processing current sample. Otherwise, joern will bail out.
        os.remove(os.path.join(workingDir, "workspace", file_name))
        for folder in os.listdir(os.path.join(workingDir, "outdir")):
            rmtree(os.path.join(workingDir, "outdir", folder))
        print("RMTREE COMPLETED")

    # rmtree(workingDir)
    if os.path.exists("time.txt"):
        with open("time.txt", 'r') as f:
            fpm = 0
            total_time = 0
            for time_used in f:
                time_used = time_used.strip()
                fpm = fpm + 1 / float(time_used)
                # total time for a dataset
                total_time = total_time + float(time_used)
            pass
        # with open("time.txt", 'w') as f:
        #     pass
        with open('time_summary.txt', 'a+') as fileO:
            fileO.write(str(total_time)+" per_file->fpm "+str(fpm) + "\n")
    return 1
