from setuptools import setup
import sys

with open('README.md') as f:
    long_description = f.read()

if sys.version_info[:3] < (3, 6, 1):
    raise Exception("cgxsh requires Python >= 3.6.1.")


setup(name='cgxsh',
      version='1.0.0b1',
      description='Command-line access to the controller-based CloudGenix ION Troubleshooting Toolkit.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/ebob9/cgxsh',
      author='Aaron Edwards',
      author_email='cgxsh@ebob9.com',
      license='MIT',
      install_requires=[
            'cloudgenix >= 5.2.1b1',
            'websockets >= 8.1',
            'fuzzywuzzy >= 0.17.0',
            'pyyaml >= 5.1.2',
            'tabulate >= 0.8.5',
            'cryptography >= 2.8'
      ],
      packages=['cgxsh_lib'],
      classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: System Administrators",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Operating System :: Microsoft :: Windows :: Windows 10",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: POSIX :: Linux",
            "Operating System :: Other OS",
            "Topic :: Terminals"
      ],
      python_requires='>=3.6.1',
      entry_points={
            'console_scripts': [
                  'cgxsh = cgxsh_lib:toolkit_client',
                  'cgxsh_generic_ws = cgxsh_lib:generic_client',
                  'cgxsh_edit_config = cgxsh_lib.file_crypto:edit_config_file',
                  'cgxsh_decrypt_config = cgxsh_lib.file_crypto:decrypt_config_file',
                  'cgxsh_encrypt_config = cgxsh_lib.file_crypto:encrypt_config_file',
                  'cgxsh_create_defaultconfig = cgxsh_lib.file_crypto:create_config_file'
            ]
      },
      )
