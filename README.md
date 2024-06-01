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

Run the `alias` command [on the host] to use `box` in lieu of `./box.sh` - this alias persists as long as your terminal window/tab remains open.

```bash
$ ./box.sh alias box=./box.sh
$ box hello
hello.sh::28 | hello world!
```

### Launch scripts 

[`scripts/main.sh`](script/smain.sh) is expected to be the entry point (see [`box.sh`](box.sh) command line).
 
Use `box acme` (or `./box.sh acme` if you did not alias the `./box.sh` command) to launch `scripts/acme.sh` script.


### Open a terminal in `The Box`

Alternatively, use the `box` with no further argument to open a terminal in the virtual machine.


# Customise `The Box`


## Environment variables

Update the [`.env`](.env) file to pass environment variables to `The Box`.


## Bring your own scripts

Scripts are deployed in the `/opt/box` read-only folder in the virtual machine.
  
The scripts folder defaults to `./scripts`. Update the [`box.sh`](box.sh) file and its `SCRIPTS` environment variable to point to another scripts folder to be mounted in the virtual machine. If you do so, you may want to change the `/opt/box/main.sh` entrypoint in [`box.sh`](box.sh).


## External Data 

External data is deployed in the `/data` folder in the virtual machine. 

It defaults to `./data`. Update the [`box.sh`](box.sh) file and its `DATA` environment variable to point to another data folder to be mounted in the virtual machine.


## Home folder

The virtual machine home folder for the -default- `ubuntu` user (`/home/ubuntu`) is persisted on the docker host in the [`home/`](home/) repo.

Add anything you need there (scripts, .bashrc, ssh keys, etc.).


## Upgrade

See [`Dockerfile`](Dockerfile) to change the Ubuntu Version, packages installed, configuration files, etc. 


