# adpro_chk - Verify your Automation Direct Productivity Suite Project Files

If you hve been bitten by the [undo
fiasco](https://community.automationdirect.com/s/question/0D5PE000005sIWe0AM/productivity-suite-410-69-file-corruption)
and ended up with a corrupted .adpro file this may be the software for you.

Currently checks the adpro file for the following issues:

1. Zombie tasks that are missing from the Task Management List
2. Tasks that are in the Task Management List, but missing a `<tasks>` in the
   `program.prj` file
3. Tasks that are missing a corresponding `.rll` ladder program file
4. Tasks with a duplicate name in the Task Management List
5. Tasks with a duplicate name in the `<tasks>` sections of the `program.prj`
   file
6. Tasks with a duplicate name in the `tasks/*.rll` files

## Automatic Repair of Corrupt .adpro Files

Warning: This is extremely experimental *USE AT YOUR OWN RISK*.

Make sure that you are working on a backup of the corrupted .adpro file. The
repair functionality should make an in memory copy of the corrupted .adpro file
and manipulate that copy.  The authors of adpro_chk assume no liability for
your use of this experimental feature.

Using the command line option `--fix output_file_name.adpro` will attempt to
fix a corrupt file.

Currently implemented fixes:

- Duplicate Task Fix: This will rename a duplicate task, using the existing
  `<taskName>` and appending an `_1` or the next available integer.
- Duplicate Node Fix: This will rename a duplicate entry in the Task Management
  List, using the existing `<nodeName>` and appending `_1` or the next
  available integer.
- Duplicate Pgm Fix: This will rename a duplicate Task Program using the
  existing `<pgmName>` value and appending an `_1` or the next available integer.
- Missing Task Fix: This will attempt to create a `<tasks>` entry for a missing
  task.  This missing task condition can often occur as side effect of the
  duplicate node and pgm fixes.
- Missing Node Fix: This will attempt to create a `<paths>` entry for a missing
  entry in the Task Management List.  This missing node condition can often
  occur as a side effect of the duplicate task and pgm fixes.

## How to run

`adpro_chk your_productivity_project.adpro`

or

`adpro_chk your_productivity_project.adpro --fix your_fixed_project.adpro`

## Example Output

```console
$ adpro_chk.py Test_my_broken.adpro
Duplicated Task Entries:
Zone10SM_BC

Duplicated Pgm Entries:
Zone10SM_BC : 'task\T12.rll', 'task\T41.rll'
```

```console
$ adpro_chk.py A_Zombie_Task.adpro ; echo $?
Missing Task Manager Entry:
Zone10SM_BC

8
```

```console
$ adpro_chk.py Good_Project.adpro ; echo $?
0
```

```console
$ adpro_chk.py Test_my_broken.adpro --fix My_Fixed.adpro
Duplicated Task Entries:
Zone10SM_BC

Duplicated Pgm Entries:
Zone10SM_BC : 'task\T12.rll', 'task\T41.rll'

Attempting to fix
Attempting to fix duplicate task Zone10SM_BC
Renamed task Zone10SM_BC duplicate to Zone10SM_BC_1
Attempting to fix duplicate task program task\T41.rll
Renamed node Zone10SM_BC duplicate to Zone10SM_BC_1
Attempting to fix missing node Zone10SM_BC_1
```
