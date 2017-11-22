# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Frozen, Masked, Variable


snapshots = Snapshot()

snapshots['test_push_branch websocket messages'] = {
    'publish': [
        {
            'channel': [
                'repositories'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryId='test_push_branch'),
                'resource_name': 'repositories'
            }
        },
        {
            'channel': [
                "repositories/<Anonymous(RepositoryId='test_push_branch')>"
            ],
            'message': {
                'action': 'modified',
                'object_id': Anonymous(RepositoryId='test_push_branch'),
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
                'repository_id': Anonymous(RepositoryId='test_push_branch'),
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
                'object_id': Anonymous(BranchUpdateId=Variable(6)),
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
                'repository_id': Anonymous(RepositoryId='test_push_branch'),
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
                'object_id': Anonymous(BranchUpdateId=Variable(1)),
                'resource_name': 'branchupdates'
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
                'branchupdates',
                "branches/<Anonymous(BranchId='branch1')>/branchupdates"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(3)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                'branchupdates',
                "branches/<Anonymous(BranchId='branch1')>/branchupdates"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(4)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                'branchupdates',
                "branches/<Anonymous(BranchId='branch1')>/branchupdates"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(5)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                'branchupdates',
                "branches/<Anonymous(BranchId='master')>/branchupdates"
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(BranchUpdateId=Variable(7)),
                'resource_name': 'branchupdates'
            }
        },
        {
            'channel': [
                "branches/<Anonymous(BranchId='branch1')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(BranchId='branch1'),
                'resource_name': 'branches'
            }
        },
        {
            'channel': [
                "repositories/<Anonymous(RepositoryId='test_push_branch')>"
            ],
            'message': {
                'action': 'deleted',
                'name': 'test_push_branch',
                'object_id': Anonymous(RepositoryId='test_push_branch'),
                'path': Anonymous(RepositoryPath='test_push_branch'),
                'resource_name': 'repositories'
            }
        }
    ]
}

snapshots['test_push_branch 1'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        "remote: Branch created based on 'master', with 3 associated commits:        ",
        'remote:   http://critic.example.org/log?repository=test_push_branch&branch=branch1        ',
        'remote: To create a review of all 3 commits:        ',
        'remote:   http://critic.example.org/createreview?repository=test_push_branch&branch=branch1        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        ' * [new branch]                                                                        branch1 -> branch1'
    ],
    'stdout': [
        "Branch 'branch1' set up to track remote branch 'branch1' from 'origin'."
    ]
}

