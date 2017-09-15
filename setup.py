#!/usr/bin/env python
from setuptools import setup

try:
    import pypandoc

    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = ""

packages = [
    'editor'
]

requires = [
    'numpy>=1.12.1'
    'Kivy>=1.10.0'
    'pillow>=2.1.0'
    'cython'
]

setup(
    name='spritex',
    version="0.1.3",
    description='A simple tool for extracting sprites from full frames. Useful for AI projects. ',
    long_description=long_description,
    author="codetorex",
    author_email='627572616b@gmail.com',
    packages=packages,
    include_package_data=True,
    install_requires=requires,
    entry_points={
        'console_scripts': ['spritex = editor:execute']
    },
    license='MIT License',
    url='https://github.com/codetorex/spritex',
    zip_safe=False,
    keywords=['spritex', 'sprite', 'extractor', 'unique color'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Multimedia :: Graphics :: Editors :: Raster-Based',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ]
)
