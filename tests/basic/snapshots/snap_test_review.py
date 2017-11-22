# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Frozen, Masked, Variable


snapshots = Snapshot()

snapshots['test_create_review websocket messages'] = {
    'publish': [
        {
            'channel': [
                'repositories'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryId='test_create_review'),
                'resource_name': 'repositories'
            }
        },
        {
            'channel': [
                "repositories/<Anonymous(RepositoryId='test_create_review')>"
            ],
            'message': {
                'action': 'modified',
                'object_id': Anonymous(RepositoryId='test_create_review'),
                'resource_name': 'repositories',
                'updates': {
                    'is_ready': True
                }
            }
        },
        {
            'channel': [
                'branches'
            ],
            'message': {
                'action': 'created',
                'name': 'master',
                'object_id': Anonymous(BranchId='master'),
                'repository_id': Anonymous(RepositoryId='test_create_review'),
                'resource_name': 'branches'
            }
        },
        {
            'channel': [
                'branchupdates',
                "branches/<Anonymous(BranchId='master')>/branchupdates"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(1)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                'branches'
            ],
            'message': {
                'action': 'created',
                'name': 'branch1',
                'object_id': Anonymous(BranchId='branch1'),
                'repository_id': Anonymous(RepositoryId='test_create_review'),
                'resource_name': 'branches'
            }
        },
        {
            'channel': [
                'branchupdates',
                "branches/<Anonymous(BranchId='branch1')>/branchupdates"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(2)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                'branches'
            ],
            'message': {
                'action': 'created',
                'name': 'r/review1',
                'object_id': Anonymous(BranchId=Variable(1)),
                'repository_id': Anonymous(RepositoryId='test_create_review'),
                'resource_name': 'branches'
            }
        },
        {
            'channel': [
                'branchupdates',
                'branches/<Anonymous(BranchId=Variable(1))>/branchupdates'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(3)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                'reviews'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ReviewId='r/review1'),
                'resource_name': 'reviews'
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='r/review1')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'created',
                'object_id': Anonymous(ReviewEventId=Variable(1)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='r/review1')
            }
        },
        {
            'channel': [
                'changesets'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ChangesetId='third'),
                'resource_name': 'changesets'
            }
        },
        {
            'channel': [
                'changesets'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ChangesetId='second'),
                'resource_name': 'changesets'
            }
        },
        {
            'channel': [
                'changesets'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ChangesetId='first'),
                'resource_name': 'changesets'
            }
        },
        {
            'channel': [
                'changesets'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ChangesetId=Variable(1)),
                'resource_name': 'changesets'
            }
        },
        {
            'channel': [
                'changesets/<Anonymous(ChangesetId=Variable(1))>'
            ],
            'message': {
                'action': 'modified',
                'object_id': Anonymous(ChangesetId=Variable(1)),
                'resource_name': 'changesets',
                'updates': {
                    'completion_level': [
                        'structure'
                    ]
                }
            }
        },
        {
            'channel': [
                'changesets/<Anonymous(ChangesetId=Variable(1))>'
            ],
            'message': {
                'action': 'modified',
                'object_id': Anonymous(ChangesetId=Variable(1)),
                'resource_name': 'changesets',
                'updates': {
                    'completion_level': [
                        'analysis',
                        'changedlines',
                        'full',
                        'structure',
                        'syntaxhighlight'
                    ]
                }
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='r/review1')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'ready',
                'object_id': Anonymous(ReviewEventId=Variable(2)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='r/review1')
            }
        },
        {
            'channel': [
                'reviewfilters',
                "reviews/<Anonymous(ReviewId='r/review1')>/reviewfilters"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ReviewFilterId=Variable(1)),
                'resource_name': 'reviewfilters'
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='r/review1')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'published',
                'object_id': Anonymous(ReviewEventId=Variable(3)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='r/review1')
            }
        },
        {
            'channel': [
                'comments',
                "reviews/<Anonymous(ReviewId='r/review1')>/comments"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(CommentId=Variable(1)),
                'resource_name': 'comments'
            }
        },
        {
            'channel': [
                'comments',
                "reviews/<Anonymous(ReviewId='r/review1')>/comments"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(CommentId=Variable(2)),
                'resource_name': 'comments'
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='r/review1')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'batch',
                'object_id': Anonymous(ReviewEventId=Variable(4)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='r/review1')
            }
        },
        {
            'channel': [
                'batches',
                "reviews/<Anonymous(ReviewId='r/review1')>/batches"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BatchId=Variable(1)),
                'resource_name': 'batches'
            }
        },
        {
            'channel': [
                'replies',
                "reviews/<Anonymous(ReviewId='r/review1')>/replies",
                'comments/<Anonymous(CommentId=Variable(1))>/replies'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ReplyId=Variable(1)),
                'resource_name': 'replies'
            }
        },
        {
            'channel': [
                "reviews/<Anonymous(ReviewId='r/review1')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(ReviewId='r/review1'),
                'resource_name': 'reviews'
            }
        }
    ]
}