snapshots['test_push_branch 2'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'include': 'commits,branchupdates',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'branches': [
                {
                    'base_branch': Anonymous(BranchId='master'),
                    'head': Anonymous(CommitId='third'),
                    'id': Anonymous(BranchId='branch1'),
                    'is_archived': False,
                    'is_merged': False,
                    'name': 'branch1',
                    'repository': Anonymous(RepositoryId='test_push_branch'),
                    'size': 3,
                    'type': 'normal',
                    'updates': [
                        Anonymous(BranchUpdateId=Variable(1))
                    ]
                }
            ],
            'linked': {
                'branchupdates': set([
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='third'),
                            Anonymous(CommitId='first'),
                            Anonymous(CommitId='second')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': None,
                        'id': Anonymous(BranchUpdateId=Variable(1)),
                        'output': '''Branch created based on 'master', with 3 associated commits:
  http://critic.example.org/log?repository=test_push_branch&branch=branch1
To create a review of all 3 commits:
  http://critic.example.org/createreview?repository=test_push_branch&branch=branch1''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='third'),
                        'updater': Anonymous(UserId='alice')
                    })
                ]),
                'commits': set([
                    Frozen({
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
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(1))
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(3))
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_push_branch 3'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        'remote: Associated 1 new commit to the branch.        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        "   <CommitSHA1='third'>..<CommitSHA1='fourth'>  branch1 -> branch1"
    ],
    'stdout': [
    ]
}

snapshots['test_push_branch 4'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'include': 'commits,branchupdates',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'branches': [
                {
                    'base_branch': Anonymous(BranchId='master'),
                    'head': Anonymous(CommitId='fourth'),
                    'id': Anonymous(BranchId='branch1'),
                    'is_archived': False,
                    'is_merged': False,
                    'name': 'branch1',
                    'repository': Anonymous(RepositoryId='test_push_branch'),
                    'size': 4,
                    'type': 'normal',
                    'updates': [
                        Anonymous(BranchUpdateId=Variable(2)),
                        Anonymous(BranchUpdateId=Variable(1))
                    ]
                }
            ],
            'linked': {
                'branchupdates': set([
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='third'),
                            Anonymous(CommitId='first'),
                            Anonymous(CommitId='second')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': None,
                        'id': Anonymous(BranchUpdateId=Variable(1)),
                        'output': '''Branch created based on 'master', with 3 associated commits:
  http://critic.example.org/log?repository=test_push_branch&branch=branch1
To create a review of all 3 commits:
  http://critic.example.org/createreview?repository=test_push_branch&branch=branch1''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='third'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='third'),
                        'id': Anonymous(BranchUpdateId=Variable(2)),
                        'output': 'Associated 1 new commit to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='fourth'),
                        'updater': Anonymous(UserId='alice')
                    })
                ]),
                'commits': set([
                    Frozen({
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
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(1))
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(3))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='fourth'),
                        'message': '''fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='fourth'),
                        'summary': 'fourth',
                        'tree': Anonymous(TreeSHA1=Variable(4))
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_push_branch 5'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        'remote: Associated 1 new commit to the branch.        ',
        'remote: Disassociated 1 old commit from the branch.        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        " + <CommitSHA1='fourth'>...<CommitSHA1='amended-fourth'> branch1 -> branch1 (forced update)"
    ],
    'stdout': [
    ]
}

snapshots['test_push_branch 6'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'include': 'commits,branchupdates',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'branches': [
                {
                    'base_branch': Anonymous(BranchId='master'),
                    'head': Anonymous(CommitId='amended-fourth'),
                    'id': Anonymous(BranchId='branch1'),
                    'is_archived': False,
                    'is_merged': False,
                    'name': 'branch1',
                    'repository': Anonymous(RepositoryId='test_push_branch'),
                    'size': 4,
                    'type': 'normal',
                    'updates': [
                        Anonymous(BranchUpdateId=Variable(3)),
                        Anonymous(BranchUpdateId=Variable(2)),
                        Anonymous(BranchUpdateId=Variable(1))
                    ]
                }
            ],
            'linked': {
                'branchupdates': set([
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='amended-fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'from_head': Anonymous(CommitId='fourth'),
                        'id': Anonymous(BranchUpdateId=Variable(3)),
                        'output': '''Associated 1 new commit to the branch.
Disassociated 1 old commit from the branch.''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='amended-fourth'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='third'),
                        'id': Anonymous(BranchUpdateId=Variable(2)),
                        'output': 'Associated 1 new commit to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='fourth'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='third'),
                            Anonymous(CommitId='first'),
                            Anonymous(CommitId='second')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': None,
                        'id': Anonymous(BranchUpdateId=Variable(1)),
                        'output': '''Branch created based on 'master', with 3 associated commits:
  http://critic.example.org/log?repository=test_push_branch&branch=branch1
To create a review of all 3 commits:
  http://critic.example.org/createreview?repository=test_push_branch&branch=branch1''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='third'),
                        'updater': Anonymous(UserId='alice')
                    })
                ]),
                'commits': set([
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(3))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='amended-fourth'),
                        'message': '''amended-fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='amended-fourth'),
                        'summary': 'amended-fourth',
                        'tree': Anonymous(TreeSHA1=Variable(5))
                    }),
                    Frozen({
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
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='fourth'),
                        'message': '''fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='fourth'),
                        'summary': 'fourth',
                        'tree': Anonymous(TreeSHA1=Variable(4))
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(1))
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_push_branch 7'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        'remote: Associated 2 new commits to the branch.        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        "   <CommitSHA1='amended-fourth'>..<CommitSHA1='merge-branch1-branch2'>  branch1 -> branch1"
    ],
    'stdout': [
    ]
}

snapshots['test_push_branch 8'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'include': 'commits,branchupdates',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'branches': [
                {
                    'base_branch': Anonymous(BranchId='master'),
                    'head': Anonymous(CommitId='merge-branch1-branch2'),
                    'id': Anonymous(BranchId='branch1'),
                    'is_archived': False,
                    'is_merged': False,
                    'name': 'branch1',
                    'repository': Anonymous(RepositoryId='test_push_branch'),
                    'size': 6,
                    'type': 'normal',
                    'updates': [
                        Anonymous(BranchUpdateId=Variable(4)),
                        Anonymous(BranchUpdateId=Variable(3)),
                        Anonymous(BranchUpdateId=Variable(2)),
                        Anonymous(BranchUpdateId=Variable(1))
                    ]
                }
            ],
            'linked': {
                'branchupdates': set([
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='amended-fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'from_head': Anonymous(CommitId='fourth'),
                        'id': Anonymous(BranchUpdateId=Variable(3)),
                        'output': '''Associated 1 new commit to the branch.
Disassociated 1 old commit from the branch.''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='amended-fourth'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='third'),
                        'id': Anonymous(BranchUpdateId=Variable(2)),
                        'output': 'Associated 1 new commit to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='fourth'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='third'),
                            Anonymous(CommitId='first'),
                            Anonymous(CommitId='second')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': None,
                        'id': Anonymous(BranchUpdateId=Variable(1)),
                        'output': '''Branch created based on 'master', with 3 associated commits:
  http://critic.example.org/log?repository=test_push_branch&branch=branch1
To create a review of all 3 commits:
  http://critic.example.org/createreview?repository=test_push_branch&branch=branch1''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='third'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='merge-branch1-branch2'),
                            Anonymous(CommitId='side1')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='amended-fourth'),
                        'id': Anonymous(BranchUpdateId=Variable(4)),
                        'output': 'Associated 2 new commits to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='merge-branch1-branch2'),
                        'updater': Anonymous(UserId='alice')
                    })
                ]),
                'commits': set([
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(3))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='amended-fourth'),
                        'message': '''amended-fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='amended-fourth'),
                        'summary': 'amended-fourth',
                        'tree': Anonymous(TreeSHA1=Variable(5))
                    }),
                    Frozen({
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
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='fourth'),
                        'message': '''fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='fourth'),
                        'summary': 'fourth',
                        'tree': Anonymous(TreeSHA1=Variable(4))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='merge-branch1-branch2'),
                        'message': '''Merge branch 'branch2' into branch1
''',
                        'parents': [
                            Anonymous(CommitId='amended-fourth'),
                            Anonymous(CommitId='side1')
                        ],
                        'sha1': Anonymous(CommitSHA1='merge-branch1-branch2'),
                        'summary': "Merge branch 'branch2' into branch1",
                        'tree': Anonymous(TreeSHA1=Variable(6))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='side1'),
                        'message': '''side1
''',
                        'parents': [
                            Anonymous(CommitId='second')
                        ],
                        'sha1': Anonymous(CommitSHA1='side1'),
                        'summary': 'side1',
                        'tree': Anonymous(TreeSHA1=Variable(7))
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(1))
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_push_branch 9'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        'remote: Associated 1 new commit to the branch.        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        "   <CommitSHA1='merge-branch1-branch2'>..<CommitSHA1='merge-branch1-branch3'>  branch1 -> branch1"
    ],
    'stdout': [
    ]
}

snapshots['test_push_branch 10'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'include': 'commits,branchupdates',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'branches': [
                {
                    'base_branch': Anonymous(BranchId='master'),
                    'head': Anonymous(CommitId='merge-branch1-branch3'),
                    'id': Anonymous(BranchId='branch1'),
                    'is_archived': False,
                    'is_merged': False,
                    'name': 'branch1',
                    'repository': Anonymous(RepositoryId='test_push_branch'),
                    'size': 7,
                    'type': 'normal',
                    'updates': [
                        Anonymous(BranchUpdateId=Variable(5)),
                        Anonymous(BranchUpdateId=Variable(4)),
                        Anonymous(BranchUpdateId=Variable(3)),
                        Anonymous(BranchUpdateId=Variable(2)),
                        Anonymous(BranchUpdateId=Variable(1))
                    ]
                }
            ],
            'linked': {
                'branchupdates': set([
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='amended-fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'from_head': Anonymous(CommitId='fourth'),
                        'id': Anonymous(BranchUpdateId=Variable(3)),
                        'output': '''Associated 1 new commit to the branch.
Disassociated 1 old commit from the branch.''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='amended-fourth'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='merge-branch1-branch3')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='merge-branch1-branch2'),
                        'id': Anonymous(BranchUpdateId=Variable(5)),
                        'output': 'Associated 1 new commit to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='merge-branch1-branch3'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='third'),
                            Anonymous(CommitId='first'),
                            Anonymous(CommitId='second')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': None,
                        'id': Anonymous(BranchUpdateId=Variable(1)),
                        'output': '''Branch created based on 'master', with 3 associated commits:
  http://critic.example.org/log?repository=test_push_branch&branch=branch1
To create a review of all 3 commits:
  http://critic.example.org/createreview?repository=test_push_branch&branch=branch1''',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='third'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='fourth')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='third'),
                        'id': Anonymous(BranchUpdateId=Variable(2)),
                        'output': 'Associated 1 new commit to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='fourth'),
                        'updater': Anonymous(UserId='alice')
                    }),
                    Frozen({
                        'associated': set([
                            Anonymous(CommitId='merge-branch1-branch2'),
                            Anonymous(CommitId='side1')
                        ]),
                        'branch': Anonymous(BranchId='branch1'),
                        'disassociated': set([
                        ]),
                        'from_head': Anonymous(CommitId='amended-fourth'),
                        'id': Anonymous(BranchUpdateId=Variable(4)),
                        'output': 'Associated 2 new commits to the branch.',
                        'timestamp': Anonymous(Timestamp=Masked()),
                        'to_head': Anonymous(CommitId='merge-branch1-branch2'),
                        'updater': Anonymous(UserId='alice')
                    })
                ]),
                'commits': set([
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(3))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='amended-fourth'),
                        'message': '''amended-fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='amended-fourth'),
                        'summary': 'amended-fourth',
                        'tree': Anonymous(TreeSHA1=Variable(5))
                    }),
                    Frozen({
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
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='merge-branch1-branch3'),
                        'message': '''Merge branch 'branch3' into branch1
