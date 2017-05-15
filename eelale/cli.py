import click
import subprocess
import hashlib
import os
import logging
import shutil


logger = logging.getLogger(__name__)


def flatten(seqs):
    return [x for seq in seqs for x in seq]


class Builder:

    def __init__(self, base_image, python='python', build_dir='.eelale-build', wheel_dir=None, policy=None):
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
        return 'eelale_%s' % hashlib.sha256(self.dockerfile.encode('utf-8')).hexdigest()[:10]

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


@click.group()
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')


@main.command()
@click.option('--requirement', '-r', multiple=True, help='Install from the given requirements file. This option can be used multiple times.')
@click.option('--wheeldir', '-w', type=click.Path(), metavar='<dir>', help='Build wheels into <dir>, where the default is the current working directory.')
@click.option('--image', default='quay.io/pypa/manylinux1_x86_64')
@click.option('--python', default='/opt/python/cp36-cp36m/bin/python')
@click.option('--policy')
@click.option('--force-build', '-f', multiple=True)
@click.argument('package', nargs=-1)
def build(requirement, wheeldir, image, python, policy, force_build, package):
    builder = Builder(
        base_image=image,
        python=python,
        policy=policy,
    )

    def build_args():
        yield from package
        for req in requirement:
            yield '-r'
            yield builder.copy(req)

    try:
        wheel_paths = builder.build(*build_args(), force=force_build)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(str(e)) from e

    os.makedirs(wheeldir, exist_ok=True)
    for wheel_path in wheel_paths:
        os.rename(wheel_path, os.path.join(wheeldir, os.path.basename(wheel_path)))
