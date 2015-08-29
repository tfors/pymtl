![PyMTL](docs/pymtl_logo.png)
==========================================================================

[![Build Status](https://travis-ci.org/cornell-brg/pymtl.svg?branch=master)](https://travis-ci.org/cornell-brg/pymtl)

PyMTL is an open-source, Python-based framework for multi-level hardware
modeling. It was introduced at MICRO-47 in December, 2014. Please note
that PyMTL is currently **alpha** software that is under active
development and documentation is currently quite sparse. We have recently
received funding from the National Science Foundation under [Award #1512937][1]
to improve PyMTL performance, documentation, and reference
models. Please stay tuned over the next few months.

 [1]: http://www.nsf.gov/awardsearch/showAward?AWD_ID=1512937

License
--------------------------------------------------------------------------

PyMTL is offered under the terms of the Open Source Initiative BSD
3-Clause License. More information about this license can be found here:

 - http://choosealicense.com/licenses/bsd-3-clause
 - http://opensource.org/licenses/BSD-3-Clause

Publications
--------------------------------------------------------------------------

If you use PyMTL in your research, please cite our [MICRO'15 paper][2]:

```
  @inproceedings{lockhart-pymtl-micro2014,
    title     = {PyMTL: A Unified Framework for Vertically Integrated
                 Computer Architecture Research},
    author    = {Derek Lockhart and Gary Zibrat and Christopher Batten},
    booktitle = {47th IEEE/ACM Int'l Symp. on Microarchitecture (MICRO)},
    month     = {Dec},
    year      = {2014},
    pages     = {280--292},
    doi       = {10.1109/MICRO.2014.50},
  }
```

 [2]: http://dx.doi.org/10.1109/MICRO.2014.50

Installation
--------------------------------------------------------------------------

PyMTL requires Python2.7 and has the following additional prerequisites:

 - verilator
 - git, Python headers, and libffi
 - virtualenv

The steps for installing these prerequisites and PyMTL on a fresh Ubuntu
distribution are shown below. They have been tested with Ubuntu Trusty
14.04.

### Install Verilator

[Verilator][3] is an open-source toolchain for compiling Verilog RTL
models into C++ simulators. PyMTL uses Verilator for both Verilog
translation and Verilog import. The following commands will build and
install Verilator from source:

```
  % sudo apt-get install git make autoconf g++ flex bison
  % mkdir -p ${HOME}/src
  % cd ${HOME}/src
  % wget http://www.veripool.org/ftp/verilator-3.876.tgz
  % tar -xzvf verilator-3.876
  % cd verilator-3.876
  % ./configure
  % make
  % sudo make install
  % export PYMTL_VERILATOR_INCLUDE_DIR="/usr/local/share/verilator/include"
```

The `PYMTL_VERILATOR_INCLUDE_DIR` environment variable is used to tell
PyMTL where to find the various Verilator source files when peforming
both Verilog translation and Verilog import.

 [3]: http://www.veripool.org/wiki/verilator

### Install git, Python headers, and libffi

We need to install the Python headers and libffi in order to be able to
install the cffi Python package. cffi provides an elegant way to call C
functions from Python, and PyMTL uses cffi to call C code generated by
Verilator. We will use git to grab the PyMTL source. The following
commands will install the appropriate packages:

```
  % sudo apt-get install git python-dev libffi-dev
```

### Install virtualenv

While not strictly necessary, we strongly recommend using [virtualenv][4]
to install PyMTL and the Python packages that PyMTL depends on.
virtualenv enables creating isolated Python environments. The following
commands will install virtualenv:

```
  % sudo apt-get install python-virtualenv
```

Now we can use the `virtualenv` command to create a new virtual
environment for PyMTL, and then we can use the corresponding `activate`
script to activate the new virtual environment:

```
  % mkdir ${HOME}/venvs
  % virtualenv --python=python2.7 ${HOME}/venvs/pymtl
  % source ${HOME}/venvs/pymtl/bin/activate
```

 [4]: https://virtualenv.pypa.io/en/latest/

### Install PyMTL

We can now use git to clone the PyMTL repo, and pip to install PyMTL and
its dependencies. Note that we use pip in editable mode so that we can
actively work in the PyMTL git repo.

```
  % mkdir -p ${HOME}/vc/git-hub/cornell-brg
  % cd ${HOME}/vc/git-hub/cornell-brg
  % git clone https://github.com/cornell-brg/pymtl.git
  % pip install --editable ./pymtl
```

Testing
--------------------------------------------------------------------------

Before running any tests, we first create a build directory inside the
PyMTL repo to hold any temporary files generated during simulation:

```
  % mkdir -p ${HOME}/vc/git-hub/cornell-brg/pymtl/build
  % cd ${HOME}/vc/git-hub/cornell-brg/pymtl/build
```

All Python simulation tests can be easily run using py.test (warning:
there are a lot of tests!):

```
  % py.test ..
```

The Verilog simulation tests are only executed if the `--test-verilog`
flag is provided. For Verilog testing to work, PyMTL requires that
Verilator is on your `PATH` and that the `PYMTL_VERILATOR_INCLUDE_DIR`
environment:

```
  % py.test .. --test-verilog
```

When you're done testing/developing, you can deactivate the virtualenv::

```
  % deactivate
```

