# Overview

`The Box` is a Ubuntu virtual machine that runs within a docker container.

Since `The Box` runs as a short-lived container, nothing that happens in the box is persisted - apart from its `home` folder. Which makes it a fully controlled and easily distributed working environment.

I personally use it as a dev-tool box (adding scripts that wrap terraform, ssh, etc.) commands. But it's also a convenient way to sandbox ubuntu stuff.


## Install Docker

If you don't have docker installed, I recommend [Docker Desktop](https://www.docker.com/products/docker-desktop/).


## Hello world!

Run the `alias` command [on the host] to use `box` in lieu of `./box.sh` - this alias persists as long as your terminal window/tab remains open.

```bash
$ alias box=./box.sh
$ box hello -l french
hello.sh::28 | salut la compagnie
```

## Add your own scripts

Add scripts to the box in the [`home/scripts/`](home/scripts/) folder.

Use `box acme` (or `./box.sh acme` if you did not alias the `./box.sh` command) to launch `scripts/acme.sh` script.


### Common functions for your `box` scripts 

The [`home/scripts/libs`](home/scripts/libs) is the folder where to declare functions that would run across your scripts (see the Logs section below for reference).

### Logs

Use following commands to add fancy colored logs.
* `critical` -> dark red logs
* `error` -> red logs
* `warning` -> orange logs
* `notice` -> purple logs
* `info` -> cyan logs
* `success` -> green logs

Debug mode (`DEBUG=1` environment variable in [`.env`](.env) file) adds: 
* `debug` -> grey logs
* a final debug line that tracks the execution time of the script


## Open a terminal in The Box

Alternatively, use the `box` (or `./box.sh` if you did not alias the `./box.sh` command) to open a terminal in the virtual machine.


# Customise `The Box`


## Environment variables

Update the [`.env`](.env) file to pass environment variables to `The Box`.


## External Data 

You can mount a read-only folder to access external data from within the virtual machine. It defaults to `./data`.

Update the [`box.sh`](box.sh) file and its `DATA` environment variable to point to another data folder to be mounted in the virtual machine.


## Home folder

The virtual machine home folder for the -default- `ubuntu` user (`/home/ubuntu`) is persisted on the docker host in the [`home/`](home/) repo.

Add anything you need there (scripts, .bashrc, ssh keys, etc.).


## Upgrade

See [`Dockerfile`](Dockerfile) to change the Ubuntu Version, packages installed, configuration files, etc. 


