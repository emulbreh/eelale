import click
import tempfile
import subprocess
import hashlib
import os
import textwrap
import shutil
import logging


logger = logging.getLogger(__name__)


def flatten(seqs):
    return [x for seq in seqs for x in seq]


class Builder:
    def __init__(self, base_image='ubuntu:xenial', python='python3', wheel_dir=None, policy=None):
        self.base_image = base_image
        self.build_dir = os.path.abspath('.eelale')
        self.wheel_dir = os.path.abspath(wheel_dir) if wheel_dir else self.build_dir
        self.pip_version = None
        self.python = python
        self.policy = policy

    def vars(self):
        return {
            'baseimage': self.base_image,
            'python': self.python,
            'pip_version': '==%s' % self.pip_version if self.pip_version else '',
            'setuptools_version': '',
            'auditwheel_version': '',
        }

    @property
    def dockerfile(self):
        return textwrap.dedent("""
            FROM {baseimage}
            VOLUME /eelale/wheels
            RUN {python} -m pip install -U pip{pip_version}
            RUN {python} -m pip install setuptools{setuptools_version}
            RUN {python} -m pip install auditwheel{auditwheel_version}
        """).format(**self.vars()).strip()

    @property
    def image_name(self):
        return 'eelale_%s' % hashlib.sha256(self.dockerfile.encode('utf-8')).hexdigest()[:10]

    def create_image(self):
        os.makedirs(self.build_dir, exist_ok=True)
        with open(os.path.join(self.build_dir, 'Dockerfile'), 'w') as f:
            f.write(self.dockerfile)
        image_name = self.image_name
        subprocess.run([
            'docker', 'build', '-t', image_name, self.build_dir
        ])

    def run(self, cmd):
        self.create_image()
        full_command = [
            'docker',
            'run',
            '--rm',
            '--volume', '%s:/eelale/wheels' % self.wheel_dir,
            self.image_name,
            *cmd
        ]
        logger.info(full_command)
        return subprocess.run(full_command, check=True)

    def build(self, packages, force=(':none:',)):
        self.create_image()
        wheel_output = self.run([
            self.python,
            '-m', 'pip',
            'wheel',
            '--wheel-dir', '/eelale/wheels',
            '--no-deps',
            *flatten(('--no-binary', package) for package in force),
            *packages
        ])
        if self.policy:
            for name in os.listdir(self.wheel_dir):
                if name.endswith('.whl'):
                    self.run([
                        self.python,
                        '-m', 'auditwheel',
                        'repair',
                        '--wheel-dir', '/eelale/wheels',
                        '--plat', self.policy,
                        '/eelale/wheels/%s' % name,
                    ])


@click.group()
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')


@main.command()
@click.option('--requirement', '-r', multiple=True)
@click.option('--wheeldir', '-w', type=click.Path())
@click.option('--image', default='quay.io/pypa/manylinux1_x86_64')
@click.option('--python', default='/opt/python/cp36-cp36m/bin/python')
@click.option('--policy')
@click.option('--force-build', '-f', multiple=True)
@click.argument('package', nargs=-1)
def build(requirement, wheeldir, image, python, policy, force_build, package):
    builder = Builder(
        base_image=image,
        python=python,
        wheel_dir=wheeldir,
        policy=policy,
    )
    print(builder.dockerfile)
    try:
        builder.build(package, force=force_build)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(str(e)) from e
