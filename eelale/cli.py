import click
import tempfile
import subprocess
import hashlib
import os
import textwrap
import shutil


def flatten(seqs):
    return [x for seq in seqs for x in seq]


class Builder:
    def __init__(self, base_image='ubuntu:xenial', script=None, python='python3', wheel_dir=None):
        self.base_image = base_image
        self.build_dir = os.path.abspath('.eelale')
        self.wheel_dir = wheel_dir or wheel_dir
        self.pip_version = None
        self.python = python
        self.script = script

    def vars(self):
        return {
            'baseimage': self.base_image,
            'python': self.python,
            'pip_version': '==%s' % self.pip_version if self.pip_version else '',
            'script': os.path.abspath(self.script) if self.script else None,
        }

    @property
    def dockerfile(self):
        return textwrap.dedent("""
            FROM {baseimage}
            VOLUME /eelale/wheels
            COPY provision.sh /eelale
            RUN /bin/bash /eelale/provision.sh
            RUN {python} -m pip install -U pip{pip_version}
            RUN {python} -m pip install auditwheel
        """).format(**self.vars()).strip()

    @property
    def image_name(self):
        h = hashlib.sha256(self.dockerfile.encode('utf-8'))
        if self.script:
            with open(self.script, 'rb') as f:
                h.update(f.read())
        return 'eelale_%s' % h.hexdigest()[:10]

    def create_image(self):
        os.makedirs(self.build_dir, exist_ok=True)
        with open(os.path.join(self.build_dir, 'Dockerfile'), 'w') as f:
            f.write(self.dockerfile)
        if self.script:
            shutil.copy(self.script, os.path.join(self.build_dir, 'provision.sh'))
        image_name = self.image_name
        subprocess.run([
            'docker', 'build', '--no-cache', '-t', image_name, self.build_dir
        ])

    def run(self, cmd):
        self.create_image()
        subprocess.run([
            'docker',
            'run',
            '--rm',
            '--volume', '%s:/eelale/wheels' % self.wheel_dir,
            self.image_name,
            *cmd
        ])

    def build(self, packages, force=(':none:',)):
        self.create_image()
        self.run([
            self.python,
            '-m', 'pip',
            'wheel',
            '--wheel-dir', '/eelale/wheels',
            '--no-deps',
            *flatten(('--no-binary', package) for package in force),
            *packages
        ])
        self.run([
            self.python,
            '-m', 'auditwheel',
            'repair', '--help',
        ])
        for name in os.listdir(self.build_dir):
            if name.endswith('.whl'):
                self.run([
                    self.python,
                    '-m', 'auditwheel',
                    'repair',
                    '--wheel-dir', '/eelale/wheels',
                    '/eelale/wheels/%s' % name,
                ])
                break


@click.group()
def main():
    pass


@main.command()
@click.option('--requirement', '-r', multiple=True)
@click.option('--wheeldir', '-w', type=click.Path(), default='.')
@click.option('--image', default='quay.io/pypa/manylinux1_x86_64')
@click.option('--python', default='/opt/python/cp36-cp36m/bin/python')
@click.option('--prepare')
@click.option('--manylinux1')
@click.option('--force-build', '-f', multiple=True)
@click.argument('package', nargs=-1)
def build(requirement, wheeldir, image, python, prepare, manylinux1, force_build, package):
    builder = Builder(
        base_image=image,
        python=python,
        wheel_dir=wheeldir,
        script=prepare,
    )
    print(builder.dockerfile)
    builder.build(package, force=force_build)

@main.command()
def repair():
    builder = Builder()
    builder.repair()
