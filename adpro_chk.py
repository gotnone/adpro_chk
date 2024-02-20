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
from dataclasses import dataclass, field
from io import BytesIO
from typing import IO, AnyStr, BinaryIO, Final, List, Set
from zipfile import ZipFile, ZipInfo

import lxml.etree as ET

DUP_NODE: Final[int] = 1
DUP_TASK: Final[int] = 1 << 1
DUP_PGM: Final[int] = 1 << 2
MISSING_NODE: Final[int] = 1 << 3
MISSING_TASK: Final[int] = 1 << 4
MISSING_PGM: Final[int] = 1 << 5
CORRUPT_PROGRAM_PRJ: Final[int] = 1 << 25
CORRUPT_PGMFILE: Final[int] = 1 << 26
MISSING_PGMNAME: Final[int] = 1 << 27
MAGIC_NUM: Final[bytes] = b"\xad\xc0\x30\x00"

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
)


@dataclass
class FixFile:
    """Class to contain ZipInfo and BytesIO filebuffer of fixed files."""

    infozip: ZipInfo
    filebuf: BytesIO


@dataclass
class RllPair:
    """Class to contain pairs of taskname, taskfile (.rll)"""

    taskname: str
    infozip: ZipInfo


@dataclass
class ProjErrors:
    """Class to hold all errors found in adpro file."""

    # pylint: disable=too-many-instance-attributes
    # This is a dataclass and it is not possible to refactor such that a
    # common dataclass can contain the missing, renamed, and duplicate data
    # structures for all three task, node, and pgm types
    missing_task: Set[str] = field(default_factory=set)
    missing_node: Set[str] = field(default_factory=set)
    missing_pgm: Set[str] = field(default_factory=set)
    renamed_task: Set[str] = field(default_factory=set)
    renamed_node: Set[str] = field(default_factory=set)
    renamed_pgm: List[RllPair] = field(default_factory=list)
    duplicate_node: List[str] = field(default_factory=list)
    duplicate_task: List[str] = field(default_factory=list)
    duplicate_pgm: List[str] = field(default_factory=list)


def write_tree(tree: ET._ElementTree, output: BinaryIO):
    """Write an ElementTree to an IO output object with adpro style xml declaration."""
    output.write(
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + ET.tostring(tree.getroot(), method="xml", encoding="UTF-8")
    )


def make_name_clsr(original: str):
    """Closure for incrementing a suffix on a base name."""
    base = original
    suffix = 0

    def name():
        nonlocal base
        return base + (("_" + str(suffix)) if suffix != 0 else "")

    def next_name():
        nonlocal suffix
        suffix += 1
        return name()

    return name, next_name


def find_dupes(list_with_dupes):
    """Function to find duplicates in a list."""
    seen = set()
    renames = set()
    dupes = []
    for item in list_with_dupes:
        if item in seen:
            dupes.append(item)
            name, nextname = make_name_clsr(item)
            while name() in renames:
                nextname()
            renames.add(name())
        else:
            seen.add(item)
    return dupes, renames


def find_rll_dupes(list_with_dupes: List[RllPair]):
    """Function to find duplicates in a list."""
    seen = set()
    renames = []
    dupes = []
    for item in list_with_dupes:
        if item.taskname in seen:
            dupes.append(item.taskname)
            name, nextname = make_name_clsr(item.taskname)
            while nextname() in (n for n, _ in renames):
                pass
            renames.append(RllPair(name(), item.infozip))
        else:
            seen.add(item.taskname)
    return dupes, renames


def print_column(list_to_print):
    """Function to print a list as a column to stdout."""
    for i in list_to_print:
        print(f"{i}\n")


def program_prj_parse(prjfile):
    """Function to parse the program.prj file."""
    logger = logging.getLogger(__name__)
    # Parse the xml file
    root: ET._Element
    try:
        root = ET.fromstring(prjfile.read())
    except ET.ParseError:
        logger.error("Program Abort\nUnable to parse program.prj file")
        sys.exit(CORRUPT_PROGRAM_PRJ)

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


def missing_task_check(
    task_names: List[str],
    node_names: List[str],
    pgm_names: List[str],
    found_errors: ProjErrors,
):
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

    found_errors.missing_task = super_set - task_set
    found_errors.missing_node = super_set - node_set
    found_errors.missing_pgm = super_set - pgm_set

    prj_common = task_set & node_set

    # print the common tasks
    logger.debug("Common:\n%s", prj_common)

    result = 0
    if found_errors.missing_node:
        print("Missing Task Manager Entry:")
        print_column(found_errors.missing_node)
        result |= MISSING_NODE

    if found_errors.missing_task:
        print("Missing Task Definition:")
        print_column(found_errors.missing_task)
        result |= MISSING_TASK

    if found_errors.missing_pgm:
        print("Missing Task Program:")
        print_column(found_errors.missing_pgm)
        result |= MISSING_PGM

    return result


