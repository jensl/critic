# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Frozen, Masked, Variable


snapshots = Snapshot()

snapshots['test_reviewscope review scope filters (initial)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/repositories/<Anonymous(RepositoryId='test_reviewscope')>/reviewscopefilters",
        'query': {
            'include': 'reviewscopes',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'reviewscopes': set([
                ])
            },
            'reviewscopefilters': [
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope review scope filters (final)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/repositories/<Anonymous(RepositoryId='test_reviewscope')>/reviewscopefilters",
        'query': {
            'include': 'reviewscopes',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'reviewscopes': set([
                    Frozen({
                        'id': Anonymous(ReviewScopeId='special'),
                        'name': 'special-***'
                    })
                ])
            },
            'reviewscopefilters': [
                {
                    'id': Anonymous(ReviewScopeFilterId='special'),
                    'path': '**/*.special',
                    'repository': Anonymous(RepositoryId='test_reviewscope'),
                    'scope': Anonymous(ReviewScopeId='special')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope push branch: branch1'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        "remote: Branch created based on 'master', with 1 associated commit:        ",
        'remote:   http://critic.example.org/log?repository=test_reviewscope-***&branch=branch1        ',
        'remote: To create a review of the commit:        ',
        'remote:   http://critic.example.org/createreview?repository=test_reviewscope-***&branch=branch1        ',
        'remote: ',
        'To http://critic.example.org/test_reviewscope-***.git',
        ' * [new branch]                                                                        branch1 -> branch1'
    ],
    'stdout': [
        "Branch 'branch1' set up to track remote branch 'branch1' from 'origin'."
    ]
}

snapshots['test_reviewscope review (initial)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>",
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
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol'),
                        Anonymous(UserId='dave')
                    ],
                    'branch': Anonymous(BranchId=Variable(1)),
                    'changesets': [
                        Anonymous(ChangesetId=Variable(1))
                    ],
                    'description': None,
                    'filters': [
                    ],
                    'id': Anonymous(ReviewId='test_reviewscope'),
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
                                Anonymous(CommitId=Variable(1))
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
                            'commit': Anonymous(CommitId=Variable(1)),
                            'reviewed_changes': 0,
                            'total_changes': 3
                        }
                    ],
                    'repository': Anonymous(RepositoryId='test_reviewscope'),
                    'state': 'draft',
                    'summary': 'created files',
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

