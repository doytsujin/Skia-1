#!/usr/bin/python2

# Copyright 2014 Google Inc.
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Skia's Chromium DEPS roll script.

This script:
- searches through the last N Skia git commits to find out the hash that is
  associated with the SVN revision number.
- creates a new branch in the Chromium tree, modifies the DEPS file to
  point at the given Skia commit, commits, uploads to Rietveld, and
  deletes the local copy of the branch.
- creates a whitespace-only commit and uploads that to to Rietveld.
- returns the Chromium tree to its previous state.

Usage:
  %prog -c CHROMIUM_PATH -r REVISION [OPTIONAL_OPTIONS]
"""


import optparse
import os
import re
import shutil
import subprocess
from subprocess import check_call
import sys
import tempfile


class DepsRollConfig(object):
    """Contains configuration options for this module.

    Attributes:
        git: (string) The git executable.
        chromium_path: (string) path to a local chromium git repository.
        save_branches: (boolean) iff false, delete temporary branches.
        verbose: (boolean)  iff false, suppress the output from git-cl.
        search_depth: (int) how far back to look for the revision.
        skia_url: (string) Skia's git repository.
        self.skip_cl_upload: (boolean)
        self.cl_bot_list: (list of strings)
    """

    # pylint: disable=I0011,R0903,R0902
    def __init__(self, options=None):
        self.skia_url = 'https://skia.googlesource.com/skia.git'
        self.revision_format = (
            'git-svn-id: http://skia.googlecode.com/svn/trunk@%d ')

        if not options:
            options = DepsRollConfig.GetOptionParser()
        # pylint: disable=I0011,E1103
        self.verbose = options.verbose
        self.save_branches = options.save_branches
        self.search_depth = options.search_depth
        self.chromium_path = options.chromium_path
        self.git = options.git_path
        self.skip_cl_upload = options.skip_cl_upload
        # Split and remove empty strigns from the bot list.
        self.cl_bot_list = [bot for bot in options.bots.split(',') if bot]
        self.skia_git_checkout_path = options.skia_git_path
        self.default_branch_name = 'autogenerated_deps_roll_branch'

    @staticmethod
    def GetOptionParser():
        # pylint: disable=I0011,C0103
        """Returns an optparse.OptionParser object.

        Returns:
            An optparse.OptionParser object.

        Called by the main() function.
        """
        default_bots_list = [
            'android_clang_dbg',
            'android_dbg',
            'android_rel',
            'cros_daisy',
            'linux',
            'linux_asan',
            'linux_chromeos',
            'linux_chromeos_asan',
            'linux_gpu',
            'linux_heapcheck',
            'linux_layout',
            'linux_layout_rel',
            'mac',
            'mac_asan',
            'mac_gpu',
            'mac_layout',
            'mac_layout_rel',
            'win',
            'win_gpu',
            'win_layout',
            'win_layout_rel',
            ]

        option_parser = optparse.OptionParser(usage=__doc__)
        # Anyone using this script on a regular basis should set the
        # CHROMIUM_CHECKOUT_PATH environment variable.
        option_parser.add_option(
            '-c', '--chromium_path', help='Path to local Chromium Git'
            ' repository checkout, defaults to CHROMIUM_CHECKOUT_PATH'
            ' if that environment variable is set.',
            default=os.environ.get('CHROMIUM_CHECKOUT_PATH'))
        option_parser.add_option(
            '-r', '--revision', type='int', default=None,
            help='The Skia SVN revision number, defaults to top of tree.')
        # Anyone using this script on a regular basis should set the
        # SKIA_GIT_CHECKOUT_PATH environment variable.
        option_parser.add_option(
            '', '--skia_git_path',
            help='Path of a pure-git Skia repository checkout.  If empty,'
            ' a temporary will be cloned.  Defaults to SKIA_GIT_CHECKOUT'
            '_PATH, if that environment variable is set.',
            default=os.environ.get('SKIA_GIT_CHECKOUT_PATH'))
        option_parser.add_option(
            '', '--search_depth', type='int', default=100,
            help='How far back to look for the revision.')
        option_parser.add_option(
            '', '--git_path', help='Git executable, defaults to "git".',
            default='git')
        option_parser.add_option(
            '', '--save_branches', help='Save the temporary branches',
            action='store_true', dest='save_branches', default=False)
        option_parser.add_option(
            '', '--verbose', help='Do not suppress the output from `git cl`.',
            action='store_true', dest='verbose', default=False)
        option_parser.add_option(
            '', '--skip_cl_upload', help='Skip the cl upload step; useful'
            ' for testing or with --save_branches.',
            action='store_true', default=False)

        default_bots_help = (
            'Comma-separated list of bots, defaults to a list of %d bots.'
            '  To skip `git cl try`, set this to an empty string.'
            % len(default_bots_list))
        default_bots = ','.join(default_bots_list)
        option_parser.add_option(
            '', '--bots', help=default_bots_help, default=default_bots)

        return option_parser


def test_git_executable(git_executable):
    """Test the git executable.

    Args:
        git_executable: git executable path.
    Returns:
        True if test is successful.
    """
    with open(os.devnull, 'w') as devnull:
        try:
            subprocess.call([git_executable, '--version'], stdout=devnull)
        except (OSError,):
            return False
    return True


class DepsRollError(Exception):
    """Exceptions specific to this module."""
    pass


def strip_output(*args, **kwargs):
    """Wrap subprocess.check_output and str.strip().

    Pass the given arguments into subprocess.check_output() and return
    the results, after stripping any excess whitespace.

    Args:
        *args: to be passed to subprocess.check_output()
        **kwargs: to be passed to subprocess.check_output()

    Returns:
        The output of the process as a string without leading or
        trailing whitespace.
    Raises:
        OSError or subprocess.CalledProcessError: raised by check_output.
    """
    return str(subprocess.check_output(*args, **kwargs)).strip()


def create_temp_skia_clone(config, depth):
    """Clones Skia in a temp dir.

    Args:
        config: (roll_deps.DepsRollConfig) object containing options.
        depth: (int) how far back to clone the tree.
    Returns:
        temporary directory path if succcessful.
    Raises:
        OSError, subprocess.CalledProcessError on failure.
    """
    git = config.git
    skia_dir = tempfile.mkdtemp(prefix='git_skia_tmp_')
    try:
        check_call(
            [git, 'clone', '-q', '--depth=%d' % depth,
             '--single-branch', config.skia_url, skia_dir])
        return skia_dir
    except (OSError, subprocess.CalledProcessError) as error:
        shutil.rmtree(skia_dir)
        raise error


def find_revision_and_hash(config, revision):
    """Finds revision number and git hash of origin/master in the Skia tree.

    Args:
        config: (roll_deps.DepsRollConfig) object containing options.
        revision: (int or None) SVN revision number.  If None, use
            tip-of-tree.

    Returns:
        A tuple (revision, hash)
            revision: (int) SVN revision number.
            hash: (string) full Git commit hash.

    Raises:
        roll_deps.DepsRollError: if the revision can't be found.
        OSError: failed to execute git or git-cl.
        subprocess.CalledProcessError: git returned unexpected status.
    """
    git = config.git
    use_temp = False
    skia_dir = None
    depth = 1 if (revision is None) else config.search_depth
    try:
        if config.skia_git_checkout_path:
            skia_dir = config.skia_git_checkout_path
            ## Update origin/master if needed.
            check_call([git, 'fetch', '-q', 'origin'], cwd=skia_dir)
        else:
            skia_dir = create_temp_skia_clone(config, depth)
            assert skia_dir
            use_temp = True

        if revision is None:
            message = subprocess.check_output(
                [git, 'log', '-n', '1', '--format=format:%B',
                 'origin/master'], cwd=skia_dir)
            svn_format = (
                'git-svn-id: http://skia.googlecode.com/svn/trunk@([0-9]+) ')
            search = re.search(svn_format, message)
            if not search:
                raise DepsRollError(
                    'Revision number missing from origin/master.')
            revision = int(search.group(1))
            git_hash = strip_output(
                [git, 'show-ref', 'origin/master', '--hash'], cwd=skia_dir)
        else:
            revision_regex = config.revision_format % revision
            git_hash = strip_output(
                [git, 'log', '--grep', revision_regex, '--format=format:%H',
                 'origin/master'], cwd=skia_dir)

        if revision < 0  or not git_hash:
            raise DepsRollError('Git hash can not be found.')
        return revision, git_hash
    finally:
        if use_temp:
            shutil.rmtree(skia_dir)


class GitBranchCLUpload(object):
    """Class to manage git branches and git-cl-upload.

    This class allows one to create a new branch in a repository based
    off of origin/master, make changes to the tree inside the
    with-block, upload that new branch to Rietveld, restore the original
    tree state, and delete the local copy of the new branch.

    See roll_deps() for an example of use.

    Constructor Args:
        config: (roll_deps.DepsRollConfig) object containing options.
        message: (string) the commit message, can be multiline.
        set_brach_name: (string or none) if not None, the name of the
            branch to use.  If None, then use a temporary branch that
            will be deleted.

    Attributes:
        issue: a string describing the codereview issue, after __exit__
            has been called, othrwise, None.

    Raises:
        OSError: failed to execute git or git-cl.
        subprocess.CalledProcessError: git returned unexpected status.
    """
    # pylint: disable=I0011,R0903,R0902

    def __init__(self, config, message, set_branch_name):
        self._message = message
        self._file_list = []
        self._branch_name = set_branch_name
        self._stash = None
        self._original_branch = None
        self._config = config
        self._svn_info = None
        self.issue = None

    def stage_for_commit(self, *paths):
        """Calls `git add ...` on each argument.

        Args:
            *paths: (list of strings) list of filenames to pass to `git add`.
        """
        self._file_list.extend(paths)

    def __enter__(self):
        git = self._config.git
        def branch_exists(branch):
            """Return true iff branch exists."""
            return 0 == subprocess.call(
                [git, 'show-ref', '--quiet', branch])
        def has_diff():
            """Return true iff repository has uncommited changes."""
            return bool(subprocess.call([git, 'diff', '--quiet', 'HEAD']))
        self._stash = has_diff()
        if self._stash:
            check_call([git, 'stash', 'save'])
        try:
            self._original_branch = strip_output(
                [git, 'symbolic-ref', '--short', 'HEAD'])
        except (subprocess.CalledProcessError,):
            self._original_branch = strip_output(
                [git, 'rev-parse', 'HEAD'])

        if not self._branch_name:
            self._branch_name = self._config.default_branch_name

        if branch_exists(self._branch_name):
            check_call([git, 'checkout', '-q', 'master'])
            check_call([git, 'branch', '-q', '-D', self._branch_name])

        check_call(
            [git, 'checkout', '-q', '-b',
             self._branch_name, 'origin/master'])

        svn_info = subprocess.check_output(['git', 'svn', 'info'])
        svn_info_search = re.search(r'Last Changed Rev: ([0-9]+)\W', svn_info)
        assert svn_info_search
        self._svn_info = svn_info_search.group(1)

    def __exit__(self, etype, value, traceback):
        # pylint: disable=I0011,R0912
        git = self._config.git
        def quiet_check_call(*args, **kwargs):
            """Call check_call, but pipe output to devnull."""
            with open(os.devnull, 'w') as devnull:
                check_call(*args, stdout=devnull, **kwargs)

        for filename in self._file_list:
            assert os.path.exists(filename)
            check_call([git, 'add', filename])
        check_call([git, 'commit', '-q', '-m', self._message])

        git_cl = [git, 'cl', 'upload', '-f', '--cc=skia-team@google.com',
                  '--bypass-hooks', '--bypass-watchlists']
        git_try = [git, 'cl', 'try', '--revision', self._svn_info]
        git_try.extend([arg for bot in self._config.cl_bot_list
                        for arg in ('-b', bot)])

        if self._config.skip_cl_upload:
            print ' '.join(git_cl)
            print
            if self._config.cl_bot_list:
                print ' '.join(git_try)
                print
            self.issue = ''
        else:
            if self._config.verbose:
                check_call(git_cl)
                print
            else:
                quiet_check_call(git_cl)
            self.issue = strip_output([git, 'cl', 'issue'])
            if self._config.cl_bot_list:
                if self._config.verbose:
                    check_call(git_try)
                    print
                else:
                    quiet_check_call(git_try)

        # deal with the aftermath of failed executions of this script.
        if self._config.default_branch_name == self._original_branch:
            self._original_branch = 'master'
        check_call([git, 'checkout', '-q', self._original_branch])

        if self._config.default_branch_name == self._branch_name:
            check_call([git, 'branch', '-q', '-D', self._branch_name])
        if self._stash:
            check_call([git, 'stash', 'pop'])


def change_skia_deps(revision, git_hash, depspath):
    """Update the DEPS file.

    Modify the skia_revision and skia_hash entries in the given DEPS file.

    Args:
        revision: (int) Skia SVN revision.
        git_hash: (string) Skia Git hash.
        depspath: (string) path to DEPS file.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False,
                                            prefix='skia_DEPS_ROLL_tmp_')
    try:
        deps_regex_rev = re.compile('"skia_revision": "[0-9]*",')
        deps_regex_hash = re.compile('"skia_hash": "[0-9a-f]*",')

        deps_regex_rev_repl = '"skia_revision": "%d",' % revision
        deps_regex_hash_repl = '"skia_hash": "%s",' % git_hash

        with open(depspath, 'r') as input_stream:
            for line in input_stream:
                line = deps_regex_rev.sub(deps_regex_rev_repl, line)
                line = deps_regex_hash.sub(deps_regex_hash_repl, line)
                temp_file.write(line)
    finally:
        temp_file.close()
    shutil.move(temp_file.name, depspath)


