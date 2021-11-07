import os
import random
from pathExtractor.utils import *
from pathExtractor.store_paths import *
from pathExtractor.extract_paths import *
import ray
import re
from shutil import copy, rmtree


def repl(m):
    return "digraph " + ' ' * (len(m.group(1)) - 2) + " {"


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

    # Process each file in the dataset one-by-one.
    for fileIndex in fileIndices:
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

        copy(in_file_path, os.path.join(workingDir, "workspace"))
        os.chdir(workingDir)
        os.system("joern-parse workspace")
        os.system("joern-export --repr ast --out " + os.path.join("outdir", "ast"))
        os.system("joern-export --repr cfg --out " + os.path.join("outdir", "cfg"))
        os.system("joern-export --repr cdg --out " + os.path.join("outdir", "cdg"))
        os.system("joern-export --repr ddg --out " + os.path.join("outdir", "ddg"))
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
        source_nodes = []
        try:
            ast_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "ast"))
            for ast_file in os.listdir(ast_path_s):
                if ast_file.endswith(".dot"):
                    label, ast_path, source_node = extract_ast_paths(os.path.join(ast_path_s, ast_file), maxLength,
                                                                     maxWidth, maxTreeSize, splitToken, separator,
                                                                     upSymbol, downSymbol, labelPlaceholder,
                                                                     useParentheses)
                    ast_paths.extend(ast_path)
                    source_nodes.extend(source_node)
        except TimeoutError:
            print(workingDir)
        else:
            # If no paths are generated, Reset and continue.
            if not ast_paths or label == None or label == "":
                print(workingDir, file_name, "no paths!!!")
                os.remove(os.path.join(workingDir, "workspace", file_name))
                for folder in os.listdir(os.path.join(workingDir, "outdir")):
                    rmtree(os.path.join(workingDir, "outdir", folder))
                continue

            cfg_paths, cdg_paths, ddg_paths = ([] for i in range(3))
            cfg_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "cfg"))
            cdg_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "cdg"))
            ddg_path_s = os.path.relpath(os.path.join(workingDir, "outdir", "ddg"))
            try:
                source = "1000101"
                # for source in source_nodes:
                for cfg_file in os.listdir(cfg_path_s):
                    if cfg_file.endswith(".dot"):
                        cfg_paths.extend(
                            extract_cfg_paths(os.path.join(cfg_path_s, cfg_file), source_nodes,
                                              splitToken, separator, upSymbol, downSymbol, labelPlaceholder,
                                              useParentheses))
                for ddg_file in os.listdir(ddg_path_s):
                    if ddg_file.endswith(".dot"):
                        ddg_paths.extend(
                            extract_ddg_paths(os.path.join(ddg_path_s, ddg_file), source,
                                              splitToken, separator, upSymbol, downSymbol, labelPlaceholder,
                                              useParentheses))
                for cdg_file in os.listdir(cdg_path_s):
                    if cdg_file.endswith(".dot"):
                        cdg_paths.extend(
                            extract_cdg_paths(os.path.join(cdg_path_s, cdg_file),
                                              splitToken, separator, upSymbol, downSymbol, labelPlaceholder,
                                              useParentheses))
            except TimeoutError:
                print(workingDir)
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
            if outputType is "file":
                label = datasetName
            store_paths(label, file_name, datasetName, ast_paths, cfg_paths, cdg_paths, ddg_paths)

        # Remove the current file, and ast, cfg, pdg folder after processing current sample. Otherwise, joern will bail out. 
        os.remove(os.path.join(workingDir, "workspace", file_name))
        for folder in os.listdir(os.path.join(workingDir, "outdir")):
            rmtree(os.path.join(workingDir, "outdir", folder))

    rmtree(workingDir)
