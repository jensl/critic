cherrypick_pattern = """\
=== git cherry-pick {sha1} ===
error: could not apply ([0-9a-f]{{4,40}})\\.\\.\\. Add conflicting nonsense
hint: after resolving the conflicts, mark the corrected paths
hint: with 'git add <paths>' or 'git rm <paths>'
hint: and commit the result with 'git commit'


"""

merge_pattern = """\
=== git merge --no-ff -m "\\.\\.\\." {sha1} ===
Auto-merging {test_name}/{conflicted}
CONFLICT \\(add/add\\): Merge conflict in {test_name}/{conflicted}
Automatic merge failed; fix conflicts and then commit the result\\.


"""

status_pattern = """\
=== git status ===
Not currently on any branch\\.
{situation}\\.
  \\(fix conflicts and run "{continue_command}"\\)
  \\({abort_instruction}\\)

Changes to be committed:

\t(?:modified|new file):   {test_name}/{modified}

Unmerged paths:
  \\(use "git add <file>\\.\\.\\." to mark resolution\\)

\tboth added:      {test_name}/{conflicted}


"""

diff_pattern = """\
=== git diff ===
diff --cc {test_name}/{conflicted}
index [0-9a-f]{{4,40}},[0-9a-f]{{4,40}}\\.\\.0000000
--- a/{test_name}/{conflicted}
\\+\\+\\+ b/{test_name}/{conflicted}
@@@ -1,26 -1,8 \\+1,37 @@@
\\+\\+<<<<<<< HEAD
 \\+\\[first\\] Lorem ipsum dolor sit amet, consectetur adipiscing
 \\+\\[first\\] elit\\. Donec ut enim sit amet purus ultricies
 \\+\\[first\\] lobortis\\. Pellentesque nisi arcu, convallis sed purus sed,
 \\+\\[first\\] semper ultrices velit\\. Ut egestas lorem tortor, vitae
 \\+\\[first\\] lacinia lorem consectetur nec\\. Integer tempor ornare ipsum
 \\+\\[first\\] at viverra\\. Curabitur nec orci mollis, lacinia sapien eget,
 \\+\\[first\\] ultricies ipsum\\. Curabitur a libero tortor\\. Curabitur
 \\+\\[first\\] volutpat lacinia erat, ac suscipit enim dignissim nec\\.
 \\+
 \\+\\[second\\] Lorem ipsum dolor sit amet, consectetur adipiscing
 \\+\\[second\\] elit\\. Donec ut enim sit amet purus ultricies
 \\+\\[second\\] lobortis\\. Pellentesque nisi arcu, convallis sed purus sed,
 \\+\\[second\\] semper ultrices velit\\. Ut egestas lorem tortor, vitae
 \\+\\[second\\] lacinia lorem consectetur nec\\. Integer tempor ornare ipsum
 \\+\\[second\\] at viverra\\. Curabitur nec orci mollis, lacinia sapien eget,
 \\+\\[second\\] ultricies ipsum\\. Curabitur a libero tortor\\. Curabitur
 \\+\\[second\\] volutpat lacinia erat, ac suscipit enim dignissim nec\\.
 \\+
 \\+\\[third\\] Lorem ipsum dolor sit amet, consectetur adipiscing
 \\+\\[third\\] elit\\. Donec ut enim sit amet purus ultricies
 \\+\\[third\\] lobortis\\. Pellentesque nisi arcu, convallis sed purus sed,
 \\+\\[third\\] semper ultrices velit\\. Ut egestas lorem tortor, vitae
 \\+\\[third\\] lacinia lorem consectetur nec\\. Integer tempor ornare ipsum
 \\+\\[third\\] at viverra\\. Curabitur nec orci mollis, lacinia sapien eget,
 \\+\\[third\\] ultricies ipsum\\. Curabitur a libero tortor\\. Curabitur
 \\+\\[third\\] volutpat lacinia erat, ac suscipit enim dignissim nec\\.
\\+\\+=======
\\+ \\[conflict\\] Lorem ipsum dolor sit amet, consectetur adipiscing
\\+ \\[conflict\\] elit\\. Donec ut enim sit amet purus ultricies
\\+ \\[conflict\\] lobortis\\. Pellentesque nisi arcu, convallis sed purus sed,
\\+ \\[conflict\\] semper ultrices velit\\. Ut egestas lorem tortor, vitae
\\+ \\[conflict\\] lacinia lorem consectetur nec\\. Integer tempor ornare ipsum
\\+ \\[conflict\\] at viverra\\. Curabitur nec orci mollis, lacinia sapien eget,
\\+ \\[conflict\\] ultricies ipsum\\. Curabitur a libero tortor\\. Curabitur
\\+ \\[conflict\\] volutpat lacinia erat, ac suscipit enim dignissim nec\\.
\\+\\+>>>>>>> {trailing}"""


def markAllAsReviewed(review):
    with frontend.signin("bob"):
        frontend.json(
            f"reviews/{review.id}/reviewablefilechanges",
            params={"assignee": "(me)", "state": "pending"},
            put={"draft_changes": {"new_is_reviewed": True}},
        )
        frontend.json(f"reviews/{review.id}/batches", post={})
        review.expectMails("Updated Review")
