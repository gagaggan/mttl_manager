"""FlaskFarm module for the MTTL-W01 backend."""

from .setup import *  # noqa: F401,F403
from .mttl_client import MTTLClientError

name = 'mttl'


class ModuleMTTL(PluginModuleBase):
    db_default = {
        'mttl_backend_url': 'http://127.0.0.1:8080',
        'mttl_public_url': '',
    }

    def __init__(self, P):
        super(ModuleMTTL, self).__init__(P, name=name, first_menu='home')

    def process_menu(self, page, req):
        try:
            settings = self.P.ModelSetting.to_dict()
            if page == 'setting':
                return render_template(
                    f'{__package__}_{name}_setting.html',
                    arg=settings,
                )

            self.P.mttl_client.configure(settings.get('mttl_backend_url', 'http://127.0.0.1:8080'))
            public_url = str(settings.get('mttl_public_url', '') or '').strip()
            if public_url:
                public_url = self.P.mttl_client.validate_base_url(public_url)
            return render_template(
                f'{__package__}_{name}_home.html',
                health=self.P.mttl_client.health(),
                backend_url=self.P.mttl_client.base_url,
                web_url=public_url or self.P.mttl_client.base_url,
            )
        except Exception as exc:
            self.P.logger.error(f'Exception:{str(exc)}')
            self.P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f'{__package__}/{name}/{page}')

    @staticmethod
    def _form_bool(req, key):
        return str(req.form.get(key, '')).strip().lower() in ('1', 'true', 'yes', 'on')

    def _ha_payload(self, req):
        host = self.P.mttl_client.validate_mqtt_host(req.form.get('host', ''))
        try:
            port = int(req.form.get('port', '1883'))
            power_threshold = float(req.form.get('power_threshold_w', '0.1'))
            power_interval = int(req.form.get('power_interval_s', '30'))
            energy_threshold = int(req.form.get('energy_threshold_wh', '1'))
            energy_interval = int(req.form.get('energy_interval_s', '60'))
        except (TypeError, ValueError) as exc:
            raise ValueError('MQTT 숫자 설정이 올바르지 않습니다') from exc
        if not 1 <= port <= 65535:
            raise ValueError('MQTT Port는 1~65535여야 합니다')
        if power_threshold not in (0.1, 0.2, 0.3, 0.5, 1.0):
            raise ValueError('Power 최소 변화량이 올바르지 않습니다')
        if power_interval not in (15, 30, 60, 120, 300, 600, 1800):
            raise ValueError('Power 보고 주기가 올바르지 않습니다')
        if energy_threshold not in (1, 2, 5, 10, 20):
            raise ValueError('Energy 최소 변화량이 올바르지 않습니다')
        if energy_interval not in (15, 30, 60, 120, 300, 600, 1800):
            raise ValueError('Energy 보고 주기가 올바르지 않습니다')
        payload = {
            'enabled': self._form_bool(req, 'enabled'),
            'host': host,
            'port': port,
            'username': str(req.form.get('username', '')),
            'tls': self._form_bool(req, 'tls'),
            'topic_prefix': self.P.mttl_client.validate_topic(req.form.get('topic_prefix', 'mttl'), 'State topic prefix'),
            'discovery_prefix': self.P.mttl_client.validate_topic(req.form.get('discovery_prefix', 'homeassistant'), 'Discovery prefix'),
            'birth_topic': self.P.mttl_client.validate_topic(req.form.get('birth_topic', 'homeassistant/status'), 'Birth topic'),
            'power_threshold_w': power_threshold,
            'power_interval_s': power_interval,
            'energy_threshold_wh': energy_threshold,
            'energy_interval_s': energy_interval,
        }
        mqtt_password = str(req.form.get('mqtt_password', ''))
        if mqtt_password:
            payload['password'] = mqtt_password
        return payload

    def process_command(self, command, arg1, arg2, arg3, req):
        if command not in ('ha_load', 'ha_test', 'ha_save', 'ha_sync'):
            return jsonify({'ok': False, 'error': '지원하지 않는 작업입니다'}), 400
        try:
            value = self.P.ModelSetting.get('mttl_backend_url') or 'http://127.0.0.1:8080'
            self.P.mttl_client.configure(value)
            admin_password = req.form.get('admin_password', '')
            if command == 'ha_load':
                result = self.P.mttl_client.admin_request(admin_password, 'GET', '/api/ha')
            elif command == 'ha_sync':
                result = self.P.mttl_client.admin_request(
                    admin_password, 'POST', '/api/ha/sync', require_changed_password=True
                )
            else:
                result = self.P.mttl_client.admin_request(
                    admin_password,
                    'POST' if command == 'ha_test' else 'PUT',
                    '/api/ha/test' if command == 'ha_test' else '/api/ha',
                    self._ha_payload(req),
                    require_changed_password=True,
                )
            return jsonify({'ok': True, 'ha': result})
        except (ValueError, MTTLClientError) as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400

    def plugin_load(self):
        value = self.P.ModelSetting.get('mttl_backend_url') or 'http://127.0.0.1:8080'
        try:
            self.P.mttl_client.configure(value)
        except ValueError as exc:
            self.P.logger.warning(f'Invalid MTTL backend URL: {exc}')

    def setting_save_after(self, change_list):
        value = self.P.ModelSetting.get('mttl_backend_url') or 'http://127.0.0.1:8080'
        self.P.mttl_client.configure(value)
        public_url = str(self.P.ModelSetting.get('mttl_public_url') or '').strip()
        if public_url:
            self.P.mttl_client.validate_base_url(public_url)
