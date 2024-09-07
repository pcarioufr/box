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

## Open a terminal in `The Box`

Alternatively, use the `box` with no further argument to open a terminal in the virtual machine.

```bash
$ ./box.sh 
me@box:~ *$*
```

## Alias `The Box` entry points

Run the `alias` command [on the host] to use `box` in lieu of `./box.sh`.

```bash
$ ./box.sh alias box=./box.sh
$ box hello
hello.sh::28 | hello world!
```

This alias persists as long as your terminal window/tab remains open.


# Customise `The Box`

## Bring you own scripts


The box comes with a starter pack, which consists of:

* a docker build folder - see [`starter-pack/build`](starter-pack/build),
* a home folder - see [`starter-pack/home`](starter-pack/home)
* some basic scripts - see [`starter-pack/opt`](starter-pack/opt)
* environment variables to set within the virtual machine - see see [`starter-pack/.env`](starter-pack/.env)

You may either customise the `starter-pack/` folder.

You may also point to another repository, updating the `BOX` variable in the [host.env](host.env) file. If you do so, and unless you update the [box.sh](box.sh) and [compose.yml](compose.yml) file, stick to the structure of the folder, most specifically:
* the docker build context should be in the `$BOX/build` folder
* the home folder should be in the `$BOX/home` folder
* the various scripts should be in `$BOX/opt` folder, with a `$BOX/opt/main` executable file that process box parameters and calls subsequent scripts.


## Bring you own data

The box may also include external data, mounted in the `/data` folder in the virtual machine - (see[compose.yml](compose.yml))

It defaults to `./data`, but you may update the `DATA` environment variable in [`box.sh`](box.sh) to point to another data folder on the host to be mounted in the virtual machine in `/data`. 

