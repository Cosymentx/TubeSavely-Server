from pathlib import Path
from setuptools import find_namespace_packages, setup

requirements = [line.strip() for line in Path('requirements.txt').read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#')]
setup(
    name='tubesavely-server', version='1.0.0',
    description='Complete TubeSavely API backend',
    packages=find_namespace_packages(include=['app', 'app.*']),
    python_requires='>=3.13', install_requires=requirements,
)
