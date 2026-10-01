from pathlib import Path
from setuptools import find_namespace_packages, setup

requirements = [line.strip() for line in Path('requirements.txt').read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#')]
setup(
    name='tubesavely-server', version='1.0.0',
    description='Complete TubeSavely API backend',
    url='https://github.com/Cosymentx/TubeSavely-Server',
    project_urls={
        'Flutter app': 'https://github.com/Cosymentx/TubeSavely',
        'Vue web client': 'https://github.com/Cosymentx/TubeSavely-Vue',
        'API documentation': 'https://tube-savely-server.vercel.app/docs',
        'Issues': 'https://github.com/Cosymentx/TubeSavely-Server/issues',
    },
    packages=find_namespace_packages(include=['app', 'app.*']),
    python_requires='>=3.13', install_requires=requirements,
)
