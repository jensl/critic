Critic Testing Framework
========================

The Critic testing framework installs Critic in a VirtualBox instance, and then
runs tests against it.  Many assumptions are made about the setup of the
VirtualBox instance, the OS running in it, and the system running VirtualBox and
the testing framework.

In this manual, the system that runs VirtualBox and the testing framework is
called the "host" and the system running in VirtualBox is called the "guest".


Host Setup
----------

Required software:

* Python 2.7
* Git
* VirtualBox
* Requests (Debian/Ubuntu package: python-requests)
* BeautifulSoup 3.x (Debian/Ubuntu package: python-beautifulsoup)

The host system is assumed to have a clone of the Critic repository, in which
the testing framework is executed.  A temporary bare clone of this repository
will be created and exported using "git daemon" as part of testing.  By default,
this "git daemon" process listens on TCP port 9418, which will fail if another
"git daemon" process already runs on the host system.  If this is a problem, a
custom port can be specified using the --git-daemon-port command-line argument.

The user that runs the testing framework must have passwordless SSH access to
the guest system, and if a different user (name) should be used on the guest
system, this needs to be configured in .ssh/config.


VirtualBox Setup
----------------

The VirtualBox instance's SSH and HTTP services must be accessible (via network)
from the host system.  Its hostname must be given as command-line argument to
the testing framework, and custom ports for SSH and HTTP can also be given as
command-line arguments, if necessary.

If the VirtualBox instance is configured to use NAT, it is typically not
directly reachable from the host system.  In this case, ports on the host system
can be forwarded to the VirtualBox instance by VirtualBox, and "localhost" can
be used as the hostname.  The host system ports that are forwarded to the
VirtualBox instance can be given to the testing framework as command-line
arguments.

Finally, the VirtualBox instance must have a snapshot named "clean" (or named
something else if overidden using the --vm-snapshot argument.)  This snapshot is
restored when testing starts.  If the snapshot is taken with the machine powered
up and ready, testing will be slightly faster.  Critic should not have been
installed on the guest system at this point.  The software packages that
Critic's installation script installs if missing (Apache, PostgreSQL et c.) may
be installed before the snapshot is taken; this reduces the time it takes to run
tests, but of course means the software installation part of the installation
script is not fully tested.  For complete testing, two snapshots can be taken,
one with the additional software installed and one without, and tests can be run
once with each snapshot specified using the --vm-snapshot argument.

Important note: When taking a "live" snapshot of an instance, supplying the
"--pause" argument to the "VBoxManage snapshot" operation may be required to
avoid triggering bugs in VirtualBox that corrupts the instance.  Also note that
VirtualBox supports having multiple snapshots of the same instance with the same
name; make sure there's only one snapshot named "clean".


Guest Setup
-----------

Required software:

* SSH server
* Python 2.7
* Git
* Sudo

The user on the guest system that the host system user that runs the testing
framework logs in as over SSH must be allowed to run "sudo" without entering a
password.  (This is typically not the default in any system, unless the user is
"root", so /etc/sudoers typically needs to be edited to achieve this.)

The hostname "host" on the guest system must resolve to the host system.  This
can for instance be accomplished by editing the guest system's /etc/hosts file.

