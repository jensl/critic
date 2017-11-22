# Installing Critic 2.0

Critic is primarily a Python (3.6+) package, installable using the `pip` tool.
This manual will assume that the Critic package is installed in a dedicated
virtual environment. This is not strictly required, but is generally a very good
idea.

As it is a somewhat complex system, Critic also depends on other non-Python
software and setup. Critic's management tool `criticctl` has sub-commands
("tasks") for taking care of all of that, but much of it can also be done
manually by the system administrator, if desired. This manual will go through
how to set the system up using the `criticctl` tool, however.

As this author has little experience working with non-Debian/Ubuntu Linux
systems, this manual, and in so far as it matters, the Critic system and its
tools, assume a Debian/Ubuntu system with `apt` package management.

## Step 0, prerequisites

Critic requires Python 3.6 or later. On a system where such a Python version is
installed, `/usr/bin/python3` or, more specifically, `/usr/bin/python3.6`, would
typically be it. Run

```
python3 --version
```

to check what version is installed. Also, the package `python3-venv` may need to
be installed to support creating virtual environments:

```
sudo apt install python3-venv
```

### Note on Ubuntu 16.04 LTS

The long-term support Ubuntu version 16.04 is typically (at the time of writing)
a good choice for setting up a production system. The Python 3 version that it
contains &mdash; Python 3.5 &mdash; is unfortunately too old to run Critic,
however.

There are surely various ways to solve this, none much more than a quick
Internet search away. A way used by this author is the following sequence of
commands:

```
sudo add-apt-repository ppa:jonathonf/python-3.6
sudo apt update
sudo apt install python3.6 python3.6-venv
```

Note that after this, `/usr/bin/python3` will still be the 3.5 version, so
`/usr/bin/python3.6` needs to be used explicitly (but actually only in "Step 2"
below.)

## Step 1: fetch Critic (optional)

Since Critic is available in the [Python package index][pypi] as the package
[critic-review][pypi_critic], it can be installed directly using `pip`. Another
option is to clone Critic's Git repository from [GitHub][github]:

```
git clone https://github.com/jensl/critic.git
```

or from the [official Critic system][critic_review]:

```
git clone https://critic-review.org/critic.git
```

Install Git first if needed. On Debian/Ubuntu, run:

```
sudo apt install git
```

Installing from a repository clone is mostly useful if a custom version of
Critic is to be installed.

## Step 2: creating a virtual environment

This is mostly standard Python procedure. It's worth noting that the location of
the virtual environment is used as Critic's "home directory" by default, and
thus selecting a suitable location for that purpose makes some sense. Reasonable
choices might be `/var/lib/critic` or perhaps `/opt/critic`. The former is
assumed in the rest of this manual, but the exact location is of no great
importance.

To create the virtual environment, run:

```
sudo python3 -m venv /var/lib/critic
```

After this, it's a good idea to ensure that the `pip` installed in the virtual
environment is up-to-date, and to install the `wheel` package to enable
installation of pre-built binary packages. To do this, run:

```
sudo -H /var/lib/critic/bin/pip install --upgrade pip wheel
```

## Step 3: install the Critic package

If "Step 1" was skipped, then simply run:

```
sudo -H /var/lib/critic/bin/pip install critic-review
```

otherwise, run:

```
sudo -H /var/lib/critic/bin/pip install /path/to/critic/
```

where `/path/to/critic/` should identify where you cloned Critic's Git
repository.

This step only installs Critic's Python code. The rest of the installation
procedure is a sequence of steps that configures various other parts of the
system to run this code.

## Step 4: basic installation

This step creates a system account and group used to run Critic and own various
files, initializes the PostgreSQL database, and writes Critic's (fairly simple)
configuration file. To do this with all the default settings, run:

```
sudo /var/lib/critic/bin/criticctl run-task install
```

For a list of possible variations, append `--help` to that command line. This
goes for all other uses of `criticctl` in this manual as well.

### Note about the database server

Critic only supports PostgreSQL databases. The default mode of operation is to
set up a PostgreSQL server running on the same system. When doing this, the
command above does all the necessary database configuration. The database server
can also run on a separate system. In this case, this server must be set up
manually to have an empty database, and a role with full control over this
database. The command above will connect to the database and create all required
database tables.

## Step 5: install `systemd` service

The Critic system has a number of background services that should be running at
all times. They can be started by running

```
sudo /var/lib/critic/bin/criticctl run_services
```

but since this needs to be done after every reboot, it is not recommended to
start them this way. A better approach is to have `systemd` do it. To configure
this, run:

```
sudo /var/lib/critic/bin/criticctl run-task install:systemd-service --start-service
```

After this, Critic's background services are managed automatically by `systemd`,
and can be controlled using `systemctl` as usual:

```
sudo systemctl (start|stop|restart|status) critic-main
```

Note: the service is called `critic-main` instead of just `critic` because
Critic supports running multiple versions (called "identities") against the same
database on the same system. "Main" is the name of the default identity. The
typical use-case for this is to run a newer development version as the service
`critic-dev`. Actually setting this up is beyond the scope of this manual,
however.

## Step 5: set up WSGI container

