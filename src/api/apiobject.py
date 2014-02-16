class APIObject(object):
    """Base class of all significant API classes

       Exposes the Critic session object as the read-only 'critic' attribute.

       Also holds the reference to the internal implementation object, which
       should only be used in the implementation of the API."""

    def __init__(self, critic, impl):
        self.__critic = critic
        self.__impl = impl

    @property
    def critic(self):
        """The Critic session object used to create the API object"""
        return self.__critic

    @property
    def _impl(self):
        """Underlying object implementation

           This value should not be used outside the implementation of
           the API."""
        return self.__impl

    def _set_impl(self, impl):
        """Set the underlying object implementation

           This method should not be called outside the implementation
           of the API."""
        self.__impl = impl