def branch_name(message):
    """Return the first line of a commit message to be used as a branch name.

    Args:
        message: (string)

    Returns:
        A string derived from message suitable for a branch name.
    """
    return message.lstrip().split('\n')[0].rstrip().replace(' ', '_')


def roll_deps(config, revision, git_hash):
    """Upload changed DEPS and a whitespace change.

    Given the correct git_hash, create two Reitveld issues.

    Args:
        config: (roll_deps.DepsRollConfig) object containing options.
        revision: (int) Skia SVN revision.
        git_hash: (string) Skia Git hash.

    Returns:
        a tuple containing textual description of the two issues.

    Raises:
        OSError: failed to execute git or git-cl.
        subprocess.CalledProcessError: git returned unexpected status.
    """
    git = config.git
    cwd = os.getcwd()
    os.chdir(config.chromium_path)
    try:
        check_call([git, 'fetch', '-q', 'origin'])
        master_hash = strip_output(
            [git, 'show-ref', 'origin/master', '--hash'])

        # master_hash[8] gives each whitespace CL a unique name.
        message = ('whitespace change %s\n\nThis CL was created by'
                   ' Skia\'s roll_deps.py script.\n') % master_hash[:8]
        branch = branch_name(message) if config.save_branches else None

        codereview = GitBranchCLUpload(config, message, branch)
        with codereview:
            with open('build/whitespace_file.txt', 'a') as output_stream:
                output_stream.write('\nCONTROL\n')
            codereview.stage_for_commit('build/whitespace_file.txt')
        whitespace_cl = codereview.issue
        if branch:
            whitespace_cl = '%s\n    branch: %s' % (whitespace_cl, branch)
        control_url_match = re.search('https?://[^) ]+', codereview.issue)
        if control_url_match:
            message = ('roll skia DEPS to %d\n\nThis CL was created by'
                       ' Skia\'s roll_deps.py script.\n\ncontrol: %s'
                       % (revision, control_url_match.group(0)))
        else:
            message = ('roll skia DEPS to %d\n\nThis CL was created by'
                       ' Skia\'s roll_deps.py script.') % revision
        branch = branch_name(message) if config.save_branches else None
        codereview = GitBranchCLUpload(config, message, branch)
        with codereview:
            change_skia_deps(revision, git_hash, 'DEPS')
            codereview.stage_for_commit('DEPS')
        deps_cl = codereview.issue
        if branch:
            deps_cl = '%s\n    branch: %s' % (deps_cl, branch)

        return deps_cl, whitespace_cl
    finally:
        os.chdir(cwd)


