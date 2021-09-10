import os
import random
from pathExtractor.utils import *
from pathExtractor.store_paths import *
from pathExtractor.extract_paths import *
import ray
from shutil import copy, rmtree
from subprocess import Popen, PIPE
import shlex

def sudo_process(command, workingDir="./"):
    sudo_password = '2203'
    p = Popen(['sudo', '-S'] + shlex.split(command), stdin=PIPE, stderr=PIPE,
                universal_newlines=True, cwd=workingDir)
    out, err = p.communicate(sudo_password + '\n')
    # print(out)
    print(err)

@ray.remote
def generate_dataset(params):
    in_path, datasetName, startIndex, endIndex, checkpointSet, global_cache, \
    maxPathContexts, maxLength, maxWidth, maxTreeSize, maxFileSize, splitToken, separator, upSymbol, downSymbol, labelPlaceholder, useParentheses = params

    # Create temporary working directories.
    workingDir = os.path.abspath("_temp_dir_" + str(os.getpid()))
    if not os.path.exists(os.path.join(workingDir, "workspace")):
        os.makedirs(os.path.join(workingDir, "workspace"))

    if not os.path.exists(os.path.join(workingDir, "outdir")):
            os.mkdir(os.path.join(workingDir, "outdir"))

    # Process each file in the dataset one-by-one.
    for fileIndex in range(startIndex, endIndex + 1):
        # If it is already extracted, continue.
        if fileIndex in checkpointSet:
            continue

        # Create environment for joern.
        file_name = str(fileIndex) + ".c"
        in_file_path = os.path.join(in_path, file_name)
        # If the file is not in dataset, continue.
        if not os.path.isfile(in_file_path):
            continue

        # Filter files as per the max size requirement.
        statinfo = os.stat(in_file_path)
        if statinfo.st_size > maxFileSize:
            continue

        copy(in_file_path, os.path.join(workingDir, "workspace"))
        # sudo_process("joern-parse workspace", workingDir)
        # sudo_process("joern-export --repr ast --out "+ os.path.join(workingDir, "outdir", "ast"), workingDir)
        # sudo_process("joern-export --repr cfg --out "+ os.path.join(workingDir, "outdir", "cfg"), workingDir)
        # sudo_process("joern-export --repr cdg --out "+ os.path.join(workingDir, "outdir", "cdg"), workingDir)
        # sudo_process("joern-export --repr ddg --out "+ os.path.join(workingDir, "outdir", "ddg"), workingDir)
        # Use joern to create AST, CFG, PDG.
        os.chdir(workingDir)
        os.system("joern-parse workspace")
        os.system("joern-export --repr ast --out " + os.path.join("outdir", "ast"))
        os.system("joern-export --repr cfg --out " + os.path.join("outdir", "cfg"))
        os.system("joern-export --repr cdg --out " + os.path.join("outdir", "cdg"))
        os.system("joern-export --repr ddg --out " + os.path.join("outdir", "ddg"))
        os.chdir("..")

        # Extract paths from AST, CFG, DDG, CDG.
        label, ast_paths, source = extract_ast_paths(os.path.relpath(os.path.join(workingDir, "outdir", "ast")), maxLength, maxWidth, maxTreeSize, splitToken, separator, upSymbol, downSymbol, labelPlaceholder, useParentheses)

        # If no paths are generated, Reset and continue. 
        if not ast_paths or label == None or label == "":
            print(workingDir,file_name, "no paths!!!")
            os.remove(os.path.join(workingDir, "workspace", file_name))
            for folder in os.listdir(os.path.join(workingDir, "outdir")):
                rmtree(os.path.join(workingDir, "outdir", folder))
            continue

        # [TODO] timeout and return empty arrays
        cfg_paths = extract_cfg_paths(source, os.path.relpath(os.path.join(workingDir, "outdir", "cfg")), splitToken, separator, upSymbol, downSymbol, labelPlaceholder, useParentheses)
        cdg_paths = extract_cdg_paths(source, os.path.relpath(os.path.join(workingDir, "outdir", "cdg")), splitToken, separator, upSymbol, downSymbol, labelPlaceholder, useParentheses)
        ddg_paths = extract_ddg_paths(source, os.path.relpath(os.path.join(workingDir, "outdir", "ddg")), splitToken, separator, upSymbol, downSymbol, labelPlaceholder, useParentheses)

        # Select maxPathContexts number of path contexts randomly.
        if len(ast_paths) > maxPathContexts:
            ast_paths = random.sample(ast_paths, maxPathContexts)
        if len(cfg_paths) > maxPathContexts:
            cfg_paths = random.sample(cfg_paths, maxPathContexts)
        if len(cdg_paths) > maxPathContexts:
            cdg_paths = random.sample(cdg_paths, maxPathContexts)
        if len(ddg_paths) > maxPathContexts:
            ddg_paths = random.sample(ddg_paths, maxPathContexts)

        # If CDG, DDG paths are empty, then add a dummy path
        # if not cdg_paths:
        #     cdg_paths.append(("<NULL/>", "<NULL/>", "<NULL/>"))
        # if not ddg_paths:
        #     ddg_paths.append(("<NULL/>", "<NULL/>", "<NULL/>"))

        # Storing the extracted paths in files.

        # i = global_cache.get.remote("i")
        # ri = ray.get(i)
        store_paths(label, file_name, datasetName, ast_paths, cfg_paths, cdg_paths, ddg_paths)
        # ,ri
        # global_cache.put.remote("i",ri+1)
        
        # with ilock:
        #     i.value += 1

        # Remove the current file, and ast, cfg, pdg folder after processing current sample. Otherwise, joern will bail out. 
        os.remove(os.path.join(workingDir, "workspace", file_name))
        for folder in os.listdir(os.path.join(workingDir, "outdir")):
            rmtree(os.path.join(workingDir, "outdir", folder))

    rmtree(workingDir)