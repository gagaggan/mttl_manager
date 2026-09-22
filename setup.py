"""FlaskFarm plugin bootstrap for MTTL-W01 management."""

from .mttl_client import MTTLClient

__menu = {
    'uri': __package__,
    'name': 'MTTL-W01 관리',
    'list': [
        {
            'uri': 'mttl',
            'name': 'MTTL-W01',
            'list': [
                {'uri': 'home', 'name': '상태'},
                {'uri': 'setting', 'name': '설정'},
            ],
        },
        {'uri': 'log', 'name': '로그'},
    ],
}

setting = {
    'filepath': __file__,
    'use_db': True,
    'use_default_setting': True,
    'home_module': 'mttl',
    'menu': __menu,
    'setting_menu': None,
    'default_route': 'normal',
}

from plugin import *  # noqa: E402,F401,F403

P = create_plugin_instance(setting)
P.mttl_client = MTTLClient()

from .mod_mttl import ModuleMTTL  # noqa: E402

P.set_module_list([ModuleMTTL])