Critic's web front-end is a WSGI application, and thus needs a WSGI container to
run in. It is not very dependent on what container that is, but the only one
that is supported (as in "has been tested") and that `criticctl` can configure
is [`uWSGI`][uwsgi].

To configure this, run:

```
sudo /var/lib/critic/bin/criticctl run-task container:uwsgi --enable-app
```

### Note on Ubuntu 16.04 LTS

Since Ubuntu 16.04's default Python 3 package version is 3.5, this is also the
only Python 3 version that its `uwsgi-plugin-python3` package supports. Since
Critic requires Python 3.6, a suitable plugin for [`uWSGI`][uwsgi] needs to be
installed manually.

This sequence of commands does that:

```
sudo apt install python3.6-dev uuid-dev libcap-dev libpcre3-dev libssl-dev uwsgi-src
PYTHON=python3.6 uwsgi --build-plugin "/usr/src/uwsgi/plugins/python python36"
sudo mv python36_plugin.so /usr/lib/uwsgi/plugins/
```

## Step 6: set up HTTP(S) front-end

The WSGI container set up in the previous step is not configured to service HTTP
requests directly. Instead, it's intended to run behind a separate HTTP(S)
front-end. Here, `criticctl` supports two different options: [`nginx`][nginx]
and [`uWSGI`][uwsgi]. Both options work perfectly fine. It seems
[`nginx`][nginx] has slightly more advanced SSL support, if that matters.

To set up [`nginx`][nginx], run:

```
sudo /var/lib/critic/bin/criticctl run-task frontend:nginx --access-scheme (http|https|both) --enable-site
```

To set up [`uWSGI`][uwsgi], run:

```
sudo /var/lib/critic/bin/criticctl run-task frontend:uwsgi --access-scheme (http|https|both) --enable-app
```

The "access scheme" is the only required argument. It determines the style of
configuration installed, and should simply match the administrator's intentions.

### Access scheme: "http"

This configures the front-end server to listen at port 80. Naturally, this is
unencrypted, and is not recommended for any kind of production setup.

### Access scheme: "https"

This configures the front-end server to listen at ports 80 and 443. HTTP
requests at port 80 are simply redirected to HTTPS at port 443. This is the
recommended mode, but setting up HTTPS of course requires various extra steps to
actually produce a working SSL configuration.

### Access scheme: "both"

This also configures the front-end server to listen at ports 80 and 443, but
HTTP requests at port 80 are serviced directly. The client is not redirected to
HTTPS at port 443 unless authentication is involved, and thus plain-text
passwords or session cookies. All HTTPS requests at port 443 are serviced
directly, of course. (In other words, unauthenticated requests over HTTPS are
not redirected back to port 80.)

## Step 7: calibrate password hashing

Critic hashes passwords using the [`passlib`][passlib] Python package, and the
[`argon2`][argon2] password hash by default. Passwords are hashed a configurable
number of rounds. The number of rounds should be chosen so that it takes a
reasonable amount of time to hash a password: not so long that users have to
wait noticably when authenticating, but long enough to make brute-force password
hacking unfeasable. The number of rounds to use obviously depends heavily on the
hardware of the system running Critic, and should therefor be calibrated on it.

To do this, run:

```
sudo /var/lib/critic/bin/criticctl run-task calibrate-pwhash
```

By default, hashing is calibrated to take roughly a quarter of a second, but
this can be adjusted using the `--hash-time=NNN` command-line argument. The
`NNN` value is a floating-point number, e.g. `0.25` for the default setting.

This calibration can be repeated any number of times. Already hashed and stored
passwords are rehashed and updated when the users next sign in, if necessary.

## Step 8: create a user

This step is arguably optional, but the system is fairly useless unless there
are some users that can access the web UI.

To create a user, run:

```
sudo /var/lib/critic/bin/criticctl adduser --username XXX
```

There are other arguments that may be of interest; append `--help` to see a list
of them. If no password is given on the command-line, a reasonably secure one is
generated and printed.

### Matching system accounts

Depending on how the system will be used, it may be reasonable to also create
system accounts for the users of the system. Exactly how this is done is beyond
the scope of this manual; but it's basic UNIX system administration.

If users are to be allowed access to Critic's Git repositories over SSH, by
logging in to such system accounts, it's important that the Critic user names
(as set by the `--username` argument to `criticctl adduser` above) and the
system account names match exactly. Otherwise, Critic will not be able to map
repository accesses to Critic users, and will typically reject them.

### The administrator role

While not strictly necessary, it's typically recommended to have at least one
administrator user, who can perform various administration tasks via the web UI.
To create such a user, run the `criticctl adduser` command above with the added
argument `--role=administrator`, or run

```
sudo /var/lib/critic/bin/criticctl addrole --username XXX --role administrator
```

to assign the role to an existing user.

[pypi]: https://pypi.python.org/
[pypi_critic]: https://pypi.python.org/pypi/critic-review
[github]: https://github.com/jensl/critic
[critic_review]: https://critic-review.org/
[nginx]: https://www.nginx.org/
[uwsgi]: http://uwsgi-docs.readthedocs.io/en/latest/
[passlib]: https://pypi.python.org/pypi/passlib
[argon2]: https://en.wikipedia.org/wiki/Argon2
