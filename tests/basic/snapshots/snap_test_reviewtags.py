# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_reviewtags initial'] = {
    'bob': [
        'assigned',
        'available',
        'pending'
    ],
    'carol': [
        'assigned',
        'available',
        'pending'
    ],
    'dave': [
        'assigned',
        'available',
        'pending'
    ]
}

snapshots['test_reviewtags bob: with draft reviewing'] = {
    'bob': [
        'active',
        'assigned',
        'available',
        'primary',
        'unpublished',
        'would_be_accepted'
    ],
    'carol': [
        'assigned',
        'available',
        'pending'
    ],
    'dave': [
        'assigned',
        'available',
        'pending'
    ]
}

snapshots['test_reviewtags bob: with draft issue'] = {
    'bob': [
        'active',
        'assigned',
        'available',
        'primary',
        'unpublished'
    ],
    'carol': [
        'assigned',
        'available',
        'pending'
    ],
    'dave': [
        'assigned',
        'available',
        'pending'
    ]
}

snapshots['test_reviewtags bob: after publish'] = {
    'bob': [
        'active',
        'assigned',
        'primary'
    ],
    'carol': [
        'assigned',
        'unseen'
    ],
    'dave': [
        'assigned',
        'unseen'
    ]
}

snapshots['test_reviewtags after followup commit'] = {
    'bob': [
        'active',
        'assigned',
        'pending',
        'primary'
    ],
    'carol': [
        'assigned',
        'pending'
    ],
    'dave': [
        'assigned',
        'pending'
    ]
}

snapshots['test_reviewtags carol: with draft reviewing'] = {
    'bob': [
        'active',
        'assigned',
        'pending',
        'primary'
    ],
    'carol': [
        'active',
        'assigned',
        'unpublished'
    ],
    'dave': [
        'assigned',
        'pending'
    ]
}

snapshots['test_reviewtags carol: with draft resolved issue'] = {
    'bob': [
        'active',
        'assigned',
        'pending',
        'primary'
    ],
    'carol': [
        'active',
        'assigned',
        'unpublished',
        'would_be_accepted'
    ],
    'dave': [
        'assigned',
        'pending'
    ]
}

snapshots['test_reviewtags carol: after publish'] = {
    'bob': [
        'active',
        'assigned',
        'unseen'
    ],
    'carol': [
        'active',
        'assigned'
    ],
    'dave': [
        'assigned',
        'unseen'
    ]
}
