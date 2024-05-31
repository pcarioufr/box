# Overview

`The Box` is a Ubuntu virtual machine that runs within a docker container, in order to do stuff.

## Hello world!

Run the `alias` command to use `box` in lieu of `./box.sh` - this alias persists as long as your terminal window/tab remains open.

```bash
$ alias box=./box.sh
$ box hello -l french
hello.sh::28 | salut la compagnie
```

## Environment variables

Use the `.env` file to pass environment variables to `The Box`.


## Home folder

The virtual machine home folder for the -default- `ubuntu` user (`/home/ubuntu`) is persisted on the docker host in the `home/` repo.


# Customise `The Box`

## Upgrade

See `Dockerfile` to change the Ubuntu Version as well as packages installed for `The Box`. 


## Add your own scripts

To add scripts to the box, simply add them in the `scripts/` folder.

Use `box acme` (or `./box.sh acme` if you did not alias the `./box.sh` command) to launch `scripts/acme.sh` script.


### Logs

You may use following commands (see `libs/verbose.sh` file) to add fancy colored logs.
* `critical` -> dark red logs
* `error` -> red logs
* `warning` -> orange logs
* `notice` -> purple logs
* `info` -> cyan logs
* `success` -> green logs

Debug mode (`DEBUG=1` environment variable in `.env` file) adds: 
* `debug` -> grey logs
* a final debug line that tracks the execution time of the script


### Library of bash functions

Use the `libs/` repo to declare bash functions that would run across your scripts. See `libs/verbose.sh` for reference.
