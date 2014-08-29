import os
import re
import pprint

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

BASE = "100-reviewing/"
TEST = BASE + "001-comment"
BRANCH = "r/" + TEST
FILENAME = TEST + ".txt"
SUMMARY = "Added " + FILENAME

NEW_SUBJECT = "New Review: " + SUMMARY
NEWISH_SUBJECT = r"New\(ish\) Review: " + SUMMARY
UPDATED_SUBJECT = "Updated Review: " + SUMMARY

LINES = ["First line",
         "Second line",
         "Third line",
         "Fourth line",
         "Fifth line",
         "Sixth line",
         "Seventh line",
         "Eighth line",
         "Ninth line",
         "Tenth line"]

################################################################################
#
# Some utility stuff.
#
################################################################################

class CommentChain(object):
    def __init__(self, chain_id, chain_type, author, text, lines=None):
        self.id = chain_id
        self.type = chain_type
        self.author = author
        self.text = text
        self.lines = lines
        self.replies = []

    def add_reply(self, author):
        self.replies.append((author, ("This is a reply from %s."
                                      % author.capitalize())))

def findChainInMail(mail, chain_id):
    chain_type = author = text = lines = trailer = reply_author = None
    replies = []
    last_comment_seen = False

    first_line_index = None

    for index, line in enumerate(mail + [None]):
        if last_comment_seen:
            if line is None or line:
                del mail[first_line_index:index]
                return chain_type, author, text, lines, replies, trailer

        if not line:
            continue

        match = re.match("(?:> )?General (issue|note)", line)
        if match:
            chain_type = "general " + match.group(1)
            continue

        match = re.match("(?:> )?(Issue|Note) in commit", line)
        if match:
            chain_type = "commit " + match.group(1).lower()
            continue

        match = re.match("(?:> )?(Issue|Note) in", line)
        if match:
            chain_type = "file " + match.group(1).lower()
            continue

        if chain_type is None:
            continue

        match = re.match(r"(?:> )?  http://.*/showcomment\?chain=(\d+)", line)
        if match:
            first_line_index = index - 1
            if int(match.group(1)) != chain_id:
                chain_type = None
            continue

        match = re.match("(?:> )?([^ ]+) von Testing at", line)
        if match:
            if author is None:
                author = match.group(1).lower()
            else:
                reply_author = match.group(1).lower()
            continue

        if re.match(r"(?:> )?-+$", line):
            if lines is None and not chain_type.startswith("general "):
                lines = []
            continue

        if lines is not None and author is None:
            if chain_type.startswith("file "):
                match = re.match(r"(?:> )?\s*(\d+)\|(.*)$", line)
                lines.append((int(match.group(1)), match.group(2)))
            else:
                match = re.match(r"(?:> )?  (.*)$", line)
                lines.append((None, match.group(1)))
            continue

        if line and (line.lower() != line == line.upper() or
                     re.match(r"\(.*\)", line)):
            trailer = line
            last_comment_seen = True
            continue

        match = re.match(r"(> )?  (.+)$", line)
        last_comment_seen = match.group(1) is None
        if reply_author:
            replies.append((reply_author, match.group(2)))
        else:
            text = match.group(2)

    testing.expect.check("<chain %d in mail>" % chain_id,
                         "<expected content not found>")

def checkSubmitter(mails, expected_submitter):
    for mail in mails:
        for line in mail:
            match = re.match("(.*) von Testing has submitted", line)
            if match:
                testing.expect.check(expected_submitter, match.group(1).lower())
                return

        testing.expect.check("<'$USER has submitted' line in mail>",
                             "<expected content not found>")

def checkChain(mails, chain, expected_trailer=None):
    for mail in mails:
        (actual_type, actual_author,
         actual_text, actual_lines,
         actual_replies, actual_trailer) = findChainInMail(mail, chain.id)

        testing.expect.check(chain.type, actual_type)
        testing.expect.check(chain.author, actual_author)
        testing.expect.check(chain.text, actual_text)
        testing.expect.check(chain.lines, actual_lines)
        testing.expect.check(chain.replies, actual_replies)

def checkNoMoreChains(mails):
    for mail in mails:
        for index, line in enumerate(mail):
            if re.match("(?:> )?General (issue|note)", line) \
                    or re.match("(?:> )?(Issue|Note) in commit", line) \
                    or re.match("(?:> )?(Issue|Note) in", line):
                testing.logger.error(
                    "Unexpected comment chain mentioned in mail:\n  %s\n  %s"
                    % (mail[index], mail[index + 1]))

