"""FlaskFarm module for the MTTL-W01 backend."""

from .setup import *  # noqa: F401,F403

name = 'mttl'


class ModuleMTTL(PluginModuleBase):
    db_default = {
        'mttl_backend_url': 'http://127.0.0.1:8080',
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
            return render_template(
                f'{__package__}_{name}_home.html',
                health=self.P.mttl_client.health(),
                backend_url=self.P.mttl_client.base_url,
            )
        except Exception as exc:
            self.P.logger.error(f'Exception:{str(exc)}')
            self.P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f'{__package__}/{name}/{page}')

    def plugin_load(self):
        value = self.P.ModelSetting.get('mttl_backend_url') or 'http://127.0.0.1:8080'
        try:
            self.P.mttl_client.configure(value)
        except ValueError as exc:
            self.P.logger.warning(f'Invalid MTTL backend URL: {exc}')

    def setting_save_after(self, change_list):
        value = self.P.ModelSetting.get('mttl_backend_url') or 'http://127.0.0.1:8080'
        self.P.mttl_client.configure(value)
