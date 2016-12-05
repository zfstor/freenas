# What is it?

ZFStor is a fork of FreeNAS 9.10.

# Why?

FreeNAS 9 is/was a stable product. FreeNAS 10 was a rewrite from the ground up and that made FreeNAS 9 lag behind. ZFStor is intended to keep the code base stable and at the same time evolve it to use latest versions of FreeBSD.

# Building ZFStor

* https://github.com/zfstor/build

To build the system (experts only):

## Requirements:

* Your build environment must be FreeBSD 12-CURRENT.

* an amd64 capable processor.  8GB of memory, or an equal/greater amount
  of swap space, is also required

* You will need the following ports/packages when compiling anything
  FreeNAS-related:
  * ports-mgmt/poudriere-devel
  * devel/git
  * devel/gmake
  * sysutils/cdrtools
  * archivers/pxz
  * lang/python3
  * sysutils/grub2-pcbsd
  * sysutils/xorriso
  * sysutils/grub2-efi
  * py27-sphinx
  * py27-sphinxcontrib-httpdomain-1.2.1
  (and all the dependencies that these ports/pkgs install, of course)

## Building the System Quickstart Flow:

* Checking out the code from git:

```
% cd /path/to/your-build-filesystem
% git clone https://github.com/zfstor/build
% cd build
```

* Build it

```
% make checkout
% make release
```

* Update the source tree, to pull in new source code changes

```
% make update
```

This will also fetch TrueOS and ports for the build from github.

## The End Result:

If your build completes successfully, you'll have 64 bit release products in
the release_stage directory.  You will also have a tarball in your build
directory containing the entire release for easy transport.
