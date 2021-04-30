# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_email_delivery delivery notification 1'] = {
    'message_id': 'message-id-***',
    'sent': True
}

snapshots['test_email_delivery delivery notification 2'] = {
    'message_id': 'message-id-***',
    'reason': 'recipients refused',
    'recipients': [
        'rejected@example.org'
    ],
    'sent': False
}

snapshots['test_email_delivery received emails'] = [
    {
        'body': 'This is a test email.',
        'message-id': 'message-id-***',
        'recipients': [
            'Alice von Testing <alice@example.org>',
            'That Bob <bob@example.org>',
            'Someone Else <else@example.org>'
        ],
        'subject': 'Test email'
    }
]