''',
                        'parents': [
                            Anonymous(CommitId='merge-branch1-branch2'),
                            Anonymous(CommitId=Variable(2))
                        ],
                        'sha1': Anonymous(CommitSHA1='merge-branch1-branch3'),
                        'summary': "Merge branch 'branch3' into branch1",
                        'tree': Anonymous(TreeSHA1=Variable(8))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='fourth'),
                        'message': '''fourth
''',
                        'parents': [
                            Anonymous(CommitId='third')
                        ],
                        'sha1': Anonymous(CommitSHA1='fourth'),
                        'summary': 'fourth',
                        'tree': Anonymous(TreeSHA1=Variable(4))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='merge-branch1-branch2'),
                        'message': '''Merge branch 'branch2' into branch1
''',
                        'parents': [
                            Anonymous(CommitId='amended-fourth'),
                            Anonymous(CommitId='side1')
                        ],
                        'sha1': Anonymous(CommitSHA1='merge-branch1-branch2'),
                        'summary': "Merge branch 'branch2' into branch1",
                        'tree': Anonymous(TreeSHA1=Variable(6))
                    }),
                    Frozen({
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
                        'id': Anonymous(CommitId='side1'),
                        'message': '''side1
''',
                        'parents': [
                            Anonymous(CommitId='second')
                        ],
                        'sha1': Anonymous(CommitSHA1='side1'),
                        'summary': 'side1',
                        'tree': Anonymous(TreeSHA1=Variable(7))
                    }),
                    Frozen({
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
                        'tree': Anonymous(TreeSHA1=Variable(1))
                    })
                ])
            }
        },
        'status_code': 200
    }
}

snapshots['test_push_branch 11'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        'remote: Associated 9 new commits to the branch.        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        "   <CommitSHA1='initial'>..<CommitSHA1='merge-master-branch1'>  master -> master"
    ],
    'stdout': [
    ]
}

snapshots['test_push_branch 12'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'branches': [
                {
                    'base_branch': Anonymous(BranchId='master'),
                    'head': Anonymous(CommitId='merge-branch1-branch3'),
                    'id': Anonymous(BranchId='branch1'),
                    'is_archived': False,
                    'is_merged': True,
                    'name': 'branch1',
                    'repository': Anonymous(RepositoryId='test_push_branch'),
                    'size': 7,
                    'type': 'normal',
                    'updates': [
                        Anonymous(BranchUpdateId=Variable(5)),
                        Anonymous(BranchUpdateId=Variable(4)),
                        Anonymous(BranchUpdateId=Variable(3)),
                        Anonymous(BranchUpdateId=Variable(2)),
                        Anonymous(BranchUpdateId=Variable(1))
                    ]
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_push_branch 13'] = {
    'returncode': 0,
    'stderr': [
        'remote: ',
        'remote: Deleted branch with 7 associated commits.        ',
        'remote: ',
        'To http://critic.example.org/test_push_branch.git',
        ' - [deleted]                                                                           branch1'
    ],
    'stdout': [
    ]
}

snapshots['test_push_branch 14'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/branches/<Anonymous(BranchId='branch1')>",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'error': {
                'code': None,
                'message': 'Invalid branch id used: ****',
                'title': 'No such resource'
            }
        },
        'status_code': 404
    }
}
