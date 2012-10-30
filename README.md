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

Adding push rights
------------------

Before a user can push review branches to the newly created Critic repository
their account must be a member of the 'critic' Unix group (or whatever group
name was choosen during installtion).  In Debian/Ubuntu this can be done using:

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
