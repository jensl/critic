API design
==========

Primary vs secondary resources
------------------------------

Accessed resources (objects) are classified as either "primary" or "secondary".

Primary resources are those that are directly addressable via some path, such as
users (/api/v1/users/1) or reviews (/api/v1/reviews/1), but also a users
individual registered email addresses (/api/v1/users/1/emails/1).  A primary
resource has a resource type that is simply the path component, i.e. "users",
"reviews" or "emails" for the resources mentioned in this paragraph.

A secondary resource is not directly addressable via a path and is only ever
returned as part of a primary resource.

A primary resource referenced by another primary resource is always included as
an id reference only, never expanded.  Such a referenced resource may, if
requested, still be included in the response, but then as a separate linked
resource.

Example:

  Users are primary resources, and are referenced by various fields in the a
  review resource, but only by id:

    /api/v1/reviews/1 => {

      "id": 1,
      "owners: [2, 3],
      "reviewers": [4, 5, 6],
      ...

    }

  The name+email+timestamp objects that represent the author and committer
  metadata in commits, OTOH, are secondary resources, and thus directly included
  in the commit resource that reference them:

    /api/v1/repository/1/commits/1 => {

      "id": 1,
      "author": { "name": "...",
                  "email": "...",
                  "timestamp": ... },
      "committer": { "name": "...",
                     "email": "...",
                     "timestamp": ... },

    }

This rule exists mostly to define a consistent answer to the question: "Should
resource X be included in resource Y?"

Referenced primary resource are not directly included because A) they are
generally convenient enough to access on their own, given an id, and B) can
always be included in the response anyway, as a linked resource.

Linked resources
----------------

Typically, any primary resource whose id is included as part of another primary
resource is recorded as a linked resource.  This includes the case of the other
primary resource also being "just" a linked resource, as long as that other
primary resource was actually going to be included in the final response.

Linked resources are included in the final response if requested via the
'include' query parameter.  Its value is a comma-separated list of resource
types.

Example:

  /api/v1/reviews/1?include=users => {

    "id": 1,
    "owners": [2, 3],
    "reviewers": [3, 4],
    ...

    "linked": { "users": [{ "id": 2,
                            "name": "...",
                            ... },
                          { "id": 3,
                            "name": "...",
                            ... },
                          { "id": 4,
                            "name": "...",
                            ... }] },

  }

Some references to primary resources do not cause the referenced resource to be
recorded as a linked resource.  One notable such exception is the references to
a commit's parent commits, since the recursive processing of linked resources
could easily cause a repository's entire history to be included.

Example:

  /api/v1/repositories/1/commits/1?include=commits => {

    "id": 1,
    "parents": [2, 3],
    ...

    "linked": {}

  }

Note that the exception here is the commit resource's 'parents' field, not
commits in general.  Other resources that include lists of commit reference do
record them as linked resources.

Example:

  /api/v1/reviews/1?include=commits => {

    "id": 1,
    "commits": [1, 2, 3],
    ...

    "linked": { "commits": [{ "id": 1,
                              "parents": [2],
                              ... },
                            { "id": 2,
                              "parents": [3],
                              ... },
                            { "id": 3,
                              "parents": [4],
                              ... }] }
  }

  Note: In this scenario, commits 1-3 are included since they are directly
        referenced from the review resource, but commit 4, which is referenced
        from commit 3's 'parents' field, is not included.

Collections
-----------

Primary resources can also typically be accessed as collections, normally via a
path that doesn't include the final component that identifies the specific
resource.

A collection of primary resources is returned as an object with a single key,
the resource type, mapped to an array of resources.

Example:

  /api/v1/users => {

    "users": [{ "id": 1,
                "name": "...",
                ... },
              { "id": 2,
                "name": "...",
                ... },
              ...]

  }

The top-level { resource_type: collection } structure is there to make it
possible to also include linked resources as part of the top-level structure.
This would not be possible if the top-level structure was an array, for
instance.


Implementation
==============

A primary resource is implemented by decorating a class with the decorator
|jsonapi.PrimaryResource|, as such:

  class User(object):
    """Internal representation"""
    def __init__(self, name):
      self.name = name

  @jsonapi.PrimaryResource
  class Users(object):
    name = "apples"
    value_class = User

    @staticmethod
    def json(value, parameters, linked):
      return { "name": value.name }

    @staticmethod
    def single(critic, argument, parameters):
      return User(argument)

    @staticmethod
    def multiple(critic, parameters):
      return [User("alice"), User("bob")]

A resource class is never instantiated; it is only expected to have class
attributes and static (or class) methods.  Two attributes are required: |name|
and |value_class|.

In addition, these attributes are used if present: |contexts| and |exceptions|.

name
----
The resource name (typically plural) as it appears in the path.  This defines
the paths that this resource class handles.

If the |name| attribute is "users", the resource class handles the path
/api/v1/users/, unless the |contexts| attribute is present and overrides this
(see below).

value_class
-----------
The internal type of the values being "wrapped".

contexts
--------
The optional |contexts| attribute should be a tuple containing strings or the
special value None.  If it contains None, the resource can appear without
context, meaning at the beginning of a path.  If it contains strings, those
strings should match the name of other primary resources, and the meaning is
that this resource can occur following that other resource on a path.

exceptions
----------
The optional |exceptions| attribute should be a tuple containing exception
types that the resource class's methods can raise and have converted into
PathError exceptions.

json()
------
The json() method is called to convert an instance of the resource class's
internal value class to a simple data structure (typically a dictionary) that
can then be converted into a JSON string.  It must be implemented.

The |value| parameter is the value being converted.  It is guaranteed to be an
instance of the resource class's internal value class.

The |parameters| parameter gives access to query string parameters, and to
context objects introduced by earlier path segments (all but the last).

The |linked| parameter holds an object that can be used to register other
primary resources referenced by this resource.

single()
--------
The single() method is called when processing a path

  .../<resource name>/<argument>

where <resource name> is the resource class's |name| attribute and <argument> is
the |argument| parameter to the method.  If the single() method is not
implemented, this type of path is invalid.

The |critic| parameter is an api.critic.Critic instance.

The |argument| parameter is the next path component, as described above.

The |parameters| parameter is the same as to json().

The return value must be an instance of the resource class's internal value
class.

multiple()
----------
The multiple() method is called when processing a path

  .../<resource name>

and would normally return "all resources of this type."  It can also filter its
return value using query parameters.  If the multiple() method is not
implemented, this type of path is invalid.

The |critic| and |parameters| parameters are the same as to single().

The return value must be an iterable of the resource class's internal value
class, or an instance of it.  The return value can be an iterator or generator.