snapshots['test_create_review push branch'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        "remote: Branch created based on 'master', with 3 associated commits:        ",
        'remote:   http://critic.example.org/log?repository=test_create_review-***&branch=branch1        ',
        'remote: To create a review of all 3 commits:        ',
        'remote:   http://critic.example.org/createreview?repository=test_create_review-***&branch=branch1        ',
        'remote: ',
        'To http://critic.example.org/test_create_review-***.git',
        ' * [new branch]                                                                        branch1 -> branch1'
    ],
    'stdout': [
        "Branch 'branch1' set up to track remote branch 'branch1' from 'origin'."
    ]
}

snapshots['test_create_review branch commits'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>/commits",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'commits': [
                {
                    'author': {
                        'email': 'alice@example.org',
                        'name': 'Alice von Testing',
                        'timestamp': Anonymous(Timestamp=Masked())
                    },
                    'committer': {
                        'email': 'alice@example.org',
                        'name': 'Alice von Testing',
                        'timestamp': Anonymous(Timestamp=Masked())
                    },
                    'id': Anonymous(CommitId='third'),
                    'message': '''third
''',
                    'parents': [
                        Anonymous(CommitId='second')
                    ],
                    'sha1': Anonymous(CommitSHA1='third'),
                    'summary': 'third',
                    'tree': Anonymous(TreeSHA1=Variable(1))
                },
                {
                    'author': {
                        'email': 'alice@example.org',
                        'name': 'Alice von Testing',
                        'timestamp': Anonymous(Timestamp=Masked())
                    },
                    'committer': {
                        'email': 'alice@example.org',
                        'name': 'Alice von Testing',
                        'timestamp': Anonymous(Timestamp=Masked())
                    },
                    'id': Anonymous(CommitId='second'),
                    'message': '''second
''',
                    'parents': [
                        Anonymous(CommitId='first')
                    ],
                    'sha1': Anonymous(CommitSHA1='second'),
                    'summary': 'second',
                    'tree': Anonymous(TreeSHA1=Variable(2))
                },
                {
                    'author': {
                        'email': 'alice@example.org',
                        'name': 'Alice von Testing',
                        'timestamp': Anonymous(Timestamp=Masked())
                    },
                    'committer': {
                        'email': 'alice@example.org',
                        'name': 'Alice von Testing',
                        'timestamp': Anonymous(Timestamp=Masked())
                    },
                    'id': Anonymous(CommitId='first'),
                    'message': '''first
''',
                    'parents': [
                        Anonymous(CommitId=Variable(1))
                    ],
                    'sha1': Anonymous(CommitSHA1='first'),
                    'summary': 'first',
                    'tree': Anonymous(TreeSHA1=Variable(3))
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review create review'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/reviews',
        'payload': {
            'branch': 'r/review1',
            'commits': [
                Anonymous(CommitId='third'),
                Anonymous(CommitId='second'),
                Anonymous(CommitId='first')
            ],
            'repository': Anonymous(RepositoryId='test_create_review')
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviews': [
                {
                    'active_reviewers': [
                    ],
                    'assigned_reviewers': [
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': None,
                    'description': None,
                    'filters': [
                    ],
                    'id': Anonymous(ReviewId='r/review1'),
                    'integration': None,
                    'is_accepted': False,
                    'issues': [
                    ],
                    'last_changed': Anonymous(Timestamp=Masked()),
                    'notes': [
                    ],
                    'owners': [
                        Anonymous(UserId='alice')
                    ],
                    'partitions': [
                        {
                            'commits': [
                                Anonymous(CommitId='third'),
                                Anonymous(CommitId='second'),
                                Anonymous(CommitId='first')
                            ],
                            'rebase': None
                        }
                    ],
                    'pending_rebase': None,
                    'pending_update': None,
                    'pings': [
                    ],
                    'progress': {
                        'open_issues': 0,
                        'reviewing': 0
                    },
                    'progress_per_commit': [
                    ],
                    'repository': Anonymous(RepositoryId='test_create_review'),
                    'state': 'draft',
                    'summary': None,
                    'tags': [
                    ],
                    'watchers': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review review ready'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>",
        'query': {
            'include': 'changesets,filechanges',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'changesets': set([
                    Frozen({
                        'completion_level': [
                            'analysis',
                            'changedlines',
                            'full',
                            'structure',
                            'syntaxhighlight'
                        ],
                        'contributing_commits': [
                            Anonymous(CommitId='first')
                        ],
                        'files': set([
                            Anonymous(FileId=Variable(1))
                        ]),
                        'from_commit': Anonymous(CommitId=Variable(1)),
                        'id': Anonymous(ChangesetId='first'),
                        'is_direct': True,
                        'is_replay': False,
                        'repository': Anonymous(RepositoryId='test_create_review'),
                        'review_state': {
                            'comments': [
                            ],
                            'review': Anonymous(ReviewId='r/review1'),
                            'reviewablefilechanges': [
                                Anonymous(ReviewableFileChangeId=Variable(1))
                            ]
                        },
                        'to_commit': Anonymous(CommitId='first')
                    }),
                    Frozen({
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
                            Anonymous(FileId=Variable(1))
                        ]),
                        'from_commit': Anonymous(CommitId='first'),
                        'id': Anonymous(ChangesetId='second'),
                        'is_direct': True,
                        'is_replay': False,
                        'repository': Anonymous(RepositoryId='test_create_review'),
                        'review_state': {
                            'comments': [
                            ],
                            'review': Anonymous(ReviewId='r/review1'),
                            'reviewablefilechanges': [
                                Anonymous(ReviewableFileChangeId=Variable(2))
                            ]
                        },
                        'to_commit': Anonymous(CommitId='second')
                    }),
                    Frozen({
                        'completion_level': [
                            'analysis',
                            'changedlines',
                            'full',
                            'structure',
                            'syntaxhighlight'
                        ],
                        'contributing_commits': [
                            Anonymous(CommitId='third')
                        ],
                        'files': set([
                            Anonymous(FileId=Variable(1))
                        ]),
                        'from_commit': Anonymous(CommitId='second'),
                        'id': Anonymous(ChangesetId='third'),
                        'is_direct': True,
                        'is_replay': False,
                        'repository': Anonymous(RepositoryId='test_create_review'),
                        'review_state': {
                            'comments': [
                            ],
                            'review': Anonymous(ReviewId='r/review1'),
                            'reviewablefilechanges': [
                                Anonymous(ReviewableFileChangeId=Variable(3))
                            ]
                        },
                        'to_commit': Anonymous(CommitId='third')
                    })
                ]),
                'filechanges': set([
                    Frozen({
                        'changeset': Anonymous(ChangesetId='second'),
                        'file': Anonymous(FileId=Variable(1)),
                        'new_mode': 33188,
                        'new_sha1': Anonymous(FileSHA1=Variable(2)),
                        'old_mode': 33188,
                        'old_sha1': Anonymous(FileSHA1=Variable(1))
                    }),
                    Frozen({
                        'changeset': Anonymous(ChangesetId='first'),
                        'file': Anonymous(FileId=Variable(1)),
                        'new_mode': 33188,
                        'new_sha1': Anonymous(FileSHA1=Variable(1)),
                        'old_mode': None,
                        'old_sha1': None
                    }),
                    Frozen({
                        'changeset': Anonymous(ChangesetId='third'),
                        'file': Anonymous(FileId=Variable(1)),
                        'new_mode': 33188,
                        'new_sha1': Anonymous(FileSHA1=Variable(3)),
                        'old_mode': 33188,
                        'old_sha1': Anonymous(FileSHA1=Variable(2))
                    })
                ])
            },
            'reviews': [
                {
                    'active_reviewers': [
                    ],
                    'assigned_reviewers': [
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': [
                        Anonymous(ChangesetId='third'),
                        Anonymous(ChangesetId='second'),
                        Anonymous(ChangesetId='first')
                    ],
                    'description': None,
                    'filters': [
                    ],
                    'id': Anonymous(ReviewId='r/review1'),
                    'integration': None,
                    'is_accepted': False,
                    'issues': [
                    ],
                    'last_changed': Anonymous(Timestamp=Masked()),
                    'notes': [
                    ],
                    'owners': [
                        Anonymous(UserId='alice')
                    ],
                    'partitions': [
                        {
                            'commits': [
                                Anonymous(CommitId='third'),
                                Anonymous(CommitId='second'),
                                Anonymous(CommitId='first')
                            ],
                            'rebase': None
                        }
                    ],
                    'pending_rebase': None,
                    'pending_update': None,
                    'pings': [
                    ],
                    'progress': {
                        'open_issues': 0,
                        'reviewing': 0.0
                    },
                    'progress_per_commit': [
                        {
                            'commit': Anonymous(CommitId='third'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='second'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='first'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        }
                    ],
                    'repository': Anonymous(RepositoryId='test_create_review'),
                    'state': 'draft',
                    'summary': None,
                    'tags': [
                    ],
                    'watchers': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review create review filter'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>/reviewfilters",
        'payload': {
            'path': '',
            'subject': Anonymous(UserId='bob'),
            'type': 'reviewer'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviewfilters': [
                {
                    'creator': Anonymous(UserId='alice'),
                    'default_scope': True,
                    'id': Anonymous(ReviewFilterId=Variable(1)),
                    'path': '/',
                    'review': Anonymous(ReviewId='r/review1'),
                    'scopes': [
                    ],
                    'subject': Anonymous(UserId='bob'),
                    'type': 'reviewer'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review publish review'] = {
    'request': {
        'method': 'PUT',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>",
        'payload': {
            'state': 'open',
            'summary': 'test_review::test_create_review'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviews': [
                {
                    'active_reviewers': [
                    ],
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': [
                        Anonymous(ChangesetId='third'),
                        Anonymous(ChangesetId='second'),
                        Anonymous(ChangesetId='first')
                    ],
                    'description': None,
                    'filters': [
                        Anonymous(ReviewFilterId=Variable(1))
                    ],
                    'id': Anonymous(ReviewId='r/review1'),
                    'integration': None,
                    'is_accepted': False,
                    'issues': [
                    ],
                    'last_changed': Anonymous(Timestamp=Masked()),
                    'notes': [
                    ],
                    'owners': [
                        Anonymous(UserId='alice')
                    ],
                    'partitions': [
                        {
                            'commits': [
                                Anonymous(CommitId='third'),
                                Anonymous(CommitId='second'),
                                Anonymous(CommitId='first')
                            ],
                            'rebase': None
                        }
                    ],
                    'pending_rebase': None,
                    'pending_update': None,
                    'pings': [
                    ],
                    'progress': {
                        'open_issues': 0,
                        'reviewing': 0.0
                    },
                    'progress_per_commit': [
                        {
                            'commit': Anonymous(CommitId='third'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='second'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='first'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        }
                    ],
                    'repository': Anonymous(RepositoryId='test_create_review'),
                    'state': 'open',
                    'summary': 'test_review::test_create_review',
                    'tags': [
                    ],
                    'watchers': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review review (as bob)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviews': [
                {
                    'active_reviewers': [
                    ],
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': [
                        Anonymous(ChangesetId='third'),
                        Anonymous(ChangesetId='second'),
                        Anonymous(ChangesetId='first')
                    ],
                    'description': None,
                    'filters': [
                        Anonymous(ReviewFilterId=Variable(1))
                    ],
                    'id': Anonymous(ReviewId='r/review1'),
                    'integration': None,
                    'is_accepted': False,
                    'issues': [
                    ],
                    'last_changed': Anonymous(Timestamp=Masked()),
                    'notes': [
                    ],
                    'owners': [
                        Anonymous(UserId='alice')
                    ],
                    'partitions': [
                        {
                            'commits': [
                                Anonymous(CommitId='third'),
                                Anonymous(CommitId='second'),
                                Anonymous(CommitId='first')
                            ],
                            'rebase': None
                        }
                    ],
                    'pending_rebase': None,
                    'pending_update': None,
                    'pings': [
                    ],
                    'progress': {
                        'open_issues': 0,
                        'reviewing': 0.0
                    },
                    'progress_per_commit': [
                        {
                            'commit': Anonymous(CommitId='third'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='second'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='first'),
                            'reviewed_changes': 0,
                            'total_changes': 1
                        }
                    ],
                    'repository': Anonymous(RepositoryId='test_create_review'),
                    'state': 'open',
                    'summary': 'test_review::test_create_review',
                    'tags': [
                        Anonymous(ReviewTagId='assigned'),
                        Anonymous(ReviewTagId='pending'),
                        Anonymous(ReviewTagId='unseen'),
                        Anonymous(ReviewTagId='single'),
                        Anonymous(ReviewTagId='available')
                    ],
                    'watchers': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review reviewable file changes (as bob)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>/reviewablefilechanges",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviewablefilechanges': [
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'changeset': Anonymous(ChangesetId='third'),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId=Variable(1)),
                    'id': Anonymous(ReviewableFileChangeId=Variable(3)),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'changeset': Anonymous(ChangesetId='second'),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId=Variable(1)),
                    'id': Anonymous(ReviewableFileChangeId=Variable(2)),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'changeset': Anonymous(ChangesetId='first'),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId=Variable(1)),
                    'id': Anonymous(ReviewableFileChangeId=Variable(1)),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_by': [
                    ],
                    'scope': None
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review raise issue (as bob)'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>/comments",
        'payload': {
            'text': 'Add a test, please!',
            'type': 'issue'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'comments': [
                {
                    'addressed_by': None,
                    'author': Anonymous(UserId='bob'),
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'is_draft': True,
                        'new_location': None,
                        'new_state': None,
                        'new_type': None,
                        'reply': None
                    },
                    'id': Anonymous(CommentId=Variable(1)),
                    'is_draft': True,
                    'location': None,
                    'replies': [
                    ],
                    'resolved_by': None,
                    'review': Anonymous(ReviewId='r/review1'),
                    'state': 'open',
                    'text': 'Add a test, please!',
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'translated_location': None,
                    'type': 'issue'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review review file changes (as bob)'] = {
    'request': {
        'method': 'PUT',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>/reviewablefilechanges",
        'payload': {
            'draft_changes': {
                'new_is_reviewed': True
            }
        },
        'query': {
            'assignee': 'bob',
            'output_format': 'static',
            'state': 'pending'
        }
    },
    'response': {
        'data': {
            'reviewablefilechanges': [
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'changeset': Anonymous(ChangesetId='third'),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId=Variable(1)),
                    'id': Anonymous(ReviewableFileChangeId=Variable(3)),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'changeset': Anonymous(ChangesetId='second'),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId=Variable(1)),
                    'id': Anonymous(ReviewableFileChangeId=Variable(2)),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'changeset': Anonymous(ChangesetId='first'),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId=Variable(1)),
                    'id': Anonymous(ReviewableFileChangeId=Variable(1)),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_by': [
                    ],
                    'scope': None
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review submit changes (as bob)'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>/batches",
        'payload': {
            'comment': 'LGTM'
        },
        'query': {
            'include': 'comments,reviews',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'batches': [
                {
                    'author': Anonymous(UserId='bob'),
                    'comment': Anonymous(CommentId=Variable(2)),
                    'created_comments': [
                        Anonymous(CommentId=Variable(1))
                    ],
                    'id': Anonymous(BatchId=Variable(1)),
                    'is_empty': False,
                    'morphed_comments': [
                    ],
                    'reopened_issues': [
                    ],
                    'resolved_issues': [
                    ],
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_changes': [
                        Anonymous(ReviewableFileChangeId=Variable(3)),
                        Anonymous(ReviewableFileChangeId=Variable(2)),
                        Anonymous(ReviewableFileChangeId=Variable(1))
                    ],
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'unreviewed_changes': [
                    ],
                    'written_replies': [
                    ]
                }
            ],
            'linked': {
                'comments': set([
                    Frozen({
                        'addressed_by': None,
                        'author': Anonymous(UserId='bob'),
                        'draft_changes': None,
                        'id': Anonymous(CommentId=Variable(1)),
                        'is_draft': False,
                        'location': None,
                        'replies': [
                        ],
                        'resolved_by': None,
                        'review': Anonymous(ReviewId='r/review1'),
                        'state': 'open',
                        'text': 'Add a test, please!',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'translated_location': None,
                        'type': 'issue'
                    }),
                    Frozen({
                        'addressed_by': None,
                        'author': Anonymous(UserId='bob'),
                        'draft_changes': None,
                        'id': Anonymous(CommentId=Variable(2)),
                        'is_draft': False,
                        'location': None,
                        'replies': [
                        ],
                        'resolved_by': None,
                        'review': Anonymous(ReviewId='r/review1'),
                        'state': None,
                        'text': 'LGTM',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'translated_location': None,
                        'type': 'note'
                    })
                ]),
                'reviews': set([
                    Frozen({
                        'active_reviewers': [
                            Anonymous(UserId='bob')
                        ],
                        'assigned_reviewers': [
                            Anonymous(UserId='bob')
                        ],
                        'branch': Anonymous(BranchId=Variable(1)),
                        'changesets': [
                            Anonymous(ChangesetId='third'),
                            Anonymous(ChangesetId='second'),
                            Anonymous(ChangesetId='first')
                        ],
                        'description': None,
                        'filters': [
                            Anonymous(ReviewFilterId=Variable(1))
                        ],
                        'id': Anonymous(ReviewId='r/review1'),
                        'integration': None,
                        'is_accepted': False,
                        'issues': [
                            Anonymous(CommentId=Variable(1))
                        ],
                        'last_changed': Anonymous(Timestamp=Masked()),
                        'notes': [
                        ],
                        'owners': [
                            Anonymous(UserId='alice')
                        ],
                        'partitions': [
                            {
                                'commits': [
                                    Anonymous(CommitId='third'),
                                    Anonymous(CommitId='second'),
                                    Anonymous(CommitId='first')
                                ],
                                'rebase': None
                            }
                        ],
                        'pending_rebase': None,
                        'pending_update': None,
                        'pings': [
                        ],
                        'progress': {
                            'open_issues': 1,
                            'reviewing': 1.0
                        },
                        'progress_per_commit': [
                            {
                                'commit': Anonymous(CommitId='third'),
                                'reviewed_changes': 1,
                                'total_changes': 1
                            },
                            {
                                'commit': Anonymous(CommitId='second'),
                                'reviewed_changes': 1,
                                'total_changes': 1
                            },
                            {
                                'commit': Anonymous(CommitId='first'),
                                'reviewed_changes': 1,
                                'total_changes': 1
                            }
                        ],
                        'repository': Anonymous(RepositoryId='test_create_review'),
                        'state': 'open',
                        'summary': 'test_review::test_create_review',
                        'tags': [
                            Anonymous(ReviewTagId='assigned'),
                            Anonymous(ReviewTagId='active'),
                            Anonymous(ReviewTagId='single'),
                            Anonymous(ReviewTagId='primary')
                        ],
                        'watchers': [
                        ]
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_create_review review state'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviews': [
                {
                    'active_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': [
                        Anonymous(ChangesetId='third'),
                        Anonymous(ChangesetId='second'),
                        Anonymous(ChangesetId='first')
                    ],
                    'description': None,
                    'filters': [
                        Anonymous(ReviewFilterId=Variable(1))
                    ],
                    'id': Anonymous(ReviewId='r/review1'),
                    'integration': None,
                    'is_accepted': False,
                    'issues': [
                        Anonymous(CommentId=Variable(1))
                    ],
                    'last_changed': Anonymous(Timestamp=Masked()),
                    'notes': [
                    ],
                    'owners': [
                        Anonymous(UserId='alice')
                    ],
                    'partitions': [
                        {
                            'commits': [
                                Anonymous(CommitId='third'),
                                Anonymous(CommitId='second'),
                                Anonymous(CommitId='first')
                            ],
                            'rebase': None
                        }
                    ],
                    'pending_rebase': None,
                    'pending_update': None,
                    'pings': [
                    ],
                    'progress': {
                        'open_issues': 1,
                        'reviewing': 1.0
                    },
                    'progress_per_commit': [
                        {
                            'commit': Anonymous(CommitId='third'),
                            'reviewed_changes': 1,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='second'),
                            'reviewed_changes': 1,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='first'),
                            'reviewed_changes': 1,
                            'total_changes': 1
                        }
                    ],
                    'repository': Anonymous(RepositoryId='test_create_review'),
                    'state': 'open',
                    'summary': 'test_review::test_create_review',
                    'tags': [
                    ],
                    'watchers': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review review state (batches)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>/batches",
        'query': {
            'include': 'comments',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'batches': [
                {
                    'author': Anonymous(UserId='bob'),
                    'comment': Anonymous(CommentId=Variable(2)),
                    'created_comments': [
                        Anonymous(CommentId=Variable(1))
                    ],
                    'id': Anonymous(BatchId=Variable(1)),
                    'is_empty': False,
                    'morphed_comments': [
                    ],
                    'reopened_issues': [
                    ],
                    'resolved_issues': [
                    ],
                    'review': Anonymous(ReviewId='r/review1'),
                    'reviewed_changes': [
                        Anonymous(ReviewableFileChangeId=Variable(3)),
                        Anonymous(ReviewableFileChangeId=Variable(2)),
                        Anonymous(ReviewableFileChangeId=Variable(1))
                    ],
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'unreviewed_changes': [
                    ],
                    'written_replies': [
                    ]
                }
            ],
            'linked': {
                'comments': set([
                    Frozen({
                        'addressed_by': None,
                        'author': Anonymous(UserId='bob'),
                        'draft_changes': None,
                        'id': Anonymous(CommentId=Variable(1)),
                        'is_draft': False,
                        'location': None,
                        'replies': [
                        ],
                        'resolved_by': None,
                        'review': Anonymous(ReviewId='r/review1'),
                        'state': 'open',
                        'text': 'Add a test, please!',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'translated_location': None,
                        'type': 'issue'
                    }),
                    Frozen({
                        'addressed_by': None,
                        'author': Anonymous(UserId='bob'),
                        'draft_changes': None,
                        'id': Anonymous(CommentId=Variable(2)),
                        'is_draft': False,
                        'location': None,
                        'replies': [
                        ],
                        'resolved_by': None,
                        'review': Anonymous(ReviewId='r/review1'),
                        'state': None,
                        'text': 'LGTM',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'translated_location': None,
                        'type': 'note'
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_create_review reply to issue (as alice)'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/comments/<Anonymous(CommentId=Variable(1))>/replies',
        'payload': {
            'text': 'Will do!'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'replies': [
                {
                    'author': Anonymous(UserId='alice'),
                    'comment': Anonymous(CommentId=Variable(1)),
                    'id': Anonymous(ReplyId=Variable(1)),
                    'is_draft': True,
                    'text': 'Will do!',
                    'timestamp': Anonymous(Timestamp=Masked())
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review resolve issue (as alice)'] = {
    'request': {
        'method': 'PUT',
        'path': 'api/v1/comments/<Anonymous(CommentId=Variable(1))>',
        'payload': {
            'draft_changes': {
                'new_state': 'resolved'
            }
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'comments': [
                {
                    'addressed_by': None,
                    'author': Anonymous(UserId='bob'),
                    'draft_changes': {
                        'author': Anonymous(UserId='alice'),
                        'is_draft': False,
                        'new_location': None,
                        'new_state': 'resolved',
                        'new_type': None,
                        'reply': Anonymous(ReplyId=Variable(1))
                    },
                    'id': Anonymous(CommentId=Variable(1)),
                    'is_draft': False,
                    'location': None,
                    'replies': [
                        Anonymous(ReplyId=Variable(1))
                    ],
                    'resolved_by': None,
                    'review': Anonymous(ReviewId='r/review1'),
                    'state': 'open',
                    'text': 'Add a test, please!',
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'translated_location': None,
                    'type': 'issue'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_create_review review state (as alice)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='r/review1')>",
        'query': {
            'include': 'batches,comments,replies',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'batches': set([
                    Frozen({
                        'author': Anonymous(UserId='alice'),
                        'comment': None,
                        'created_comments': [
                        ],
                        'id': None,
                        'is_empty': False,
                        'morphed_comments': [
                        ],
                        'reopened_issues': [
                        ],
                        'resolved_issues': [
                            Anonymous(CommentId=Variable(1))
                        ],
                        'review': Anonymous(ReviewId='r/review1'),
                        'reviewed_changes': [
                        ],
                        'timestamp': None,
                        'unreviewed_changes': [
                        ],
                        'written_replies': [
                            Anonymous(ReplyId=Variable(1))
                        ]
                    })
                ]),
                'comments': set([
                    Frozen({
                        'addressed_by': None,
                        'author': Anonymous(UserId='bob'),
                        'draft_changes': {
                            'author': Anonymous(UserId='alice'),
                            'is_draft': False,
                            'new_location': None,
                            'new_state': 'resolved',
                            'new_type': None,
                            'reply': Anonymous(ReplyId=Variable(1))
                        },
                        'id': Anonymous(CommentId=Variable(1)),
                        'is_draft': False,
                        'location': None,
                        'replies': [
                            Anonymous(ReplyId=Variable(1))
                        ],
                        'resolved_by': None,
                        'review': Anonymous(ReviewId='r/review1'),
                        'state': 'open',
                        'text': 'Add a test, please!',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'translated_location': None,
                        'type': 'issue'
                    })
                ]),
                'replies': set([
                    Frozen({
                        'author': Anonymous(UserId='alice'),
                        'comment': Anonymous(CommentId=Variable(1)),
                        'id': Anonymous(ReplyId=Variable(1)),
                        'is_draft': True,
                        'text': 'Will do!',
                        'timestamp': Anonymous(Timestamp=Masked())
                    })
                ])
            },
            'reviews': [
                {
                    'active_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'assigned_reviewers': [
                        Anonymous(UserId='bob')
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': [
                        Anonymous(ChangesetId='third'),
                        Anonymous(ChangesetId='second'),
                        Anonymous(ChangesetId='first')
                    ],
                    'description': None,
                    'filters': [
                        Anonymous(ReviewFilterId=Variable(1))
                    ],
                    'id': Anonymous(ReviewId='r/review1'),
                    'integration': None,
                    'is_accepted': False,
                    'issues': [
                        Anonymous(CommentId=Variable(1))
                    ],
                    'last_changed': Anonymous(Timestamp=Masked()),
                    'notes': [
                    ],
                    'owners': [
                        Anonymous(UserId='alice')
                    ],
                    'partitions': [
                        {
                            'commits': [
                                Anonymous(CommitId='third'),
                                Anonymous(CommitId='second'),
                                Anonymous(CommitId='first')
                            ],
                            'rebase': None
                        }
                    ],
                    'pending_rebase': None,
                    'pending_update': None,
                    'pings': [
                    ],
                    'progress': {
                        'open_issues': 1,
                        'reviewing': 1.0
                    },
                    'progress_per_commit': [
                        {
                            'commit': Anonymous(CommitId='third'),
                            'reviewed_changes': 1,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='second'),
                            'reviewed_changes': 1,
                            'total_changes': 1
                        },
                        {
                            'commit': Anonymous(CommitId='first'),
                            'reviewed_changes': 1,
                            'total_changes': 1
                        }
                    ],
                    'repository': Anonymous(RepositoryId='test_create_review'),
                    'state': 'open',
                    'summary': 'test_review::test_create_review',
                    'tags': [
                        Anonymous(ReviewTagId='unpublished')
                    ],
                    'watchers': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}
