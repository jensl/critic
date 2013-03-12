Critic
======

This is the code review system, Critic.

Critic has a few [concepts][concepts] that might be useful to know.

Installation
------------

To install Critic, run the script `install.py` as root:

    # python install.py

It will ask a number of questions and then perform the installation.

You should probably read the [INSTALL file][install] for all the information.


[install]: https://github.com/jensl/critic/blob/master/INSTALL
[concepts]: https://github.com/jensl/critic/blob/master/documentation/concepts.txt

Adding a repository
-------------------

After installing you should be able to navigate to the hostname you
specified during installtion and see Critic running.  When using the
administrator account you will also see 'Repositories' and 'Services'
as top level menu items, in addition to the usual menu items.  To add
a new repository, click the 'Repositories' menu item and then the
'Add Repository' button in the top right corner.

If Critic only has ssh access to the upstream of your repository, you must
set up the 'critic' system user (or whatever user name was chosen during
installation) to have ssh access without the need of a password.  You can do
that by creating an ssh key without a password and using 'ssh-copy-id' to
copy the key across to the server.  If you need to connect to the upstream
server using a different user name, you need to create a 'config' file in
the 'critic' system user's '.ssh' directory containing:

    Host <upstream-host-name>
    User <upstream-user-name>

Make sure to verify that you can access the repository from the 'critic'
user by running something like this:

    su -s /bin/bash -c "ssh -v <upstream-host-name>" critic

This should also ensure that the upstream server key is stored in the
'critic' user's 'known_hosts' file.

This needs only to be done once per upstream server.

Adding users
------------

If you are using the 'host' authentication system, users authenticated by
the web server will be added automatically to the Critic user database.  If
you are using the 'critic' authentication system you can use the 'critcctl'
tool to add users beyond the administrative user created by the install.py
script:

    sudo criticctl adduser

Only the users added with this method will be able to sign in to the system
when using the 'critic' authentication system.

Adding push rights
------------------

Before a user can push review branches to the newly created Critic repository
their system account must be a member of the 'critic' system group (or whatever
group name was chosen during installation).  In Debian/Ubuntu this can be done
using:

    usermod -a -G critic <user-who-wants-push-rights>

Setting up reviewers and requesting a review
--------------------------------------------

The developers responsible for performing the code review can subscribe
to new review requests either for a specific set of subdirectories or for
the entire source tree.  This configuration is done by each reviewer under
the 'Home' top level menu item.

For information about how to request a new code review, click the 'Tutorial'
top level menu item, and then select 'Requesting a Review'.

See also
--------

The [Critic user FAQ][faq] answers some common questions and gives some useful
tips on how to use Critic efficiently.

[faq]: https://github.com/jensl/critic/blob/master/documentation/user_faq.md
