"""配置管理模块 - 读写 config.ini，管理数据根目录和项目号规则"""
import configparser
import os

DEFAULT_CONFIG = {
    'general': {
        'data_root': '',
        'project_number_rule': '{type_prefix}-{yy}{mm}-{flow:03d}',
    },
    'project_types': {
        '研发': 'RD',
        '生产': 'PR',
        '外包': 'OS',
        '内部': 'IN',
    },
    'approval': {
        'requirement_stages': '项目经理,需求工程师',
        'drawing_stages': '项目经理,设计工程师',
        'bom_stages': '项目经理,设计工程师,文控/质量',
    }
}


class Config:
    def __init__(self, config_path='config.ini'):
        self.config_path = config_path
        self.parser = configparser.ConfigParser()
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            self.parser.read(self.config_path, encoding='utf-8')
        else:
            for section, values in DEFAULT_CONFIG.items():
                self.parser[section] = values
            self.save()

    def save(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.parser.write(f)

    def get(self, section, key, fallback=None):
        return self.parser.get(section, key, fallback=fallback)

    def set(self, section, key, value):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, value)
        self.save()

    @property
    def data_root(self):
        return self.get('general', 'data_root', '')

    @data_root.setter
    def data_root(self, value):
        self.set('general', 'data_root', value)

    @property
    def db_path(self):
        root = self.data_root
        if root:
            return os.path.join(root, 'project_data', 'database.db')
        return 'database.db'

    @property
    def upload_root(self):
        root = self.data_root
        if root:
            return os.path.join(root, 'project_data')
        return 'project_data'

    def get_project_types(self):
        if self.parser.has_section('project_types'):
            return dict(self.parser['project_types'])
        return DEFAULT_CONFIG['project_types']

    def get_approval_stages(self, module):
        key = f'{module}_stages'
        val = self.get('approval', key, '')
        return [s.strip() for s in val.split(',') if s.strip()] if val else []
