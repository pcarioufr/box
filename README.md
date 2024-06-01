# Overview

`The Box` is a Ubuntu virtual machine that runs within a docker container.

Since `The Box` runs as a short-lived container, nothing that happens in the box is persisted - apart from its `home` folder. Which makes it a fully controlled and easily distributed working environment.

I personally use it as a dev-tool box (adding scripts that wrap terraform, ssh, etc.) commands. But it's also a convenient way to sandbox ubuntu stuff.


## Install Docker

If you don't have docker installed, I recommend [Docker Desktop](https://www.docker.com/products/docker-desktop/).


## Hello world!

```bash
$ ./box.sh hello -l french
hello.sh::28 | salut la compagnie !
```

## `The Box` entry points

Run the `alias` command [on the host] to use `box` in lieu of `./box.sh`.

```bash
$ ./box.sh alias box=./box.sh
$ box hello
hello.sh::28 | hello world!
```

This alias persists as long as your terminal window/tab remains open.


### Launch scripts 

[`scripts/main.sh`](script/smain.sh) is expected to be the entry point (see [`box.sh`](box.sh) command line).
 
If you stick to default scripts (see [Bring your own scripts](#bring-your-own-scripts) section), use `box acme` to launch `scripts/acme.sh` script.


### Open a terminal in `The Box`

Alternatively, use the `box` with no further argument to open a terminal in the virtual machine.


# Customise `The Box`

## Home folder

The virtual machine home folder for the -default- `ubuntu` user (`/home/ubuntu`) is persisted on the docker host in the [`home/`](home/) repo.

Add anything you need there (scripts, .bashrc, ssh keys, etc.).


## Environment variables

Environment variables in the virtual machine are defined in a file on the host.

This files defaults to the [`.env`](.env). Edit its content, or update `ENV` environment variable in [`box.sh`](box.sh) to point to another environment variable file.


## Bring your own scripts

Scripts are deployed in the `/opt/box` read-only folder in the virtual machine.
  
The scripts folder defaults to `./scripts`. Edit its content, or update `SCRIPTS` environment variable in [`box.sh`](box.sh) to point to another scripts folder to be mounted in the virtual machine. If you do so, you may want to change the `/opt/box/main.sh` entrypoint in [`box.sh`](box.sh).


## External Data 

External data is deployed in the `/data` folder in the virtual machine. 

It defaults to `./data`. Edit its content, or update the `DATA` environment variable in [`box.sh`](box.sh) to point to another data folder to be mounted in the virtual machine.


## Upgrade

The definition of the virtual machine (the Ubuntu Version, the packages installed, etc.) is defined through a build folder with a `Dockerfile`.

It defaults to [`./build`](./build). Edit its content, or update `BUILD` environment variable in [`box.sh`](box.sh) to point to another build folder.
