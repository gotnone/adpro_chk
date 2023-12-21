# adpro_chk - Verify your Productivity Suite Project Files

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

## How to run
`adpro_chk your_productivity_project.adpro`

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