def find_hash_and_roll_deps(config, revision):
    """Call find_hash_from_revision() and roll_deps().

    The calls to git will be verbose on standard output.  After a
    successful upload of both issues, print links to the new
    codereview issues.

    Args:
        config: (roll_deps.DepsRollConfig) object containing options.
        revision: (int or None) the Skia SVN revision number or None
            to use the tip of the tree.

    Raises:
        roll_deps.DepsRollError: if the revision can't be found.
        OSError: failed to execute git or git-cl.
        subprocess.CalledProcessError: git returned unexpected status.
    """
    revision, git_hash = find_revision_and_hash(config, revision)

    print 'revision=%r\nhash=%r\n' % (revision, git_hash)

    deps_issue, whitespace_issue = roll_deps(config, revision, git_hash)

    print 'DEPS roll:\n    %s\n' % deps_issue
    print 'Whitespace change:\n    %s\n' % whitespace_issue


def main(args):
    """main function; see module-level docstring and GetOptionParser help.

    Args:
        args: sys.argv[1:]-type argument list.
    """
    option_parser = DepsRollConfig.GetOptionParser()
    options = option_parser.parse_args(args)[0]

    if not options.chromium_path:
        option_parser.error('Must specify chromium_path.')
    if not os.path.isdir(options.chromium_path):
        option_parser.error('chromium_path must be a directory.')
    if not test_git_executable(options.git_path):
        option_parser.error('Invalid git executable.')

    config = DepsRollConfig(options)
    find_hash_and_roll_deps(config, options.revision)


if __name__ == '__main__':
    main(sys.argv[1:])

