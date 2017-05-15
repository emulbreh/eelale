from setuptools import setup, find_packages


with open('README.rst') as f:
    description = f.read()

setup(
    name='eelale',
    url='http://github.com/emulbreh/eelale/',
    version='0.3.0-dev',
    packages=find_packages(),
    license='BSD License',
    author='',
    maintainer='Johannes Dollinger',
    maintainer_email='emulbreh@googlemail.com',
    description='cross-compiles Python wheels',
    long_description=description,
    include_package_data=True,
    install_requires=[
        'click',
    ],
    entry_points={
        'console_scripts': [
            'eelale = eelale.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3'
    ]
)
