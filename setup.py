from setuptools import setup
import sys

with open('README.md') as f:
    long_description = f.read()

if sys.version_info[:3] < (3, 6, 1):
    raise Exception("websockets requires Python >= 3.6.1.")


setup(name='cgxsh',
      version='0.0.1b1',
      description='Command-line access to the controller-based CloudGenix ION Troubleshooting Toolkit.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/ebob9/cgxsh',
      author='Aaron Edwards',
      author_email='cgxsh@ebob9.com',
      license='MIT',
      install_requires=[
            'cloudgenix >= 5.2.1b1',
            'fuzzywuzzy >= 0.17.0',
            'pyyaml >= 3.13'
      ],
      packages=['cgxsh_lib'],
      classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: End Users/Desktop",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
      ],
      python_requires='>=3.6.1',
      entry_points={
            'console_scripts': [
                  'cgxsh = cgxsh_lib:toolkit_client',
            ]
      },
      )
