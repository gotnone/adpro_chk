#!/usr/bin/env python

#
# adpro_chk - Checks for File Corruption Issues in Automation Direct
# Productivity Suite Project Files
#
# Stanley Pinchak
# stanley.pinchak@gmail.com
#
# Copyright 2023 Stanley Pinchak
# License: MIT
#

import sys
import argparse
import xml.etree.ElementTree as ET
from zipfile import ZipFile, Path
import logging

logging.basicConfig(level = logging.DEBUG,format = "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s")


def find_dupes(l):
    seen = set()
    dupes = []
    for x in l:
        if x in seen:
                dupes.append(x)
        else:
            seen.add(x)
    return dupes


def print_column(l):
    [print(f"{i}\n") for i in l]


def program_prj_parse(prjfile):
    logger = logging.getLogger(__name__)
    # Parse the xml file
    root = ET.fromstring(prjfile.read())

    # Create an empty list to store the node names
    node_names = []

    # Find all elements with tag name <NodeName>
    paths = root.findall(".//paths")

    # Loop over the nodes and append their text to the list
    for path in paths:
        if path.find("[folder='false']"):
            node = path.find("nodeName")
            node_names.append(node.text)

        # Print the list of node names
    logger.debug(node_names)
    logger.debug(find_dupes(node_names))

    # Create an empty list to store the task names
    task_names = []

    # Find all elements with tag name <taskName>
    tasks = root.findall(".//tasks/taskName")

    # Loop over the tasks and append their text to the list
    for task in tasks:
            task_names.append(task.text)

        # Print the list of task names
    logger.debug(task_names)
    logger.debug(find_dupes(task_names))
    return [task_names, node_names]


def project_check(task_names, node_names, rll_pairs):
    logger = logging.getLogger(__name__)
    pgm_names = [p for [p, x] in rll_pairs]
    logger.debug(pgm_names)
    task_set = set(task_names)
    node_set = set(node_names)
    pgm_set = set(pgm_names)
    super_set = task_set | node_set | pgm_set
    logger.debug("Task_set\n{}".format(task_set))
    logger.debug("Node_set\n{}".format(node_set))
    logger.debug("Pgm_set\n{}".format(pgm_set))
    logger.debug("Super_set\n{}".format(super_set))

    missing_task = super_set - task_set
    missing_node = super_set - node_set
    missing_pgm = super_set - pgm_set

    prj_common = task_set & node_set

    task_dupes = find_dupes(task_names)
    node_dupes = find_dupes(node_names)
    pgm_dupes = find_dupes(pgm_names)
    #common = [x for x in node_names if x in task_names]

        #print the common tasks
    logger.debug("Common:\n{}".format(prj_common))

    result = 0;
    if node_dupes:
        print("Duplicated Node Entries:")
        print_column(node_dupes)
        result |= 1

    if task_dupes:
        print("Duplicated Task Entries:")
        print_column(task_dupes)
        result |= 2

    if pgm_dupes:
        print("Duplicated Pgm Entries:")
        for d in pgm_dupes:
            print(f"{d} : " + ', '.join([f"'{f.name}'" for [p,f] in rll_pairs if p in d]))
        result |=4

    if missing_node:
        print("Missing Task Manager Entry:")
        print_column(missing_node)
        result |= 8

    if missing_task:
        print("Missing Task Definition:")
        print_column(missing_task)
        result |= 16

    if missing_pgm:
        print("Missing Task Program:")
        print_column(missing_pgm)
        result |= 32

    return result


def taskfile_parse(taskfile):
    """Function parses an .rll file"""
    logger = logging.getLogger(__name__)
    logger.debug(taskfile)
    # Parse the xml file
    root = ET.fromstring(taskfile.read())
    # Find all elements with tag name <pgmName>
    pgmname = root.find(".//pgmName")
    if pgmname is not None:
        return pgmname.text

    logger.error(
        "Program Abort\nCould not find '<pgmName>' in task file %s", taskfile.name
    )
    sys.exit(-1)


def main():
    """Program main() function"""
    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser("Productivity Suite Project Verificator")
    parser.add_argument("projfile", help="The .adpro file to check")
    parser.add_argument(
        "-log",
        "--loglevel",
        default="warning",
        help="Provide logging level. Example --loglevel debug, default=warning",
    )
    args = parser.parse_args()
    logger.setLevel(args.loglevel.upper())

    with ZipFile(args.projfile) as projfile:
        task_names = []
        node_names = []
        rll_pairs = []
        with projfile.open("program.prj") as program_prj:
            [task_names, node_names] = program_prj_parse(program_prj)

        tasks = [x for x in Path(projfile).iterdir() if r"task" in x.name]

        for t in tasks:
            with t.open() as taskfile:
                pgm_name = taskfile_parse(taskfile)
                rll_pairs.append((pgm_name, t))

        logger.debug([[p, f.name] for [p, f] in rll_pairs])

        sys.exit(project_check(task_names, node_names, rll_pairs))


if __name__ == "__main__":
    main()
