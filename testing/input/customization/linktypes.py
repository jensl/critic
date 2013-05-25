import linkify

class IssueLink(linkify.LinkType):
    def __init__(self):
        super(IssueLink, self).__init__("#[0-9]+")
    def linkify(self, word, context):
        return "https://issuetracker.example.com/showIssue?id=" + word[1:]

IssueLink()
