# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from tests.utilities import Anonymous, Masked, Variable


snapshots = Snapshot()

snapshots['test_email_delivery websocket messages'] = {
    'publish': [
        {
            'channel': [
                'extensions'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ExtensionId='test-extension'),
                'resource_name': 'extensions'
            }
        },
        {
            'channel': [
                'extensioninstallations'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ExtensionInstallationId='test-extension'),
                'resource_name': 'extensioninstallations'
            }
        },
        {
            'channel': [
                'extensions'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ExtensionId='email-delivery'),
                'resource_name': 'extensions'
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                    'value': False
                },
                'key': 'smtp.configured',
                'object_id': 10,
                'resource_name': 'systemevents',
                'title': 'Setting created'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.configured',
                'object_id': 109,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.address.host',
                'object_id': 110,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.address.port',
                'object_id': 111,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                    'value': False
                },
                'key': 'smtp.use_smtps',
                'object_id': 13,
                'resource_name': 'systemevents',
                'title': 'Setting created'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.use_smtps',
                'object_id': 112,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                    'value': False
                },
                'key': 'smtp.use_starttls',
                'object_id': 14,
                'resource_name': 'systemevents',
                'title': 'Setting created'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.use_starttls',
                'object_id': 113,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                },
                'key': 'smtp.credentials.username',
                'object_id': 15,
                'resource_name': 'systemevents',
                'title': 'Setting created'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.credentials.username',
                'object_id': 114,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                },
                'key': 'smtp.credentials.password',
                'object_id': 16,
                'resource_name': 'systemevents',
                'title': 'Setting created'
            }
        },
        {
            'channel': [
                'systemsettings'
            ],
            'message': {
                'action': 'created',
                'key': 'smtp.credentials.password',
                'object_id': 115,
                'resource_name': 'systemsettings'
            }
        },
        {
            'channel': [
                'extensioninstallations'
            ],
            'message': {
                'action': 'created',
                'object_id': Anonymous(ExtensionInstallationId='email-delivery'),
                'resource_name': 'extensioninstallations'
            }
        },
        {
            'channel': [
                'email/sent'
            ],
            'message': {
                'message_id': 'message-id-***',
                'sent': True
            }
        },
        {
            'channel': [
                'email/sent'
            ],
            'message': {
                'message_id': 'message-id-***',
                'reason': 'recipients refused',
                'recipients': [
                    'rejected@example.org'
                ],
                'sent': False
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                    'new_value': None,
                    'old_value': 'localhost'
                },
                'key': 'smtp.address.host',
                'object_id': 19,
                'resource_name': 'systemevents',
                'title': 'Value modified'
            }
        },
        {
            'channel': [
                'systemevents'
            ],
            'message': {
                'action': 'created',
                'category': 'settings',
                'data': {
                    'new_value': 25,
                    'old_value': 40505
                },
                'key': 'smtp.address.port',
                'object_id': 20,
                'resource_name': 'systemevents',
                'title': 'Value modified'
            }
        },
        {
            'channel': [
                "extensioninstallations/<Anonymous(ExtensionInstallationId='email-delivery')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(ExtensionInstallationId='email-delivery'),
                'resource_name': 'extensioninstallations'
            }
        },
        {
            'channel': [
                "extensions/<Anonymous(ExtensionId='email-delivery')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(ExtensionId='email-delivery'),
                'resource_name': 'extensions'
            }
        },
        {
            'channel': [
                "extensioninstallations/<Anonymous(ExtensionInstallationId='test-extension')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(ExtensionInstallationId='test-extension'),
                'resource_name': 'extensioninstallations'
            }
        },
        {
            'channel': [
                "extensions/<Anonymous(ExtensionId='test-extension')>"
            ],
            'message': {
                'action': 'deleted',
                'object_id': Anonymous(ExtensionId='test-extension'),
                'resource_name': 'extensions'
            }
        }
    ]
}

snapshots['test_email_delivery created extensions: test-extension'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/extensions',
        'payload': {
            'name': 'test-extension-***',
            'system': True,
            'url': 'git://extensions/test-extension.git'
        },
        'query': {
            'fields': '-versions',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'extensions': [
                {
                    'id': Anonymous(ExtensionId='test-extension'),
                    'installation': None,
                    'is_partial': True,
                    'key': 'test-extension-***',
                    'name': 'test-extension-***',
                    'publisher': None,
                    'url': 'git://extensions/test-extension.git'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_email_delivery fetched extensionversions: test-extension'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/extensions/<Anonymous(ExtensionId='test-extension')>/extensionversions",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'extensionversions': [
                {
                    'extension': Anonymous(ExtensionId='test-extension'),
                    'id': Anonymous(ExtensionVersionId='test-extension'),
                    'name': None,
                    'sha1': Anonymous(ExtensionVersionSHA11='test-extension')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_email_delivery created extensioninstallations: test-extension'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/extensioninstallations',
        'payload': {
            'extension': Anonymous(ExtensionId='test-extension'),
            'universal': True,
            'version': Anonymous(ExtensionVersionId='test-extension')
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'extensioninstallations': [
                {
                    'extension': Anonymous(ExtensionId='test-extension'),
                    'id': Anonymous(ExtensionInstallationId='test-extension'),
                    'manifest': {
                        'ui_addons': [
                        ]
                    },
                    'user': None,
                    'version': Anonymous(ExtensionVersionId='test-extension')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_email_delivery created extensions: email-delivery'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/extensions',
        'payload': {
            'name': 'email-delivery-***',
            'system': True,
            'url': 'git://extensions/email-delivery.git'
        },
        'query': {
            'fields': '-versions',
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'extensions': [
                {
                    'id': Anonymous(ExtensionId='email-delivery'),
                    'installation': None,
                    'is_partial': True,
                    'key': 'email-delivery-***',
                    'name': 'email-delivery-***',
                    'publisher': None,
                    'url': 'git://extensions/email-delivery.git'
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_email_delivery fetched extensionversions: email-delivery'] = {
    'request': {
        'method': 'GET',
        'path': "api/v1/extensions/<Anonymous(ExtensionId='email-delivery')>/extensionversions",
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'extensionversions': [
                {
                    'extension': Anonymous(ExtensionId='email-delivery'),
                    'id': Anonymous(ExtensionVersionId='email-delivery'),
                    'name': None,
                    'sha1': Anonymous(ExtensionVersionSHA11='email-delivery')
                }
            ]
        },
        'status_code': 200
    }
}

snapshots['test_email_delivery created extensioninstallations: email-delivery'] = {
    'request': {
        'method': 'POST',
        'path': 'api/v1/extensioninstallations',
        'payload': {
            'extension': Anonymous(ExtensionId='email-delivery'),
            'universal': True,
            'version': Anonymous(ExtensionVersionId='email-delivery')
        },
        'query': {
            'output_format': 'static'
        }
    },
    'response': {
        'data': {
            'extensioninstallations': [
                {
                    'extension': Anonymous(ExtensionId='email-delivery'),
                    'id': Anonymous(ExtensionInstallationId='email-delivery'),
                    'manifest': {
                        'ui_addons': [
                        ]
                    },
                    'user': None,
                    'version': Anonymous(ExtensionVersionId='email-delivery')
                }
            ]
        },
        'status_code': 200
    }
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
