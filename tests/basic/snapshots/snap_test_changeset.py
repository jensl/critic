# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Frozen, Masked, Variable


snapshots = Snapshot()

snapshots['test_changeset push branch'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        "remote: Branch created based on 'master', with 2 associated commits:        ",
        'remote:   http://critic.example.org/log?repository=test_changeset-***&branch=branch1        ',
        'remote: To create a review of all 2 commits:        ',
        'remote:   http://critic.example.org/createreview?repository=test_changeset-***&branch=branch1        ',
        'remote: ',
        'To http://critic.example.org/test_changeset-***.git',
        ' * [new branch]                                                                        branch1 -> branch1'
    ],
    'stdout': [
        "Branch 'branch1' set up to track remote branch 'branch1' from 'origin'."
    ]
}

snapshots['test_changeset initial'] = {
    'request': {
        'method': 'GET',
        'path': 'api/v1/changesets',
        'query': {
            'commit': Anonymous(CommitSHA1='second'),
            'output_format': 'static',
            'repository': Anonymous(RepositoryId='test_changeset')
        }
    },
    'response': {
        'data': {
            'changesets': [
                {
                    'completion_level': [
                    ],
                    'contributing_commits': [
                        Anonymous(CommitId='second')
                    ],
                    'files': None,
                    'from_commit': Anonymous(CommitId='first'),
                    'id': Anonymous(ChangesetId='created'),
                    'is_direct': True,
                    'is_replay': False,
                    'repository': Anonymous(RepositoryId='test_changeset'),
                    'review_state': None,
                    'to_commit': Anonymous(CommitId='second')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_changeset ready'] = {
    'request': {
        'method': 'GET',
        'path': 'api/v1/changesets',
        'query': {
            'commit': Anonymous(CommitSHA1='second'),
            'include': 'files,filechanges',
            'output_format': 'static',
            'repository': Anonymous(RepositoryId='test_changeset')
        }
    },
    'response': {
        'data': {
            'changesets': [
                {
                    'completion_level': [
                        'analysis',
                        'changedlines',
                        'full',
                        'structure',
                        'syntaxhighlight'
                    ],
                    'contributing_commits': [
                        Anonymous(CommitId='second')
                    ],
                    'files': set([
                        Anonymous(FileId='deleted.txt'),
                        Anonymous(FileId='modified.txt'),
                        Anonymous(FileId='added.txt')
                    ]),
                    'from_commit': Anonymous(CommitId='first'),
                    'id': Anonymous(ChangesetId='created'),
                    'is_direct': True,
                    'is_replay': False,
                    'repository': Anonymous(RepositoryId='test_changeset'),
                    'review_state': None,
                    'to_commit': Anonymous(CommitId='second')
                }
            ],
            'linked': {
                'filechanges': set([
                    Frozen({
                        'changeset': Anonymous(ChangesetId='created'),
                        'file': Anonymous(FileId='modified.txt'),
                        'new_mode': 33188,
                        'new_sha1': Anonymous(FileSHA1='initial modified\n'),
                        'old_mode': 33188,
                        'old_sha1': Anonymous(FileSHA1='initial\n')
                    }),
                    Frozen({
                        'changeset': Anonymous(ChangesetId='created'),
                        'file': Anonymous(FileId='added.txt'),
                        'new_mode': 33188,
                        'new_sha1': Anonymous(FileSHA1='added\n'),
                        'old_mode': None,
                        'old_sha1': None
                    }),
                    Frozen({
                        'changeset': Anonymous(ChangesetId='created'),
                        'file': Anonymous(FileId='deleted.txt'),
                        'new_mode': None,
                        'new_sha1': None,
                        'old_mode': 33188,
                        'old_sha1': Anonymous(FileSHA1='deleted\n')
                    })
                ]),
                'files': set([
                    Frozen({
                        'id': Anonymous(FileId='modified.txt'),
                        'path': 'modified.txt'
                    }),
                    Frozen({
                        'id': Anonymous(FileId='added.txt'),
                        'path': 'added.txt'
                    }),
                    Frozen({
                        'id': Anonymous(FileId='deleted.txt'),
                        'path': 'deleted.txt'
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_changeset readable diffs'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/changesets/<Anonymous(ChangesetId='created')>/filediffs",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'filediffs': set([
                Frozen({
                    'changeset': Anonymous(ChangesetId='created'),
                    'file': Anonymous(FileId='deleted.txt'),
                    'macro_chunks': [
                        {
                            'content': [
                                {
                                    'content': [
                                        [
                                            'deleted',
                                            0,
                                            -2
                                        ]
                                    ],
                                    'new_offset': 1,
                                    'old_offset': 1,
                                    'type': 'DELETED'
                                }
                            ],
                            'new_count': 0,
                            'new_offset': 1,
                            'old_count': 1,
                            'old_offset': 1
                        }
                    ],
                    'new_is_binary': None,
                    'new_length': None,
                    'new_linebreak': None,
                    'new_syntax': None,
                    'old_is_binary': False,
                    'old_length': 1,
                    'old_linebreak': None,
                    'old_syntax': None
                }),
                Frozen({
                    'changeset': Anonymous(ChangesetId='created'),
                    'file': Anonymous(FileId='modified.txt'),
                    'macro_chunks': [
                        {
                            'content': [
                                {
                                    'content': [
                                        'initial',
                                        [
                                            ' modified',
                                            0,
                                            2
                                        ]
                                    ],
                                    'new_offset': 1,
                                    'old_offset': 1,
                                    'type': 'MODIFIED'
                                }
                            ],
                            'new_count': 1,
                            'new_offset': 1,
                            'old_count': 1,
                            'old_offset': 1
                        }
                    ],
                    'new_is_binary': False,
                    'new_length': 1,
                    'new_linebreak': None,
                    'new_syntax': None,
                    'old_is_binary': False,
                    'old_length': 1,
                    'old_linebreak': None,
                    'old_syntax': None
                }),
                Frozen({
                    'changeset': Anonymous(ChangesetId='created'),
                    'file': Anonymous(FileId='added.txt'),
                    'macro_chunks': [
                        {
                            'content': [
                                {
                                    'content': [
                                        [
                                            'added',
                                            0,
                                            2
                                        ]
                                    ],
                                    'new_offset': 1,
                                    'old_offset': 1,
                                    'type': 'INSERTED'
                                }
                            ],
                            'new_count': 1,
                            'new_offset': 1,
                            'old_count': 0,
                            'old_offset': 1
                        }
                    ],
                    'new_is_binary': False,
                    'new_length': 1,
                    'new_linebreak': None,
                    'new_syntax': None,
                    'old_is_binary': None,
                    'old_length': None,
                    'old_linebreak': None,
                    'old_syntax': None
                })
            ])
        },
        'status_code': 200
    }
}

snapshots['test_changeset compact diffs'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/changesets/<Anonymous(ChangesetId='created')>/filediffs",
        'query': {
            'compact': 'yes',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'filediffs': set([
                Frozen({
                    'changeset': Anonymous(ChangesetId='created'),
                    'file': Anonymous(FileId='modified.txt'),
                    'macro_chunks': [
                        [
                            [
                                [
                                    3,
                                    [
                                        'initial',
                                        [
                                            ' modified',
                                            0,
                                            2
                                        ]
                                    ]
                                ]
                            ],
                            1,
                            1,
                            1,
                            1
                        ]
                    ],
                    'new_is_binary': False,
                    'new_length': 1,
                    'new_linebreak': None,
                    'new_syntax': None,
                    'old_is_binary': False,
                    'old_length': 1,
                    'old_linebreak': None,
                    'old_syntax': None
                }),
                Frozen({
                    'changeset': Anonymous(ChangesetId='created'),
                    'file': Anonymous(FileId='added.txt'),
                    'macro_chunks': [
                        [
                            [
                                [
                                    5,
                                    [
                                        [
                                            'added',
                                            0,
                                            2
                                        ]
                                    ]
                                ]
                            ],
                            1,
                            1,
                            0,
                            1
                        ]
                    ],
                    'new_is_binary': False,
                    'new_length': 1,
                    'new_linebreak': None,
                    'new_syntax': None,
                    'old_is_binary': None,
                    'old_length': None,
                    'old_linebreak': None,
                    'old_syntax': None
                }),
                Frozen({
                    'changeset': Anonymous(ChangesetId='created'),
                    'file': Anonymous(FileId='deleted.txt'),
                    'macro_chunks': [
                        [
                            [
                                [
                                    2,
                                    [
                                        [
                                            'deleted',
                                            0,
                                            -2
                                        ]
                                    ]
                                ]
                            ],
                            1,
                            1,
                            1,
                            0
                        ]
                    ],
                    'new_is_binary': None,
                    'new_length': None,
                    'new_linebreak': None,
                    'new_syntax': None,
                    'old_is_binary': False,
                    'old_length': 1,
                    'old_linebreak': None,
                    'old_syntax': None
                })
            ])
        },
        'status_code': 200
    }
}
