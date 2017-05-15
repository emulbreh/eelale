import click
import subprocess
import os
import logging

from .builder import Builder


logger = logging.getLogger(__name__)


@click.group()
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )


@main.command()
@click.option(
    '--requirement', '-r',
    multiple=True,
    metavar='<file>',
    help='Install from the given requirements file. This option can be used multiple times.'
)
@click.option(
    '--wheeldir', '-w',
    type=click.Path(),
    default='.',
    metavar='<dir>',
    help='Build wheels into <dir>, where the default is the current working directory.'
)
@click.option(
    '--image',
    metavar='<image>',
    help='Build in a container based on <image>.',
)
@click.option(
    '--python',
    metavar='<path>',
    help='Use Python executable at <path> inside the container.',
)
@click.option(
    '--policy',
    metavar='<policy>',
    help='auditwheel policy, should be manylinux1_PLATFORM.',
)
@click.option(
    '--force-build',
    multiple=True,
    metavar='<package>',
    help='Build the given wheel inside the container even if a precompiled wheel is available. Set to :all: to force build all wheels. This option can be used multiple times.'
)
@click.argument('package', nargs=-1)
def build(requirement, wheeldir, image, python, policy, force_build, package):
    if not image:
        image = 'quay.io/pypa/manylinux1_x86_64'
        logger.info('Defaulting to manylinux1 image: %s' % image)
        if not python:
            python = '/opt/python/cp36-cp36m/bin/python'
    elif not python:
        python = 'python'

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