snapshots['test_reviewscope reviewable file changes (initial)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewablefilechanges",
        'query': {
            'include': 'files,reviewscopes',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'files': set([
                    Frozen({
                        'id': Anonymous(FileId='created.regular'),
                        'path': 'created.regular'
                    }),
                    Frozen({
                        'id': Anonymous(FileId='created.special'),
                        'path': 'created.special'
                    })
                ]),
                'reviewscopes': set([
                    Frozen({
                        'id': Anonymous(ReviewScopeId='special'),
                        'name': 'special-***'
                    })
                ])
            },
            'reviewablefilechanges': [
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId='created.regular'),
                    'id': Anonymous(ReviewableFileChangeId='created.regular'),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special'),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='dave')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special:special'),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                    ],
                    'scope': Anonymous(ReviewScopeId='special')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope bob: mark all changes as reviewed'] = {
    'request': {
        'method': 'PUT',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewablefilechanges",
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
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId='created.regular'),
                    'id': Anonymous(ReviewableFileChangeId='created.regular'),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special'),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='dave')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='bob'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special:special'),
                    'inserted_lines': 0,
                    'is_reviewed': False,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                    ],
                    'scope': Anonymous(ReviewScopeId='special')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope bob: publish changes'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/batches",
        'payload': {
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'batches': [
                {
                    'author': Anonymous(UserId='bob'),
                    'comment': None,
                    'created_comments': [
                    ],
                    'id': Anonymous(BatchId=Variable(1)),
                    'is_empty': False,
                    'morphed_comments': [
                    ],
                    'reopened_issues': [
                    ],
                    'resolved_issues': [
                    ],
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_changes': [
                        Anonymous(ReviewableFileChangeId='created.regular'),
                        Anonymous(ReviewableFileChangeId='created.special'),
                        Anonymous(ReviewableFileChangeId='created.special:special')
                    ],
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'unreviewed_changes': [
                    ],
                    'written_replies': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope carol: mark all changes as reviewed'] = {
    'request': {
        'method': 'PUT',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewablefilechanges",
        'payload': {
            'draft_changes': {
                'new_is_reviewed': True
            }
        },
        'query': {
            'assignee': 'carol',
            'output_format': 'static',
            'state': 'pending'
        }
    },
    'response': {
        'data': {
            'reviewablefilechanges': [
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='carol'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId='created.regular'),
                    'id': Anonymous(ReviewableFileChangeId='created.regular'),
                    'inserted_lines': 0,
                    'is_reviewed': True,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                        Anonymous(UserId='bob')
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='carol'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special'),
                    'inserted_lines': 0,
                    'is_reviewed': True,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                        Anonymous(UserId='bob')
                    ],
                    'scope': None
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope carol: publish changes'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/batches",
        'payload': {
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'batches': [
                {
                    'author': Anonymous(UserId='carol'),
                    'comment': None,
                    'created_comments': [
                    ],
                    'id': Anonymous(BatchId=Variable(2)),
                    'is_empty': False,
                    'morphed_comments': [
                    ],
                    'reopened_issues': [
                    ],
                    'resolved_issues': [
                    ],
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_changes': [
                        Anonymous(ReviewableFileChangeId='created.regular'),
                        Anonymous(ReviewableFileChangeId='created.special')
                    ],
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'unreviewed_changes': [
                    ],
                    'written_replies': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope dave: mark all changes as reviewed'] = {
    'request': {
        'method': 'PUT',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewablefilechanges",
        'payload': {
            'draft_changes': {
                'new_is_reviewed': True
            }
        },
        'query': {
            'assignee': 'dave',
            'output_format': 'static',
            'state': 'pending'
        }
    },
    'response': {
        'data': {
            'reviewablefilechanges': [
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='dave')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': {
                        'author': Anonymous(UserId='dave'),
                        'new_is_reviewed': True
                    },
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special:special'),
                    'inserted_lines': 0,
                    'is_reviewed': True,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                        Anonymous(UserId='bob')
                    ],
                    'scope': Anonymous(ReviewScopeId='special')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope dave: publish changes'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/batches",
        'payload': {
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'batches': [
                {
                    'author': Anonymous(UserId='dave'),
                    'comment': None,
                    'created_comments': [
                    ],
                    'id': Anonymous(BatchId=Variable(3)),
                    'is_empty': False,
                    'morphed_comments': [
                    ],
                    'reopened_issues': [
                    ],
                    'resolved_issues': [
                    ],
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_changes': [
                        Anonymous(ReviewableFileChangeId='created.special:special')
                    ],
                    'timestamp': Anonymous(Timestamp=Masked()),
                    'unreviewed_changes': [
                    ],
                    'written_replies': [
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope reviewable file changes (final)'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewablefilechanges",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviewablefilechanges': [
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId='created.regular'),
                    'id': Anonymous(ReviewableFileChangeId='created.regular'),
                    'inserted_lines': 0,
                    'is_reviewed': True,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special'),
                    'inserted_lines': 0,
                    'is_reviewed': True,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='carol')
                    ],
                    'scope': None
                },
                {
                    'assigned_reviewers': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='dave')
                    ],
                    'changeset': Anonymous(ChangesetId=Variable(1)),
                    'deleted_lines': 1,
                    'draft_changes': None,
                    'file': Anonymous(FileId='created.special'),
                    'id': Anonymous(ReviewableFileChangeId='created.special:special'),
                    'inserted_lines': 0,
                    'is_reviewed': True,
                    'review': Anonymous(ReviewId='test_reviewscope'),
                    'reviewed_by': [
                        Anonymous(UserId='bob'),
                        Anonymous(UserId='dave')
                    ],
                    'scope': Anonymous(ReviewScopeId='special')
                }
            ]
        },
        'status_code': 200
    }
}