def project_check(
    task_names: List[str],
    node_names: List[str],
    rll_pairs: List[RllPair],
    found_errors: ProjErrors,
):
    """Function to check for corruption in an .adpro file."""
    logger = logging.getLogger(__name__)
    pgm_names = [p.taskname for p in rll_pairs]
    logger.debug(pgm_names)

    found_errors.duplicate_task, found_errors.renamed_task = find_dupes(task_names)
    found_errors.duplicate_node, found_errors.renamed_node = find_dupes(node_names)
    found_errors.duplicate_pgm, found_errors.renamed_pgm = find_rll_dupes(rll_pairs)
    logger.debug("task_dupes:%s", found_errors.duplicate_task)
    logger.debug("node_dupes:%s", found_errors.duplicate_node)
    logger.debug("pgm_dupes:%s", found_errors.duplicate_pgm)

    result = 0
    if found_errors.duplicate_node:
        print("Duplicated Node Entries:")
        print_column(found_errors.duplicate_node)
        result |= DUP_NODE

    if found_errors.duplicate_task:
        print("Duplicated Task Entries:")
        print_column(found_errors.duplicate_task)
        result |= DUP_TASK

    if found_errors.duplicate_pgm:
        print("Duplicated Pgm Entries:")
        print_column(
            [
                f"{dup} : "
                + ", ".join(
                    [p.infozip.filename for p in rll_pairs if p.taskname == dup]
                )
                for dup in found_errors.duplicate_pgm
            ]
        )
        result |= DUP_PGM

    return result | missing_task_check(task_names, node_names, pgm_names, found_errors)


def taskfile_parse(taskfile: IO[AnyStr], filename: str):
    """Function parses an .rll file."""
    logger = logging.getLogger(__name__)
    logger.debug(taskfile)
    # Parse the xml file
    root: ET._Element
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


def fix_program_prj(
    projfile: ZipFile, found_errors: ProjErrors, fixlist: List[FixFile]
):
    """Function to fix errors in program.prj."""
    _ = (projfile, found_errors, fixlist)


def in_fixlist(chkfile: ZipInfo, fixlist: List[FixFile]):
    """Function to return FixFile if chkfile in fixlist."""
    index = next(
        (i for i, f in enumerate(fixlist) if f.infozip.filename == chkfile.filename),
        None,
    )
    if index is not None:
        return fixlist.pop(index)
    return None


def fix_project(projfilestr: str, fixfilestr: str, found_errors: ProjErrors):
    """Function to fix errors in adpro file."""
    print("Attempting to fix")
    fixlist: List[FixFile] = []
    tempbuf = BytesIO()
    with ZipFile(projfilestr, mode="r") as projfile:
        fix_program_prj(projfile, found_errors, fixlist)
        with ZipFile(tempbuf, mode="w") as fixfile:
            for info in projfile.infolist():
                fix = in_fixlist(info, fixlist)
                # Use fixlist filebuf contents for modified files
                if fix is not None:
                    fix.filebuf.seek(0)
                    fixfile.writestr(fix.infozip, fix.filebuf.read())
                # Pass unchanged files through to output zip
                else:
                    with projfile.open(info) as inputfile:
                        fixfile.writestr(info, inputfile.read())

            # If there are remaining fixlist items write them out
            for fix in fixlist:
                fix.filebuf.seek(0)
                fixfile.writestr(fix.infozip, fix.filebuf.read())

    with open(fixfilestr, "wb") as outfile:
        tempbuf.seek(0)
        outfile.write(MAGIC_NUM)
        outfile.write(tempbuf.read())


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
    parser.add_argument(
        "--fix",
        help=(
            "Attempt to fix errors, saving to a new file. Example --fix"
            " Fixed_Project.adpro"
        ),
    )
    args = parser.parse_args()
    logger.setLevel(args.loglevel.upper())

    result = 0

    found_errors = ProjErrors()
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

        result = project_check(task_names, node_names, rll_pairs, found_errors)

    if args.fix is not None and result != 0:
        fix_project(args.projfile, args.fix, found_errors)

    sys.exit(result)


if __name__ == "__main__":
    main()
