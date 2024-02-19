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

"""adpro_chk Checks for File Corruption in Automation Direct Productivity Suite Project
Files."""

import argparse
import logging
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import IO, AnyStr, Final, List
from zipfile import ZipFile, ZipInfo

CORRUPT_PGMFILE: Final[int] = 1 << 26
MISSING_PGMNAME: Final[int] = 1 << 27

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
)


@dataclass
class RllPair:
    """Class to contain pairs of taskname, taskfile (.rll)"""

    taskname: str
    infozip: ZipInfo


def find_dupes(list_with_dupes):
    """Function to find duplicates in a list."""
    seen = set()
    dupes = []
    for item in list_with_dupes:
        if item in seen:
            dupes.append(item)
        else:
            seen.add(item)
    return dupes


def print_column(list_to_print):
    """Function to print a list as a column to stdout."""
    for i in list_to_print:
        print(f"{i}\n")


def program_prj_parse(prjfile):
    """Function to parse the program.prj file."""
    logger = logging.getLogger(__name__)
    # Parse the xml file
    root = ET.fromstring(prjfile.read())

    # Create an empty list to store the node names
    node_names = []

    # Find all elements in <paths> which have <folder> = false with tag name <nodeName>
    nodes = root.findall(".//paths/[folder='false']/nodeName")

    # Loop over the nodes and append their text to the list
    for node in nodes:
        node_names.append(node.text)

    # Print the list of node names
    logger.debug("node_names:\n%s", node_names)

    # Create an empty list to store the task names
    task_names = []

    # Find all elements in <tasks> with tag name <taskName>
    tasks = root.findall("./tasks/taskName")

    # Loop over the tasks and append their text to the list
    for task in tasks:
        task_names.append(task.text)

    # Print the list of task names
    logger.debug("task_names:\n%s", task_names)
    return [task_names, node_names]


def missing_task_check(task_names, node_names, pgm_names):
    """Function checks to see if there are missing tasks."""
    logger = logging.getLogger(__name__)
    task_set = set(task_names)
    node_set = set(node_names)
    pgm_set = set(pgm_names)
    super_set = task_set | node_set | pgm_set
    logger.debug("Task_set\n%s", task_set)
    logger.debug("Node_set\n%s", node_set)
    logger.debug("Pgm_set\n%s", pgm_set)
    logger.debug("Super_set\n%s", super_set)

    missing_task = super_set - task_set
    missing_node = super_set - node_set
    missing_pgm = super_set - pgm_set

    prj_common = task_set & node_set

    # print the common tasks
    logger.debug("Common:\n%s", prj_common)

    result = 0
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


def project_check(task_names, node_names, rll_pairs):
    """Function to check for corruption in an .adpro file."""
    logger = logging.getLogger(__name__)
    pgm_names = [p.taskname for p in rll_pairs]
    logger.debug(pgm_names)

    task_dupes = find_dupes(task_names)
    node_dupes = find_dupes(node_names)
    pgm_dupes = find_dupes(pgm_names)
    logger.debug("task_dupes:%s", task_dupes)
    logger.debug("node_dupes:%s", node_dupes)
    logger.debug("pgm_dupes:%s", pgm_dupes)

    result = 0
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
        for dup in pgm_dupes:
            print(
                f"{dup} : "
                + ", ".join(
                    [f"'{p.infozip.filename}'" for p in rll_pairs if p.taskname in dup]
                )
            )
        result |= 4

    return result | missing_task_check(task_names, node_names, pgm_names)


def taskfile_parse(taskfile: IO[AnyStr], filename: str):
    """Function parses an .rll file."""
    logger = logging.getLogger(__name__)
    logger.debug(taskfile)
    # Parse the xml file
    root: ET.Element
    try:
        root = ET.fromstring(taskfile.read())
    except ET.ParseError:
        logger.error(
            "Program Abort\nUnable to parse task program file for %s", filename
        )
        sys.exit(CORRUPT_PGMFILE)
    # Find all elements with tag name <pgmName>
    pgmname = root.find("./pgmName")
    if pgmname is not None:
        if pgmname.text is not None:
            return pgmname.text
        logger.error(
            "Program Abort\nUnable to find '<pgmName>' with valid text in task file %s",
            taskfile.name,
        )
        sys.exit(MISSING_PGMNAME)
    logger.error(
        "Program Abort\nUnable to find '<pgmName>' in task file %s", taskfile.name
    )
    sys.exit(MISSING_PGMNAME)


def main():
    """Program main() function."""
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

    task_names: List[str]
    node_names: List[str]
    rll_pairs: List[RllPair] = []

    with ZipFile(args.projfile, mode="r") as projfile:
        with projfile.open("program.prj") as program_prj:
            task_names, node_names = program_prj_parse(program_prj)

        tasks = [x for x in projfile.infolist() if r"task" in x.filename]

        for task in tasks:
            with projfile.open(task) as taskfile:
                rll_pairs.append(RllPair(taskfile_parse(taskfile, task.filename), task))

        logger.debug([(p.taskname, p.infozip.filename) for p in rll_pairs])

        sys.exit(project_check(task_names, node_names, rll_pairs))


if __name__ == "__main__":
    main()
