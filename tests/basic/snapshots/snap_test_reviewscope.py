# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Frozen, Masked, Variable


snapshots = Snapshot()

snapshots['test_reviewscope websocket messages'] = {
    'publish': [
        {
            'channel': [
                'repositories'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryId='test_reviewscope'),
                'resource_name': 'repositories'
            }
        },
        {
            'channel': [
                "repositories/<Anonymous(RepositoryId='test_reviewscope')>"
            ],
            'message': {
                'action': 'modified',
                'object_id': Anonymous(RepositoryId='test_reviewscope'),
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
                'repository_id': Anonymous(RepositoryId='test_reviewscope'),
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
                'reviewscopes'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ReviewScopeId='special'),
                'resource_name': 'reviewscopes'
            }
        },
        {
            'channel': [
                'reviewscopefilters'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ReviewScopeFilterId='special'),
                'resource_name': 'reviewscopefilters'
            }
        },
        {
            'channel': [
                'repositoryfilters',
                "users/<Anonymous(UserId='bob')>/repositoryfilters"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryFilterId='bob'),
                'resource_name': 'repositoryfilters'
            }
        },
        {
            'channel': [
                'repositoryfilters',
                "users/<Anonymous(UserId='carol')>/repositoryfilters"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryFilterId='carol'),
                'resource_name': 'repositoryfilters'
            }
        },
        {
            'channel': [
                'repositoryfilters',
                "users/<Anonymous(UserId='dave')>/repositoryfilters"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryFilterId='dave'),
                'resource_name': 'repositoryfilters'
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
                'repository_id': Anonymous(RepositoryId='test_reviewscope'),
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
                'name': 'r/test_reviewscope',
                'object_id': Anonymous(BranchId=Variable(1)),
                'repository_id': Anonymous(RepositoryId='test_reviewscope'),
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
                'object_id': Anonymous(ReviewId='test_reviewscope'),
                'resource_name': 'reviews'
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'created',
                'object_id': Anonymous(ReviewEventId=Variable(1)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='test_reviewscope')
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
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'ready',
                'object_id': Anonymous(ReviewEventId=Variable(2)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='test_reviewscope')
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'published',
                'object_id': Anonymous(ReviewEventId=Variable(3)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='test_reviewscope')
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'batch',
                'object_id': Anonymous(ReviewEventId=Variable(4)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='test_reviewscope')
            }
        },
        {
            'channel': [
                'batches',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/batches"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BatchId=Variable(1)),
                'resource_name': 'batches'
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'batch',
                'object_id': Anonymous(ReviewEventId=Variable(5)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='test_reviewscope')
            }
        },
        {
            'channel': [
                'batches',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/batches"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BatchId=Variable(2)),
                'resource_name': 'batches'
            }
        },
        {
            'channel': [
                'reviewevents',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/reviewevents"
            ],
            'message': {
                'action': 'created',
                'event_type': 'batch',
                'object_id': Anonymous(ReviewEventId=Variable(6)),
                'resource_name': 'reviewevents',
                'review_id': Anonymous(ReviewId='test_reviewscope')
            }
        },
        {
            'channel': [
                'batches',
                "reviews/<Anonymous(ReviewId='test_reviewscope')>/batches"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BatchId=Variable(3)),
                'resource_name': 'batches'
            }
        },
        {
            'channel': [
                "reviews/<Anonymous(ReviewId='test_reviewscope')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(ReviewId='test_reviewscope'),
                'resource_name': 'reviews'
            }
        },
        {
            'channel': [
                'branches/<Anonymous(BranchId=Variable(1))>'
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(BranchId=Variable(1)),
                'resource_name': 'branches'
            }
        },
        {
            'channel': [
                "repositories/<Anonymous(RepositoryId='test_reviewscope')>"
            ],
            'message': {
                'action': 'deleted',
                'name': 'test_reviewscope',
                'object_id': Anonymous(RepositoryId='test_reviewscope'),
                'path': Anonymous(RepositoryPath='test_reviewscope'),
                'resource_name': 'repositories'
            }
        }
    ]
}

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
                        'name': 'special'
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

snapshots['test_reviewscope created repositoryfilters: carol'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/repositoryfilters',
        'payload': {
            'path': '/',
            'repository': Anonymous(RepositoryId='test_reviewscope'),
            'type': 'reviewer'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'repositoryfilters': [
                {
                    'default_scope': True,
                    'delegates': [
                    ],
                    'id': Anonymous(RepositoryFilterId='carol'),
                    'path': '/',
                    'repository': Anonymous(RepositoryId='test_reviewscope'),
                    'scopes': [
                    ],
                    'subject': Anonymous(UserId='carol'),
                    'type': 'reviewer'
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
        'remote:   http://critic.example.org/log?repository=test_reviewscope&branch=branch1        ',
        'remote: To create a review of the commit:        ',
        'remote:   http://critic.example.org/createreview?repository=test_reviewscope&branch=branch1        ',
        'remote: ',
        'To http://critic.example.org/test_reviewscope.git',
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

snapshots['test_reviewscope created repositoryfilters: bob'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/repositoryfilters',
        'payload': {
            'path': '/',
            'repository': Anonymous(RepositoryId='test_reviewscope'),
            'scopes': [
                Anonymous(ReviewScopeId='special')
            ],
            'type': 'reviewer'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'repositoryfilters': [
                {
                    'default_scope': True,
                    'delegates': [
                    ],
                    'id': Anonymous(RepositoryFilterId='bob'),
                    'path': '/',
                    'repository': Anonymous(RepositoryId='test_reviewscope'),
                    'scopes': [
                        Anonymous(ReviewScopeId='special')
                    ],
                    'subject': Anonymous(UserId='bob'),
                    'type': 'reviewer'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope created reviewscopes: special'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/reviewscopes',
        'payload': {
            'name': 'special'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'reviewscopes': [
                {
                    'id': Anonymous(ReviewScopeId='special'),
                    'name': 'special'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_reviewscope created reviewscopefilters: special'] = {
    'request': {
        'method': 'POST',
        'path': "api/v1/repositories/<Anonymous(RepositoryId='test_reviewscope')>/reviewscopefilters",
        'payload': {
            'included': True,
            'path': '**/*.special',
            'scope': Anonymous(ReviewScopeId='special')
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
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

snapshots['test_reviewscope created repositoryfilters: dave'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/repositoryfilters',
        'payload': {
            'default_scope': False,
            'path': '/',
            'repository': Anonymous(RepositoryId='test_reviewscope'),
            'scopes': [
                Anonymous(ReviewScopeId='special')
            ],
            'type': 'reviewer'
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'repositoryfilters': [
                {
                    'default_scope': False,
                    'delegates': [
                    ],
                    'id': Anonymous(RepositoryFilterId='dave'),
                    'path': '/',
                    'repository': Anonymous(RepositoryId='test_reviewscope'),
                    'scopes': [
                        Anonymous(ReviewScopeId='special')
                    ],
                    'subject': Anonymous(UserId='dave'),
                    'type': 'reviewer'
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
                        'id': Anonymous(FileId='created.special'),
                        'path': 'created.special'
                    }),
                    Frozen({
                        'id': Anonymous(FileId='created.regular'),
                        'path': 'created.regular'
                    })
                ]),
                'reviewscopes': set([
                    Frozen({
                        'id': Anonymous(ReviewScopeId='special'),
                        'name': 'special'
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