def receiveMails(subject):
    return [mailbox.pop(accept=[to(whom), about(subject)]).lines[:]
            for whom in ["alice", "bob", "dave", "erin"]]

def createComment(chain, author):
    frontend.operation(
        "createcomment",
        data={ "chain_id": chain.id,
               "text": "This is a reply from %s." % author.capitalize() })

def resolveCommentChain(chain):
    frontend.operation(
        "resolvecommentchain",
        data={ "chain_id": chain.id })

def reopenResolvedCommentChain(chain):
    frontend.operation(
        "reopenresolvedcommentchain",
        data={ "chain_id": chain.id })

def morphCommentChain(chain, new_type):
    frontend.operation(
        "morphcommentchain",
        data={ "chain_id": chain.id,
               "new_type": new_type })

def submitChanges():
    if instance.has_flag("fixed-batch-preview"):
        frontend.page(
            "showbatch",
            params={ "review": str(review_id) })

    result = frontend.operation(
        "submitchanges",
        data={ "review_id": review_id })

    if "batch_id" in result:
        frontend.page(
            "showbatch",
            params={ "batch": result["batch_id"] })

with repository.workcopy() as work:
    ############################################################################
    #
    # As Alice, create a commit that adds a file, and a review of that commit,
    # with Bob, Dave and Erin as associated users.
    #
    ############################################################################

    REMOTE_URL = "alice@%s:/var/git/critic.git" % instance.hostname

    parent_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    work.run(["checkout", "-b", BRANCH, "--no-track", "origin/master"])

    os.mkdir(os.path.join(work.path, "100-reviewing"))

    with open(os.path.join(work.path, FILENAME), "w") as review_file:
        review_file.write("\n".join(LINES) + "\n")

    work.run(["add", FILENAME])
    work.run(["commit", "-m", "\n".join([SUMMARY, ""] + LINES[:3])])

    child_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    review_id = testing.utils.createReviewViaPush(work, "alice")

    mailbox.pop(accept=[to("alice"), about(NEW_SUBJECT)])

    with frontend.signin("alice"):
        frontend.operation(
            "addreviewfilters",
            data={ "review_id": review_id,
                   "filters": [{ "type": "reviewer",
                                 "user_names": ["bob"],
                                 "paths": [BASE] },
                               { "type": "watcher",
                                 "user_names": ["dave"],
                                 "paths": ["/"] },
                               { "type": "watcher",
                                 "user_names": ["erin"],
                                 "paths": ["src/"] }]})

        for whom in ["bob", "dave", "erin"]:
            mailbox.pop(accept=[to(whom), about(NEWISH_SUBJECT)])
            mailbox.pop(accept=[to(whom), about(UPDATED_SUBJECT)])

    ############################################################################
    #
    # Create one each of the different types of comment chain:
    #   { general, commit, file } x { issue, note}
    #
    # Submit, and check that everyone involved received a mail with each comment
    # chain included (and correctly rendered.)
    #
    ############################################################################

    with frontend.signin("alice"):
        result = frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "issue",
                   "text": "This is a general issue." })

        general_issue = CommentChain(
            chain_id=result["chain_id"],
            chain_type="general issue",
            author="alice",
            text="This is a general issue.")

        result = frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "text": "This is a general note." })

        general_note = CommentChain(
            chain_id=result["chain_id"],
            chain_type="general note",
            author="alice",
            text="This is a general note.")

        result = frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "issue",
                   "commit_context": { "commit": child_sha1,
                                       "offset": 0,
                                       "count": 3 },
                   "text": "This is a commit issue." })

        commit_issue = CommentChain(
            chain_id=result["chain_id"],
            chain_type="commit issue",
            author="alice",
            text="This is a commit issue.",
            lines=[(None, SUMMARY),
                   (None, ""),
                   (None, "First line")])

        result = frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "commit_context": { "commit": child_sha1,
                                       "offset": 4,
                                       "count": 1 },
                   "text": "This is a commit note." })

        commit_note = CommentChain(
            chain_id=result["chain_id"],
            chain_type="commit note",
            author="alice",
            text="This is a commit note.",
            lines=[(None, "Third line")])

        result = frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "issue",
                   "file_context": { "origin": "new",
                                     "parent": parent_sha1,
                                     "child": child_sha1,
                                     "file": FILENAME,
                                     "offset": 2,
                                     "count": 3 },
                   "text": "This is a file issue." })

        file_issue = CommentChain(
            chain_id=result["chain_id"],
            chain_type="file issue",
            author="alice",
            text="This is a file issue.",
            lines=[(2, "Second line"),
                   (3, "Third line"),
                   (4, "Fourth line")])

        result = frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "file_context": { "origin": "new",
                                     "parent": parent_sha1,
                                     "child": child_sha1,
                                     "file": FILENAME,
                                     "offset": 10,
                                     "count": 1 },
                   "text": "This is a file note." })

        file_note = CommentChain(
            chain_id=result["chain_id"],
            chain_type="file note",
            author="alice",
            text="This is a file note.",
            lines=[(10, "Tenth line")])

        testing.expect.check(6, result["draft_status"]["writtenComments"])

        submitChanges()

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "alice")
    checkChain(mails, general_issue)
    checkChain(mails, general_note)
    checkChain(mails, commit_issue)
    checkChain(mails, commit_note)
    checkChain(mails, file_issue)
    checkChain(mails, file_note)
    checkNoMoreChains(mails)

    ############################################################################
    #
    # Verify that we have some basic correctness checks on comment creation,
    # such as the commented lines existing.
    #
    ############################################################################

    with frontend.signin("alice"):
        # These don't work since the comment text is empty or contains only
        # white-space characters.
        for text in ("", " ", "\t", "\n", "\r"):
            frontend.operation(
                "createcommentchain",
                data={ "review_id": review_id,
                       "chain_type": "note",
                       "commit_context": { "commit": parent_sha1,
                                           "offset": 0,
                                           "count": 1 },
                       "text": text },
                expect={ "status": "failure",
                         "title": "Empty comment!" })

        # These don't work since we're trying to comment lines that don't
        # exist in the commit message.  (We tried offset=4/count=1 above.)
        frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "commit_context": { "commit": child_sha1,
                                       "offset": 5,
                                       "count": 1 },
                   "text": "This won't stick." },
            expect={ "status": "failure",
                     "message": "It's not possible to create a comment here." })
        frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "commit_context": { "commit": child_sha1,
                                       "offset": 4,
                                       "count": 2 },
                   "text": "This won't stick." },
            expect={ "status": "failure",
                     "message": "It's not possible to create a comment here." })

        # This doesn't work since we're trying to comment the "old" side of the
        # commit that added the commented file.
        frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "file_context": { "origin": "old",
                                     "parent": parent_sha1,
                                     "child": child_sha1,
                                     "file": FILENAME,
                                     "offset": 3,
                                     "count": 3 },
                   "text": "This won't stick." },
            expect={ "status": "failure",
                     "message": "It's not possible to create a comment here." })

        # These don't work, since we're trying to comment lines that don't
        # exist in the file.  (We tried offset=10/count=1 above.)
        frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "file_context": { "origin": "old",
                                     "parent": parent_sha1,
                                     "child": child_sha1,
                                     "file": FILENAME,
                                     "offset": 11,
                                     "count": 1 },
                   "text": "This won't stick." },
            expect={ "status": "failure",
                     "message": "It's not possible to create a comment here." })
        frontend.operation(
            "createcommentchain",
            data={ "review_id": review_id,
                   "chain_type": "note",
                   "file_context": { "origin": "old",
                                     "parent": parent_sha1,
                                     "child": child_sha1,
                                     "file": FILENAME,
                                     "offset": 10,
                                     "count": 2 },
                   "text": "This won't stick." },
            expect={ "status": "failure",
                     "message": "It's not possible to create a comment here." })

    ############################################################################
    #
    # Reply to some of the comment chains, and morph, resolve and reopen them,
    # as multiple users.
    #
    ############################################################################

    # Bob replies to some issues, but before he submits, Dave also replies to
    # one of them, and submits.  Checks that Dave's reply appears before Bob's,
    # even though Bob created his first.

    with frontend.signin("bob"):
        createComment(general_issue, "bob")
        createComment(commit_issue, "bob")
        createComment(file_issue, "bob")

    with frontend.signin("dave"):
        createComment(general_issue, "dave")
        submitChanges()

        general_issue.add_reply("dave")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "dave")
    checkChain(mails, general_issue)
    checkNoMoreChains(mails)

    with frontend.signin("bob"):
        submitChanges()

        general_issue.add_reply("bob")
        commit_issue.add_reply("bob")
        file_issue.add_reply("bob")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "bob")
    checkChain(mails, general_issue)
    checkChain(mails, commit_issue)
    checkChain(mails, file_issue)
    checkNoMoreChains(mails)

    # Erin replies to an issue too.

    with frontend.signin("erin"):
        createComment(commit_issue, "erin")
        submitChanges()

        commit_issue.add_reply("erin")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "erin")
    checkChain(mails, commit_issue)
    checkNoMoreChains(mails)

    # Alice replies to the general note and converts it to an issue (in the same
    # batch.)

    with frontend.signin("alice"):
        createComment(general_note, "alice")
        morphCommentChain(general_note, "issue")
        submitChanges()

        general_note.add_reply("alice")
        general_note.type = "general issue"

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "alice")
    checkChain(mails, general_note, "CONVERTED TO ISSUE!")
    checkNoMoreChains(mails)

    # Alice converts the general note back to a note, without replying.

    with frontend.signin("alice"):
        morphCommentChain(general_note, "note")
        submitChanges()

        general_note.type = "general note"

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "alice")
    checkChain(mails, general_note, "CONVERTED TO NOTE!")
    checkNoMoreChains(mails)

    # Bob replies to and converts the general note to an issue, but before he
    # submits, Dave also converts it to an issue and submits.  Checks that Bob's
    # converting of the issue has no effect, but his reply remains.

    with frontend.signin("bob"):
        createComment(general_note, "bob")
        morphCommentChain(general_note, "issue")

    with frontend.signin("dave"):
        morphCommentChain(general_note, "issue")
        submitChanges()

        general_note.type = "general issue"

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "dave")
    checkChain(mails, general_note, "CONVERTED TO ISSUE!")
    checkNoMoreChains(mails)

    with frontend.signin("bob"):
        submitChanges()

        general_note.add_reply("bob")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "bob")
    checkChain(mails, general_note)
    checkNoMoreChains(mails)

    # Alice resolves the general issue.

    with frontend.signin("alice"):
        resolveCommentChain(general_issue)
        submitChanges()

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "alice")
    checkChain(mails, general_issue, "ISSUE RESOLVED!")
    checkNoMoreChains(mails)

    # Erin replies to the now resolved general issue.

    with frontend.signin("erin"):
        createComment(general_issue, "erin")
        submitChanges()

        general_issue.add_reply("erin")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "erin")
    checkChain(mails, general_issue, "(This issue is resolved.)")
    checkNoMoreChains(mails)

    # Alice replies to and reopens the general issue, but before she submits,
    # Bob also replies to and reopens it, and submits.  Checks that Alice's
    # reopening of the issue has no effect, but her reply remains.

    with frontend.signin("alice"):
        createComment(general_issue, "alice")
        reopenResolvedCommentChain(general_issue)

    with frontend.signin("bob"):
        createComment(general_issue, "bob")
        reopenResolvedCommentChain(general_issue)
        submitChanges()

        general_issue.add_reply("bob")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "bob")
    checkChain(mails, general_issue, "ISSUE REOPENED!")
    checkNoMoreChains(mails)

    with frontend.signin("alice"):
        submitChanges()

        general_issue.add_reply("alice")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "alice")
    checkChain(mails, general_issue)
    checkNoMoreChains(mails)

    # Alice replies to and resolved the commit issue, as does Dave, but before
    # either submit, Bob swoops in and converts the issue to a note, and
    # submits.  Then Alice submits, which checks (again) that her resolving of
    # the issue has no effect, but her reply remains.  Then Bob converts the
    # issue back to an issue, and submits.  Finally, Dave submits, which checks
    # that his (old) resolving of the issue still remains and takes effect.

    with frontend.signin("alice"):
        createComment(commit_issue, "alice")
        resolveCommentChain(commit_issue)

    with frontend.signin("dave"):
        resolveCommentChain(commit_issue)

    with frontend.signin("bob"):
        morphCommentChain(commit_issue, "note")
        submitChanges()

        commit_issue.type = "commit note"

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "bob")
    checkChain(mails, commit_issue, "CONVERTED TO NOTE!")
    checkNoMoreChains(mails)

    with frontend.signin("alice"):
        submitChanges()

        commit_issue.add_reply("alice")

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "alice")
    checkChain(mails, commit_issue)
    checkNoMoreChains(mails)

    with frontend.signin("bob"):
        morphCommentChain(commit_issue, "issue")
        submitChanges()

        commit_issue.type = "commit issue"

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "bob")
    checkChain(mails, commit_issue, "CONVERTED TO ISSUE!")
    checkNoMoreChains(mails)

    with frontend.signin("dave"):
        submitChanges()

    mails = receiveMails(UPDATED_SUBJECT)

    checkSubmitter(mails, "dave")
    checkChain(mails, commit_issue, "ISSUE RESOLVED!")
    checkNoMoreChains(mails)
