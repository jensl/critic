# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Frozen, Masked, Variable


snapshots = Snapshot()

snapshots['test_install all users'] = {
    'request': {
        'method': 'GET',
        'path': 'api/v1/users',
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'users': [
                {
                    'fullname': 'Testing Administrator',
                    'id': Anonymous(UserId='admin'),
                    'name': 'admin',
                    'status': 'current'
                },
                {
                    'fullname': 'Alice von Testing',
                    'id': Anonymous(UserId='alice'),
                    'name': 'alice',
                    'status': 'current'
                },
                {
                    'fullname': 'Bob von Testing',
                    'id': Anonymous(UserId='bob'),
                    'name': 'bob',
                    'status': 'current'
                },
                {
                    'fullname': 'Carol von Testing',
                    'id': Anonymous(UserId='carol'),
                    'name': 'carol',
                    'status': 'current'
                },
                {
                    'fullname': 'Dave von Testing',
                    'id': Anonymous(UserId='dave'),
                    'name': 'dave',
                    'status': 'current'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_install as admin'] = {
    'request': {
        'method': 'GET',
        'path': 'api/v1/sessions/current',
        'query': {
            'include': 'users',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'users': set([
                    Frozen({
                        'email': 'admin@example.org',
                        'fullname': 'Testing Administrator',
                        'id': Anonymous(UserId='admin'),
                        'name': 'admin',
                        'password_status': 'set',
                        'roles': [
                            'administrator'
                        ],
                        'status': 'current'
                    })
                ])
            },
            'sessions': [
                {
                    'external_account': None,
                    'fields': [
                        {
                            'description': None,
                            'hidden': False,
                            'identifier': 'username',
                            'label': 'Username'
                        },
                        {
                            'description': None,
                            'hidden': True,
                            'identifier': 'password',
                            'label': 'Password'
                        }
                    ],
                    'providers': [
                    ],
                    'type': 'normal',
                    'user': Anonymous(UserId='admin')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_install as alice'] = {
    'request': {
        'method': 'GET',
        'path': 'api/v1/sessions/current',
        'query': {
            'include': 'users',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'linked': {
                'users': set([
                    Frozen({
                        'email': 'alice@example.org',
                        'fullname': 'Alice von Testing',
                        'id': Anonymous(UserId='alice'),
                        'name': 'alice',
                        'password_status': 'set',
                        'roles': [
                        ],
                        'status': 'current'
                    })
                ])
            },
            'sessions': [
                {
                    'external_account': None,
                    'fields': [
                        {
                            'description': None,
                            'hidden': False,
                            'identifier': 'username',
                            'label': 'Username'
                        },
                        {
                            'description': None,
                            'hidden': True,
                            'identifier': 'password',
                            'label': 'Password'
                        }
                    ],
                    'providers': [
                    ],
                    'type': 'normal',
                    'user': Anonymous(UserId='alice')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_critic_repo websocket messages'] = {
    'publish': [
        {
            'channel': [
                'repositories'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(RepositoryId='test_critic_repo'),
                'resource_name': 'repositories'
            }
        },
        {
            'channel': [
                "repositories/<Anonymous(RepositoryId='test_critic_repo')>"
            ],
            'message': {
                'action': 'modified',
                'object_id': Anonymous(RepositoryId='test_critic_repo'),
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
                'repository_id': Anonymous(RepositoryId='test_critic_repo'),
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
                "repositories/<Anonymous(RepositoryId='test_critic_repo')>"
            ],
            'message': {
                'action': 'deleted',
                'name': 'test_critic_repo',
                'object_id': Anonymous(RepositoryId='test_critic_repo'),
                'path': Anonymous(RepositoryPath='test_critic_repo'),
                'resource_name': 'repositories'
            }
        }
    ]
}

snapshots['test_install websocket messages'] = {
    'publish': [
    ]
}

snapshots['test_empty_repo 1'] = {
    'returncode': 0,
    'stderr': [
    ],
    'stdout': [
        "<CommitSHA1='initial'>\tHEAD",
        "<CommitSHA1='initial'>\trefs/heads/master"
    ]
}

snapshots['test_empty_repo websocket messages'] = {
    'publish': [
    ]
}
