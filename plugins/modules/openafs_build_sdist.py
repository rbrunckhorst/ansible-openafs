#!/usr/bin/python

# Copyright (c) 2021, Sine Nomine Associates
# BSD 2-Clause License

ANSIBLE_METADATA = {
    'metadata_version': '1.1.',
    'status': ['preview'],
    'supported_by': 'community',
}

DOCUMENTATION = r'''
---
module: openafs_build_sdist

short_description: Create OpenAFS source distribution archives from a git repo.

description:
  - Create OpenAFS source and document source distribution archives from
    a git checkout.

requirements:
  - git
  - autoconfig
  - automake
  - libtools
  - tar
  - gzip
  - bzip2
  - md5sum
  - pod2man

options:
  sdist:
    description:
      - The path on the remote node to write the source distribution files.
      - This path will be created if it does not exist.
    type: path
    required: true

  topdir:
    description: git project directory on the remote node.
    type: path
    default: C(openafs)

  logdir:
    description:
      - The path to write build log files on the remote node.
    type: path
    default: I(topdir)/.ansible

  tar:
    description: C(tar) program path
    type: path
    default: detected

  git:
    description: C(git) program path
    type: path
    default: detected

  gzip:
    description: C(gzip) program path
    type: path
    default: detected

  bzip2:
    description: C(bzip2) program path
    type: path
    default: detected

  md5sum:
    description: C(md5sum) program path
    type: path
    default: detected

author:
  - Michael Meffie
'''

EXAMPLES = r'''
- import_role:
    name: openafs_devel

- name: Checkout source.
  git:
    repo: "git://git.openafs.org/openafs.git"
    version: "openafs-stable-1_8_8"
    dest: "openafs"

- name: Make source distribution files.
  openafs_build_sdist:
    topdir: "openafs"
    sdist: "openafs/packages"
'''

RETURN = r'''
version:
  description: OpenAFS version
  returned: always
  type: dict

files:
  description: The list of sdist files created on the remote node.
  returned: always
  type: list
'''


import glob                    # noqa: E402
import os                      # noqa: E402
import re                      # noqa: E402
import shutil                  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.openafs_contrib.openafs.plugins.module_utils.common import Logger  # noqa: E402, E501
from ansible_collections.openafs_contrib.openafs.plugins.module_utils.common import chdir  # noqa: E402, E501
from ansible_collections.openafs_contrib.openafs.plugins.module_utils.common import tmpdir  # noqa: E402, E501
from ansible_collections.openafs_contrib.openafs.plugins.module_utils.common import execute  # noqa: E402, E501

# Globals
module_name = os.path.basename(__file__).replace('.py', '')
log = None
logdir = None
module = None
results = None


def expand_path(p):
    """
    Expand optional path to absolute path.
    """
    if p:
        p = os.path.abspath(os.path.expanduser(p))
    return p


def lookup_bin(name):
    """
    Lookup a binary path.

    Use the specified path if given, otherwise search the PATH for it. Use GNU
    tar on Solaris by default.
    """
    bin_ = module.params.get(name, None)
    if not bin_:
        if name == 'tar' and os.uname()[0] == 'SunOS':
            name = 'gtar'
        bin_ = module.get_bin_path(name, required=True)
    return bin_


def tostring(s):
    """
    Convert the object to string for py2/py3 compat.
    """
    try:
        s = s.decode()
    except (UnicodeDecodeError, AttributeError):
        pass
    return s


def extract_version_string():
    """
    Find the OpenAFS version string from the .version file if found,
    or the git describe.
    """
    if os.path.exists('.version'):
        with open('.version') as f:
            output = f.read().rstrip()
        if output.startswith('openafs-'):
            version = re.sub('openafs-[^-]*-', '', output).replace('_', '.')
        elif output.startswith('BP-'):
            version = re.sub('BP-openafs-[^-]*-', '', output).replace('_', '.')
        else:
            version = output  # Use the given version string.
    else:
        output = execute('git describe --abbrev=4 HEAD').rstrip()
        version = re.sub(r'^openafs-[^-]*-', '', output).replace('_', '.')
    log.info('version is %s' % version)
    results['version'] = version
    return version


def compress(format_, filename, destdir):
    """
    Create a compressed file and checksum file.
    """
    f2b = {
        'gz': 'gzip',
        'bz2': 'bzip2',
    }
    bin_ = lookup_bin(f2b[format_])
    md5sum = lookup_bin('md5sum')
    output = '%(destdir)s/%(filename)s.%(format_)s' % locals()
    execute('%(bin_)s <%(filename)s >%(output)s' % locals())
    execute('%(md5sum)s %(output)s >%(output)s.md5' % locals())
    results['files'].append(output)
    results['files'].append(output + '.md5')


def make_sdist(topdir, sdist):
    """
    Make source distribution files.
    """
    # Lookup bins
    tar = lookup_bin('tar')
    git = lookup_bin('git')

    # Create output directory if not present.
    if not os.path.exists(sdist):
        os.makedirs(sdist)

    # Get the version and change log.
    with chdir(topdir):
        version = extract_version_string()
        changelog = '%(sdist)s/ChangeLog' % locals()
        execute('%(git)s log >%(changelog)s' % locals())
        results['files'].append(changelog)

    # Make source archives.
    with tmpdir():
        # Extract source tree into temp dir.
        execute('(cd %(topdir)s &&'
                ' %(git)s archive'
                '  --format=tar'
                '  --prefix=openafs-%(version)s/  HEAD) |'
                ' %(tar)s xf -' % locals())

        # Generate configure, makefiles, and documents in temp dir.
        with chdir('openafs-%(version)s' % locals()):
            with open('.version', 'w') as f:
                f.write(version + '\n')
            execute('./regen.sh')

        # Create documentation and source archives.
        execute('%(tar)s cf'
                ' openafs-%(version)s-doc.tar'
                ' openafs-%(version)s/doc' % locals())
        shutil.rmtree('openafs-%(version)s/doc' % locals())
        execute('%(tar)s cf '
                ' openafs-%(version)s-src.tar'
                ' openafs-%(version)s' % locals())

        # Create compressed archives in destination directory.
        for archive in glob.glob('*.tar'):
            compress('gz', archive, sdist)
            compress('bz2', archive, sdist)


def main():
    global log
    global logdir
    global results
    global module
    results = dict(
        changed=False,
        version='',
        files=[],
    )
    module = AnsibleModule(
        argument_spec=dict(
            sdist=dict(type='path', required=True),
            topdir=dict(type='path', default='openafs'),
            logdir=dict(type='path', default=None),
            # bin paths
            git=dict(type='path', default=None),
            tar=dict(type='path', default=None),
            gzip=dict(type='path', default=None),
            bzip2=dict(type='path', default=None),
            md5sum=dict(type='path', default=None),
        ),
        supports_check_mode=False,
    )
    log = Logger(module_name)
    log.info('Starting %s', module_name)

    sdist = expand_path(module.params['sdist'])
    topdir = expand_path(module.params['topdir'])
    logdir = expand_path(module.params['logdir'])

    make_sdist(topdir, sdist)
    results['changed'] = True
    module.exit_json(**results)


if __name__ == '__main__':
    main()
