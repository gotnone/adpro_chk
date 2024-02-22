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
import datetime
import logging
import sys
from dataclasses import dataclass, field
from io import BytesIO
from typing import IO, AnyStr, BinaryIO, Callable, Final, List, Set
from zipfile import ZipFile, ZipInfo

import lxml.etree as ET

DUP_NODE: Final[int] = 1
DUP_TASK: Final[int] = 1 << 1
DUP_PGM: Final[int] = 1 << 2
MISSING_NODE: Final[int] = 1 << 3
MISSING_TASK: Final[int] = 1 << 4
MISSING_PGM: Final[int] = 1 << 5
CORRUPT_XML: Final[int] = 1 << 24
CORRUPT_PROGRAM_PRJ: Final[int] = 1 << 25
CORRUPT_PGMFILE: Final[int] = 1 << 26
MISSING_PGMNAME: Final[int] = 1 << 27
MISSING_TASKNUM: Final[int] = 1 << 28
MISSING_VALUE: Final[int] = 1 << 29
MISSING_KEY: Final[int] = 1 << 30

MAGIC_NUM: Final[bytes] = b"\xad\xc0\x30\x00"

NSMAP: Final[dict] = {
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

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


def max_tasknumber(tasks: List[ET._Element]):
    """Function for finding the maximum tasknumber of a given Element."""
    return max(
        (int(i) for i in (t.findtext("./taskNumber") for t in tasks) if i is not None)
    )


def next_number_clsr(basefunc: Callable, *args, **kwargs):
    """Closure to increment a base value derived from user supplied base function."""
    base = basefunc(*args, **kwargs)
    increment = 0

    def tasknumber():
        nonlocal base
        nonlocal increment
        return str(base + increment)

    def nexttasknumber():
        nonlocal increment
        increment += 1
        return tasknumber()

    return tasknumber, nexttasknumber


def max_tasknumber_clsr(tasks: List[ET._Element]):
    """Closure for incrementing the maximum tasknumber of a given Element."""
    return next_number_clsr(max_tasknumber, tasks)


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


def fix_task_duplicates(root: ET._Element, found_errors: ProjErrors):
    """Function to fix duplicate tasks."""
    for taskname in found_errors.duplicate_task:
        print(f"Attempting to fix duplicate task {taskname}")
        # Find all elements in <tasks> with <taskname> = taskname
        tasks = root.findall(f"./tasks/taskName/[.='{taskname}']")
        name, nextname = make_name_clsr(taskname)
        for t in tasks[1:]:
            t.text = nextname()
            if name() not in found_errors.renamed_node:
                found_errors.missing_node.add(name())
            if name() not in [n.taskname for n in found_errors.renamed_pgm]:
                found_errors.missing_pgm.add(name())
            print(f"Renamed task {taskname} duplicate to {name()}")


def fix_node_duplicates(root: ET._Element, found_errors: ProjErrors):
    """Function to fix duplicate nodes."""
    for nodename in found_errors.duplicate_node:
        print(f"Attempting to fix duplicate node {nodename}")
        # Find all elements in <paths> which have <folder> = false with
        # tag name <nodeName> = nodename
        nodes = root.findall(f".//paths/[folder='false']/[nodeName='{nodename}']")
        name, nextname = make_name_clsr(nodename)
        for n in nodes[1:]:
            n.text = nextname()
            if name() not in found_errors.renamed_task:
                found_errors.missing_task.add(name())
            if name() not in [n.taskname for n in found_errors.renamed_pgm]:
                found_errors.missing_pgm.add(name())
            print(f"Renamed node {nodename} duplicate to {name()}")


def fix_pgm_duplicates(
    projfile: ZipFile, found_errors: ProjErrors, fixlist: List[FixFile]
):
    """Function to fix duplicate task programs."""
    logger = logging.getLogger(__name__)

    for pgmpair in found_errors.renamed_pgm:
        print(f"Attempting to fix duplicate task program {pgmpair.infozip.filename}")
        # Find all elements with tag name <NodeName>
        tree: ET._ElementTree
        with projfile.open(pgmpair.infozip, mode="r") as pgmfile:
            tree = ET.parse(pgmfile)
        if tree is None:
            logger.error(
                "Program Abort\nUnable to parse task program %s",
                pgmpair.infozip.filename,
            )
            sys.exit(CORRUPT_PGMFILE)
        root = tree.getroot()
        # Find all elements with tag name <pgmName>
        pgm = root.find("./pgmName")
        if pgm is not None:
            before = pgm.text
            pgm.text = pgmpair.taskname
            print(f"Renamed node {before} duplicate to {pgmpair.taskname}")
            fixlist.append(FixFile(pgmpair.infozip, BytesIO()))
            write_tree(tree, fixlist[-1].filebuf)


def make_timestamp():
    """Function to make timestamp in format expected by adpro file."""
    now = datetime.datetime.now().astimezone()
    return (
        now.strftime("%Y-%m-%dT%H:%M:%S.")
        + f"{int(now.microsecond /1000)}"
        + now.strftime("%z")
    )


def make_task_element(taskname: str, tasknumber: str, taskseqnum: str):
    """Create a new tasks element."""
    # pylint: disable=line-too-long
    # This is an xml string
    xmlstr = f'<Project xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><tasks><author>adpro_chk</author><backgroundRGB>16777215</backgroundRGB><comment/><createTime>{make_timestamp()}</createTime><execOption>0</execOption><localTags><tags xsi:type="group"><type>java.util.ArrayList</type></tags></localTags><protection>false</protection><scanOption>0</scanOption><taskName>{taskname}</taskName><taskNumber>{tasknumber}</taskNumber><taskSeqNum>{taskseqnum}</taskSeqNum><taskType>0</taskType><wireRGB>0</wireRGB></tasks></Project>'
    tree = ET.fromstring(xmlstr)
    task = tree.find("./tasks")
    if task is not None:
        return task
    logger = logging.getLogger(__name__)
    logger.error("Program Abort\nUnable to parse XML in make_task_element()")
    sys.exit(CORRUPT_XML)


def fix_task_missing(root: ET._Element, found_errors: ProjErrors):
    """Function to fix missing tasks."""
    logger = logging.getLogger(__name__)

    # Find all tasks
    tasks = root.findall("./tasks")
    _, nexttasknumber = max_tasknumber_clsr(tasks)

    for taskname in found_errors.missing_task:
        print(f"Attempting to fix missing task {taskname}")
        task = make_task_element(taskname, nexttasknumber(), "0")
        # Since we are placing the new task at taskSeqNum = 0, we increment
        # the taskSeqNum for all the other tasks
        for t in tasks:
            taskseqnum = t.find("./taskSeqNum")
            if taskseqnum is None or taskseqnum.text is None:
                logger.error(
                    "Program Abort\nUnable to increment '<taskSeqNum>' for %s",
                    t.findtext("./taskName"),
                )
                sys.exit(MISSING_TASKNUM)
            taskseqnum.text = str(int(taskseqnum.text) + 1)
        root.append(task)


def make_paths_element(nodename: str):
    """Create a new paths element."""
    # pylint: disable=line-too-long
    # This is an xml string
    xmlstr = f"<value><paths><folder>false</folder><nodeName>{nodename}</nodeName><path>~Project~Tasks~Run Every Scan~</path></paths></value>"
    tree = ET.fromstring(xmlstr)
    paths = tree.find("paths")
    if paths is not None:
        return paths
    logger = logging.getLogger(__name__)
    logger.error("Program Abort\nUnable to parse XML in make_paths_element()")
    sys.exit(CORRUPT_XML)


def fix_node_missing(root: ET._Element, found_errors: ProjErrors):
    """Function to fix missing nodes."""
    logger = logging.getLogger(__name__)

    for nodename in found_errors.missing_node:
        print(f"Attempting to fix missing node {nodename}")

        value = root.find("./projectTaskPaths/entry/[key='0']/value")
        if value is None:
            value = root.find("./projectTaskPaths/entry/../value")
            if value is None:
                logger.error(
                    "Program Abort\nUnable to find task path '<value>' element in XML"
                )
                sys.exit(MISSING_VALUE)
            key = value.find("../key")
            if key is None or key.text is None:
                logger.error(
                    "Program Abort\nUnable to find task path '<key>'"
                    " associated with '<value>' %s",
                    value.text,
                )
                sys.exit(MISSING_KEY)
            logger.warning(
                "New task path will be added to '<value>' with associate '<key>' %s",
                key.text,
            )
        paths = make_paths_element(nodename)
        value.insert(0, paths)


def fix_program_prj(
    projfile: ZipFile, found_errors: ProjErrors, fixlist: List[FixFile]
):
    """Function to fix errors in program.prj."""
    logger = logging.getLogger(__name__)
    tree: ET._ElementTree
    zipinfo = next((x for x in projfile.infolist() if x.filename == "program.prj"))
    if zipinfo is not None:
        logger.debug("Found zipinfo for program.prj %s", zipinfo)
        with projfile.open(zipinfo, mode="r") as program_prj:
            # Parse the xml file
            tree = ET.parse(program_prj)
        if tree is not None:
            root = tree.getroot()
            # placeholder for program.prj FileFix
            fixlist.append(FixFile(zipinfo, BytesIO()))
            fix_task_duplicates(root, found_errors)
            fix_node_duplicates(root, found_errors)
            fix_pgm_duplicates(projfile, found_errors, fixlist)
            fix_task_missing(root, found_errors)
            fix_node_missing(root, found_errors)

            write_tree(tree, fixlist[0].filebuf)


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
