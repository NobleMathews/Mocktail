import glob
import math
from pkgutil import iter_modules
import psutil
import ray
from projectPreprocessor.process_files import *
from pathExtractor.generate_dataset import *
from output_formatter import *
from questionary import Choice
from pathlib import Path
import configparser
import questionary
import os
from shutil import rmtree, which

# find . -name '*.txt' -exec sh -c 'mv "$0" "${0%.txt}.c"' {} \;
# Reading the configuration parameters from config.ini file.
config = configparser.ConfigParser()
dirname = os.path.dirname(os.path.realpath(__file__))
config.read(os.path.join(dirname, "config.ini"))

in_path = "./1_input"
process_path = "./2_processed"
output_dir = "./3_output"

# dot -Tpng 0-ast.dot -o 0-ast.png
numOfProcesses = psutil.cpu_count()
num_cpus = psutil.cpu_count(logical=False)
outputType = config['projectPreprocessor']['outputType']

def checks():
    # if os.getuid() == 0:
    #     raise Exception("This program requires to be run as root but was called by " + getpass.getuser())
    for dependency in ["joern", "terashuf"]:
        if which(dependency) is None:
            raise Exception("Check whether " + dependency + " is on PATH and marked as executable.")
    modules = set(x[1] for x in iter_modules())
    with open(os.path.join(dirname, './requirements.txt'), 'r') as f:
        for line in f:
            requirement = line.split("=")[0].strip()
            if requirement not in modules:
                raise Exception("Missing dependency: " + requirement)
    in_path = "./1_input"
    if not Path.exists(Path(os.path.join(dirname, in_path))):
        raise Exception("Missing input directory, please update config.ini")
    if not questionary.confirm("Have you updated config with required details ?").ask():
        raise Exception("Please update and confirm config file contents")


def divide(lst, n):
    p = len(lst) // n
    if len(lst) - p > 0:
        return [lst[:p]] + divide(lst[p:], n - 1)
    else:
        return [lst]


def getFileIndices(in_path, numOfProcesses):
    # Divide the work between processes.
    totalFiles = os.listdir(in_path)
    return divide(totalFiles, numOfProcesses)


def pre_process():
    # print({section: dict(config[section]) for section in config.sections()})
    maxFileSize = config['projectPreprocessor'].getint('maxFileSize')

    intermediate_path = os.path.join(dirname, in_path, "_temp_file_dir_")
    if os.path.exists(intermediate_path):
        rmtree(intermediate_path)
    os.mkdir(intermediate_path)

    try:
        filter_files(in_path, intermediate_path)
        if outputType == "multiple":
            split_files_into_functions_multiple(intermediate_path, process_path, maxFileSize)
        elif outputType == "single":
            split_files_into_functions_single(intermediate_path, process_path, maxFileSize)
        elif outputType == "file":
            filter_files(in_path, process_path)

    except Exception as e:
        raise Exception(e)

    finally:
        rmtree(intermediate_path)
        for filename in glob.glob("./_temp_*"):
            rmtree(filename)


def process(datasetName):
    maxPathContexts = config['pathExtractor'].getint('maxPathContexts')
    maxLength = config['pathExtractor'].getint('maxLength')
    maxWidth = config['pathExtractor'].getint('maxWidth')
    maxTreeSize = config['pathExtractor'].getint('maxTreeSize')
    maxFileSize = config['pathExtractor'].getint('maxFileSize')
    separator = config['pathExtractor']['separator']
    splitToken = config['pathExtractor'].getboolean('splitToken')
    upSymbol = config['pathExtractor']['upSymbol']
    downSymbol = config['pathExtractor']['downSymbol']
    labelPlaceholder = config['pathExtractor']['labelPlaceholder']
    useParentheses = config['pathExtractor'].getboolean('useParentheses')
    useCheckpoint = config['pathExtractor'].getboolean('useCheckpoint')
    outputType = config['projectPreprocessor']['outputType']

    # Divide the work between processes.
    processFileIndices = getFileIndices(os.path.join(process_path, datasetName), numOfProcesses)

    # This is used to track what files were processed already by each process. Used in checkpointing.
    initialCount = 0
    checkpointDict = {}
    for processIndex in range(numOfProcesses):
        checkpointDict[processIndex] = set()

    # If the output files already exist, either use it as a checkpoint or don't continue the execution.
    if os.path.isfile(os.path.join(process_path, datasetName, datasetName + ".c2v")):
        if useCheckpoint:
            print(datasetName + ".c2v file exists. Using it as a checkpoint ...")

            with open(os.path.join(process_path, datasetName, datasetName + ".c2v"), 'r') as f:
                for line in f:
                    if line.startswith("file:"):
                        fileIndex = line.strip('file:\n\t ')
                        for processIndex, filesRange in enumerate(processFileIndices):
                            if fileIndex in filesRange:
                                checkpointDict[processIndex].add(fileIndex)
                                initialCount += 1
                                break
            initialCount += 1

        else:
            print(datasetName + ".c2v file already exist. Exiting ...")
            sys.exit()

    # Create the argument collection, where each element contains the array of parameters for each process.
    ProcessArguments = (
        [process_path, datasetName, outputType] + [FileIndices] + [checkpointDict[processIndex]] + [maxPathContexts,
                                                                                                    maxLength,
                                                                                                    maxWidth,
                                                                                                    maxTreeSize,
                                                                                                    maxFileSize,
                                                                                                    splitToken,
                                                                                                    separator, upSymbol,
                                                                                                    downSymbol,
                                                                                                    labelPlaceholder,
                                                                                                    useParentheses]
        for
        processIndex, FileIndices in enumerate(processFileIndices))

    # # Start executing multiple processes.
    # with mp.Pool(processes = numOfProcesses) as pool:
    #     pool.map(generate_dataset, ProcessArguments)
    ray.init(num_cpus=num_cpus)
    ray.get([generate_dataset.remote(x) for x in ProcessArguments])
    for filename in glob.glob("./_temp_*"):
        print(filename)
        rmtree(filename)
    ray.shutdown()


