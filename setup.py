from setuptools import setup

reqs = [line.strip() for line in open('requirements.txt')]

def readme():
    with open('README.md') as f:
        return f.read()

kwargs = {
    'name': 'kuberr',
    'author': 'Micah Wengren',
    'author_email': 'micah.wengren@gmail.com',
    'url': 'https://github.com/mwengren/kuberr',
    'description': 'Kubernetes API client to configure ERDDAP, in conjunction with ERDDAP Helm chart',
    'long_description': 'readme()',
    'entry_points': {
        'console_scripts': [
            'erddap-config=kuberr.erddap_config:main',
        ]
    },
    'classifiers': [
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: GIS'
    ],
    'packages': ['kuberr'],
    'package_data': {
        
    },
    'version': '0.1.0',
}

kwargs['install_requires'] = reqs

setup(**kwargs)