Critic will be installed on the guest system from the directory $HOME/critic,
which must not exist.  (IOW, the VirtualBox instance's "clean" snapshot must be
taken at a time when it doesn't exist.)


Running Tests
-------------

Tests are run in the clone of Critic's repository on the host system.  From the
root of that repository, run

    $ python -m testing.main ARGS

Two arguments are required,

    --vm-identifier=NAME|UUID

which specifies which VirtualBox instance to run the tests in, and

    --vm-hostname=HOSTNAME

which specifies how to address the VirtualBox instance from the host system.

Note: this hostname only needs to work on the host system, and need not be the
hostname that the guest OS has been configured with.

Also note: if both the host and guest OS:s use Avahi, the VirtualBox instance
might be accessible using the name "<hostname>.local" where <hostname> is the
hostname that the guest OS has been configured with.

The argument

    --vm-snapshot=NAME|UUID

can be used to select a snapshot to restore when starting the VirtualBox
instance.  A snapshot is always restored; if this argument is not provided, a
snapshot named "clean" is restored.

The arguments

    --vm-ssh-port=PORT
    --vm-http-port=PORT

can be used to tweak how the VirtualBox instance's SSH and HTTP services are
reached from the host system.

The argument

    --git-daemon-port=PORT

can be used to have the "git daemon" process that is automatically started to
export the Critic repository listen on a different port (by default it listens
on port 9418.)

The arguments

    --commit=SHA1|REF
    --upgrade-from=SHA1|REF

can be used to control which commit to test.  The --commit argument defaults to
the commit that is checked out in the non-bare repository on the host system.
Since this commit's version of the testing framework and the tests is what will
be running, it rarely makes any sense to specify any other commit.  Doing so
might not work as intended because of incompatibilities between the testing
framework in the checked out commit and the installed version of Critic.

The --upgrade-from argument is more useful.  When given, instead of installing
the tested commit directly, the commit specified by the --upgrade-from argument
is installed, and then the system is upgraded to the tested commit.  A typical
use-case for this is to test the changes on a topic branch by installing the
commit on 'master' from which the topic branch was branched off and then
upgrading to the tip of the topic branch, and then run the tests.

Note: The tested commit, as well as the commit to upgrade from, if given, must
not be earlier than the integration of the testing framework, since the
install.py and upgrade.py scripts were extended as part of the testing framework
implementation.

The arguments

    --debug
    --quiet

can be used to control the amount of output produced while running tests.  With
--debug, various rather noisy and not terribly useful debugging output is added.
With --quiet, only warnings and errors are output, not basic progress messages.
(With --quiet, a successful test run would produce no output at all.)

Finally, to run only selected tests, or groups of tests, the paths of these can
be provided as additional command-line arguments.  These paths should be
relative the testing/tests/ directory.

Test Structure
--------------

The actual tests are Python scripts in sub-directories of the testing/tests/
directory.  All file and directory names under testing/tests/ should, by
convention, begin with three digits, followed by a '-', followed by a short
identifier of the test or test group.  Files and directories are sorted
according to the three-digit number in their name, and processed in that order.
A directory is processed by processing all files and directories under it,
recursively.  A file whose name ends with ".py" is processed by executing it
(using execfile()).  All other files are ignored.

There should be no files directly in the testing/tests/ directory.  The
immediate sub-directories of testing/tests/ are "top-level test groups" and are
significant in that each one starts with a clean, restarted VirtualBox instance.
There should be a test (typically the first one) in each top-level test group
that calls "instance.install()" to install Critic in the VirtualBox instance,
and one test (possibly also the first one) that calls "instance.upgrade()" to
upgrade to the tested commit.  (The "instance.upgrade()" call is a no-op unless
the testing framework was started with the --upgrade-from argument.)

The organization of tests into test groups is mostly free, but there is one
detail worth noting: the directory tree layout implicitly defines dependencies
between tests, as such: a test B depends on a test A (IOW, test A must run
successfully in order for test B to be runnable) if test A runs before B (due to
the basic sorting described above) and is either in the top-level group or is in
an ancestor group of test B.

For instance, given the tests

    001-main/001-testA.py
    001-main/002-groupB/001-testB1.py
    001-main/002-groupB/002-testB2.py
    001-main/003-testC.py
    001-main/004-groupD/001-testD.py

the test 001-testA.py is a dependency of all other tests, and 003-testC.py is a
dependency of the test 004-groupD/001-testD.py, but the tests under 002-groupB/
are not dependencies of the tests 003-testC.py or 001-testD.py, despite normally
executing before them, and the test 001-testB1.py is not a dependency of the
test 001-testB2.py.
