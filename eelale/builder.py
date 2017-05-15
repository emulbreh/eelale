import subprocess
import hashlib
import os
import logging
import shutil


logger = logging.getLogger(__name__)


def flatten(seqs):
    return [x for seq in seqs for x in seq]


class Builder:

    def __init__(self, base_image, python='python', build_dir='.eelale-build', policy=None):
        self.base_image = base_image
        self.python = python
        self.build_dir = os.path.abspath(build_dir)
        self.policy = policy
        self.build_deps = ['pip', 'setuptools', 'auditwheel']

    @property
    def wheel_dir(self):
        return os.path.join(self.build_dir, 'wheels')

    @property
    def dockerfile(self):
        lines = [
            'FROM %s' % self.base_image,
            'VOLUME /eelale',
        ]
        for dep in self.build_deps:
            lines.append('RUN %s -m pip install -U %s' % (self.python, dep))
        return '\n'.join(lines)

    @property
    def image_name(self):
        image_hash = hashlib.sha256(self.dockerfile.encode('utf-8')).hexdigest()
        return 'eelale_%s' % image_hash[:10]

    def create_image(self):
        if os.path.exists(self.build_dir):
            logger.info('cleaning build dir')
            shutil.rmtree(self.build_dir)
        os.makedirs(self.build_dir, exist_ok=True)
        os.mkdir(self.wheel_dir)
        with open(os.path.join(self.build_dir, 'Dockerfile'), 'w') as f:
            f.write(self.dockerfile)
        image_name = self.image_name
        subprocess.run([
            'docker', 'build', '-t', image_name, self.build_dir
        ])

    def run(self, cmd):
        full_command = [
            'docker',
            'run',
            '--rm',
            '--volume', '%s:%s' % (self.build_dir, '/eelale'),
            self.image_name,
            *cmd
        ]
        logger.info(full_command)
        return subprocess.run(full_command, check=True)

    def copy(self, path):
        base, ext = os.path.splitext(path)
        filename = '%s%s' % (hashlib.sha1(base.encode('utf-8')).hexdigest(), ext)
        shutil.copy(path, os.path.join(self.build_dir, filename))
        return '/eelale/%s' % filename

    def build(self, *args, force=(':none:',)):
        self.create_image()
        self.run([
            self.python,
            '-m', 'pip',
            'wheel',
            '--wheel-dir', '/eelale/wheels',
            '--no-deps',
            *flatten(('--no-binary', package) for package in force),
            *args
        ])
        paths = []
        for name in os.listdir(self.wheel_dir):
            if not name.endswith('.whl'):
                continue
            if self.policy:
                self.run([
                    self.python,
                    '-m', 'auditwheel',
                    'repair',
                    '--wheel-dir', '/eelale/wheels',
                    '--plat', self.policy,
                    '/eelale/wheels/%s' % name,
                ])
            paths.append(os.path.join(self.wheel_dir, name))
        return paths
