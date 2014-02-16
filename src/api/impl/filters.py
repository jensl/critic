import api

class RepositoryFilter(object):
    def __init__(self, subject_id, filter_type, path, filter_id, repository_id,
                 delegate_string, repository=None):
        self.__subject_id = subject_id
        self.__subject = None
        self.type = filter_type
        self.path = path
        self.id = filter_id
        self.__repository_id = repository_id
        self.__repository = repository
        self.__delegate_string = delegate_string
        self.__delegates = None

    def getSubject(self, critic):
        if self.__subject is None:
            self.__subject = api.user.fetch(critic, user_id=self.__subject_id)
        return self.__subject

    def getRepository(self, critic):
        if self.__repository is None:
            self.__repository = api.repository.fetch(
                critic, repository_id=self.__repository_id)
        return self.__repository

    def getDelegates(self, critic):
        if self.__delegates is None:
            self.__delegates = frozenset(
                api.user.fetch(critic, name=name.strip())
                for name in filter(None, self.__delegate_string.split(",")))
        return self.__delegates

class ReviewFilter(object):
    def __init__(self, subject_id, filter_type, path, filter_id, review_id,
                 creator_id):
        self.__subject_id = subject_id
        self.__subject = None
        self.type = filter_type
        self.path = path
        self.id = filter_id
        self.__review_id = review_id
        self.__review = None
        self.__creator_id = creator_id
        self.__creator = None

    def getSubject(self, critic):
        if self.__subject is None:
            self.__subject = api.user.fetch(critic, user_id=self.__subject_id)
        return self.__subject

    def getReview(self, critic):
        if self.__review is None:
            self.__review = api.review.fetch(critic, review_id=self.__review_id)
        return self.__review

    def getCreator(self, critic):
        if self.__creator is None:
            self.__creator = api.user.fetch(critic, user_id=self.__creator_id)
        return self.__creator