def post_process(options):
    hash_to_string_dict = {}
    token_freq_dict = {}
    path_freq_dict = {}
    target_freq_dict = {}

    include_paths = {'ast': "AST" in options, 'cfg': "CFG" in options, 'cdg': "CDG" in options, 'ddg': "DDG" in options}
    max_path_count = {'ast': 0, 'cfg': 0, 'cdg': 0, 'ddg': 0}
    dataset_name_ext = '_'.join(options)
    datasets = [f.name for f in os.scandir("./2_processed") if f.is_dir()]
    not_include_methods = config['outputFormatter']['notIncludeMethods']
    not_include_methods = [method.strip() for method in not_include_methods.split(',')]

    max_path_count['ast'] = config['outputFormatter'].getint('maxASTPaths')
    max_path_count['cfg'] = config['outputFormatter'].getint('maxCFGPaths')
    max_path_count['cdg'] = config['outputFormatter'].getint('maxCDGPaths')
    max_path_count['ddg'] = config['outputFormatter'].getint('maxDDGPaths')

    ## For normal Train-Test-Val split.
    for dataset_name in datasets:
        try:
            destination_dir = os.path.join(output_dir, dataset_name, dataset_name_ext)
            data_path = os.path.join(process_path, dataset_name, dataset_name + ".c2v")
            os.makedirs(destination_dir, exist_ok=True)

            ## Convert the input data file into model input format. Takes only "max_path_count" number of paths for each type. Removes the "not_include_methods" methods.
            num_examples = convert_to_model_input_format(data_path, os.path.join(output_dir, dataset_name,
                                                                                 "{}.c2v".format(dataset_name + '.full')),
                                                         max_path_count, not_include_methods, hash_to_string_dict)

            ## Shuffle the output file of above step.
            if os.path.isfile(os.path.join(output_dir, dataset_name, '{}.full.shuffled.c2v'.format(dataset_name))):
                print("{} already exists!".format(
                    os.path.join(output_dir, dataset_name, '{}.full.shuffled.c2v'.format(dataset_name))))
            else:
                os.system(
                    'terashuf < {output_dir}/{dataset_name}/{dataset_name}.full.c2v > {output_dir}/{dataset_name}/{dataset_name}.full.shuffled.c2v'.format(
                        output_dir=output_dir, dataset_name=dataset_name))

            ## Splitting the joined and shuffled file into Train-Test-Val sets.
            split_dataset(os.path.join(output_dir, dataset_name), dataset_name, num_examples)

            ## Use "include_paths" to select specific type of paths.
            filter_paths(os.path.join(output_dir, dataset_name, '{}.train.c2v'.format(dataset_name)),
                         os.path.join(destination_dir, '{}.train.c2v'.format(dataset_name + '_' + dataset_name_ext)),
                         os.path.join(output_dir, '{}.train.c2v'.format(dataset_name_ext)),
                         include_paths, max_path_count)
            filter_paths(os.path.join(output_dir, dataset_name, '{}.test.c2v'.format(dataset_name)),
                         os.path.join(destination_dir, '{}.test.c2v'.format(dataset_name + '_' + dataset_name_ext)),
                      os.path.join(output_dir, '{}.test.c2v'.format(dataset_name_ext)),
                         include_paths, max_path_count)
            filter_paths(os.path.join(output_dir, dataset_name, '{}.val.c2v'.format(dataset_name)),
                         os.path.join(destination_dir, '{}.val.c2v'.format(dataset_name + '_' + dataset_name_ext)),
                      os.path.join(output_dir, '{}.val.c2v'.format(dataset_name_ext)),
                         include_paths, max_path_count)

            ## Create dictionaries using training data.
            create_dictionaries(os.path.join(destination_dir, '{}.train.c2v'.format(dataset_name + '_' + dataset_name_ext)),
                                token_freq_dict, path_freq_dict, target_freq_dict)

            ## Save the dictionary file.
            save_dictionaries(os.path.join(output_dir, '{}.dict.c2v'.format(dataset_name_ext)),
                              hash_to_string_dict, token_freq_dict, path_freq_dict, target_freq_dict, outputType,
                              round(num_examples * 0.89))
        except Exception as e:
            print(e)


if __name__ == "__main__":
    try:
        checks()
    except Exception as err:
        raise SystemExit(err)
    joblist = questionary.checkbox(
        "Select actions to perform",
        choices=[Choice("Preprocess project", checked=True), Choice("Path extraction", checked=True),
                 Choice("Format output", checked=True)],
    ).ask()
    include_paths = questionary.checkbox(
        "Select paths to include",
        choices=[Choice("AST", checked=True), Choice("CFG", checked=True), Choice("CDG", checked=False),
                 Choice("DDG", checked=True)],
    ).ask()
    if "Preprocess project" in joblist:
        pre_process()
    if "Path extraction" in joblist:
        for f in os.scandir("./2_processed"):
            if f.is_dir():
                process(f.name)
    if "Format output" in joblist:
        post_process(include_paths)
