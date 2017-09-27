# Copyright 2017, Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from unittest.mock import call, Mock, mock_open, patch

import pytest

from tasks import _git, accounts, google_api_nodejs_client
from tests import common

_NPM_ACCOUNT = accounts.NpmAccount('auth_token')


@patch('tasks.google_api_nodejs_client._commit_message.date')
@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_update(clone_from_github_mock, check_output_mock, date_mock):
    repo_mock = Mock()
    repo_mock.diff_name_status.return_value = [
        ('apis/foo/v1.ts', _git.Status.ADDED),
        ('apis/bar/v1.ts', _git.Status.UPDATED),
        ('apis/baz/v1.ts', _git.Status.DELETED)
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    date_mock.today.return_value.isoformat.return_value = '2000-01-01'

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(repo_mock, 'repo')

    google_api_nodejs_client.update('/tmp', common.GITHUB_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.check_output(['npm', 'install'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['node', '--max_old_space_size=2000', '/usr/bin/npm',
                           'run', 'generate-apis'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.diff_name_status(staged=False),
        call.check_output(['node', '--max_old_space_size=2000', '/usr/bin/npm',
                           'run', 'build'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'test'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.add(['apis']),
        call.repo.commit(('Autogenerated update (2000-01-01)\n'
                          '\nAdd:\n- foo:v1\n'
                          '\nDelete:\n- baz:v1\n'
                          '\nUpdate:\n- bar:v1'),
                         'Alice',
                         'alice@test.com'),
        call.repo.push()
    ]


@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_update_no_changes(clone_from_github_mock, check_output_mock):
    repo_mock = Mock()
    repo_mock.diff_name_status.return_value = []
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(repo_mock, 'repo')

    google_api_nodejs_client.update('/tmp', common.GITHUB_ACCOUNT)
    npm_args = ['node', '--max_old_space_size=2000', '/usr/bin/npm']
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.check_output(['npm', 'install'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output([*npm_args, 'run', 'generate-apis'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.diff_name_status(staged=False)
    ]


@patch('tasks.google_api_nodejs_client.os.path.expanduser')
@patch('tasks.google_api_nodejs_client.date')
@patch('tasks.google_api_nodejs_client.open', new_callable=mock_open)
@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_major(clone_from_github_mock,
                       check_output_mock,
                       open_mock,
                       date_mock,
                       expanduser_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = ['alice@test.com', 'alice@test.com']
    repo_mock.diff_name_status.return_value = [
        ('apis/foo/v1.ts', _git.Status.ADDED),
        ('apis/bar/v1.ts', _git.Status.DELETED),
        ('apis/baz/v1.ts', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = '20.1.0'
    open_package_json_mock = mock_open(read_data=('{"version": "20.1.0"}'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_npmrc_mock = mock_open()
    open_index_md_mock = mock_open(
        read_data=('...\n\n'
                   '### ...\n\n'
                   '* [v20.1.0 (latest)](...)\n'
                   '...\n'))
    open_mock.side_effect = [
        open_package_json_mock.return_value,
        open_package_json_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_npmrc_mock.return_value,
        open_index_md_mock.return_value,
        open_index_md_mock.return_value
    ]
    date_mock.today.return_value.strftime.return_value = '1 September 2017'
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(open_mock, 'open')
    manager.attach_mock(repo_mock, 'repo')
    manager.attach_mock(open_package_json_mock, 'open_package_json')
    manager.attach_mock(open_changelog_md_mock, 'open_changelog_md')
    manager.attach_mock(open_npmrc_mock, 'open_npmrc')
    manager.attach_mock(open_index_md_mock, 'open_index_md')

    google_api_nodejs_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('20.1.0'),
        call.check_output(['npm', 'view', 'googleapis', 'version']),
        call.repo.diff_name_status(rev='20.1.0'),
        call.open('/tmp/google-api-nodejs-client/package.json'),
        call.open_package_json().__enter__(),
        call.open_package_json().read(),
        call.open_package_json().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/package.json', 'w'),
        call.open_package_json().__enter__(),
        call.open_package_json().write('{\n  "version": "21.0.0"\n}'),
        call.open_package_json().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/CHANGELOG.md'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().read(),
        call.open_changelog_md().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/CHANGELOG.md', 'w'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().write(('##### 21.0.0 - 1 September 2017\n\n'
                                        '###### Breaking changes\n'
                                        '- Deleted `bar`\n\n'
                                        '###### Backwards compatible changes\n'
                                        '- Added `foo`\n'
                                        '- Updated `baz`\n\n'
                                        '...\n')),
        call.open_changelog_md().__exit__(None, None, None),
        call.check_output(['npm', 'install'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['node', '--max_old_space_size=2000', '/usr/bin/npm',
                           'run', 'build'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'test'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.commit('21.0.0', 'Alice', 'alice@test.com'),
        call.repo.tag('21.0.0'),
        call.repo.push(),
        call.repo.push(tags=True),
        call.open('/home/test/.npmrc', 'w'),
        call.open_npmrc().__enter__(),
        call.open_npmrc().write(
            '//registry.npmjs.org/:_authToken=auth_token\n'),
        call.open_npmrc().__exit__(None, None, None),
        call.check_output(['npm', 'publish'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'doc'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.checkout('gh-pages'),
        call.check_output(['rm', '-rf', 'latest'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['cp', '-r', 'doc/googleapis/21.0.0'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['cp', '-r', 'doc/googleapis/21.0.0', '21.0.0'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.open('/tmp/google-api-nodejs-client/index.md'),
        call.open_index_md().__enter__(),
        call.open_index_md().readlines(),
        call.open_index_md().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/index.md', 'w'),
        call.open_index_md().__enter__(),
        call.open_index_md().write(
            ('...\n\n'
             '### ...\n\n'
             '* [v21.0.0 (latest)]'
             '(http://google.github.io/google-api-nodejs-client/21.0.0/'
             'index.html)\n'
             '* [v20.1.0](...)\n'
             '...\n')),
        call.open_index_md().__exit__(None, None, None),
        call.repo.add(['latest', '21.0.0']),
        call.repo.commit('21.0.0', 'Alice', 'alice@test.com'),
        call.repo.push(branch='gh-pages'),
        call.repo.checkout('master')
    ]


@patch('tasks.google_api_nodejs_client.os.path.expanduser')
@patch('tasks.google_api_nodejs_client.date')
@patch('tasks.google_api_nodejs_client.open', new_callable=mock_open)
@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_minor(clone_from_github_mock,
                       check_output_mock,
                       open_mock,
                       date_mock,
                       expanduser_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = ['alice@test.com', 'alice@test.com']
    repo_mock.diff_name_status.return_value = [
        ('apis/foo/v1.ts', _git.Status.ADDED),
        ('apis/baz/v1.ts', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = '20.1.0'
    open_package_json_mock = mock_open(read_data=('{"version": "20.1.0"}'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_npmrc_mock = mock_open()
    open_index_md_mock = mock_open(
        read_data=('...\n\n'
                   '### ...\n\n'
                   '* [v20.1.0 (latest)](...)\n'
                   '...\n'))
    open_mock.side_effect = [
        open_package_json_mock.return_value,
        open_package_json_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_npmrc_mock.return_value,
        open_index_md_mock.return_value,
        open_index_md_mock.return_value
    ]
    date_mock.today.return_value.strftime.return_value = '1 September 2017'
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(open_mock, 'open')
    manager.attach_mock(repo_mock, 'repo')
    manager.attach_mock(open_package_json_mock, 'open_package_json')
    manager.attach_mock(open_changelog_md_mock, 'open_changelog_md')
    manager.attach_mock(open_npmrc_mock, 'open_npmrc')
    manager.attach_mock(open_index_md_mock, 'open_index_md')

    google_api_nodejs_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('20.1.0'),
        call.check_output(['npm', 'view', 'googleapis', 'version']),
        call.repo.diff_name_status(rev='20.1.0'),
        call.open('/tmp/google-api-nodejs-client/package.json'),
        call.open_package_json().__enter__(),
        call.open_package_json().read(),
        call.open_package_json().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/package.json', 'w'),
        call.open_package_json().__enter__(),
        call.open_package_json().write('{\n  "version": "20.2.0"\n}'),
        call.open_package_json().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/CHANGELOG.md'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().read(),
        call.open_changelog_md().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/CHANGELOG.md', 'w'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().write(('##### 20.2.0 - 1 September 2017\n\n'
                                        '###### Backwards compatible changes\n'
                                        '- Added `foo`\n'
                                        '- Updated `baz`\n\n'
                                        '...\n')),
        call.open_changelog_md().__exit__(None, None, None),
        call.check_output(['npm', 'install'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['node', '--max_old_space_size=2000', '/usr/bin/npm',
                           'run', 'build'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'test'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.commit('20.2.0', 'Alice', 'alice@test.com'),
        call.repo.tag('20.2.0'),
        call.repo.push(),
        call.repo.push(tags=True),
        call.open('/home/test/.npmrc', 'w'),
        call.open_npmrc().__enter__(),
        call.open_npmrc().write(
            '//registry.npmjs.org/:_authToken=auth_token\n'),
        call.open_npmrc().__exit__(None, None, None),
        call.check_output(['npm', 'publish'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'doc'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.checkout('gh-pages'),
        call.check_output(['rm', '-rf', 'latest'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['cp', '-r', 'doc/googleapis/20.2.0'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['cp', '-r', 'doc/googleapis/20.2.0', '20.2.0'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.open('/tmp/google-api-nodejs-client/index.md'),
        call.open_index_md().__enter__(),
        call.open_index_md().readlines(),
        call.open_index_md().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/index.md', 'w'),
        call.open_index_md().__enter__(),
        call.open_index_md().write(
            ('...\n\n'
             '### ...\n\n'
             '* [v20.2.0 (latest)]'
             '(http://google.github.io/google-api-nodejs-client/20.2.0/'
             'index.html)\n'
             '* [v20.1.0](...)\n'
             '...\n')),
        call.open_index_md().__exit__(None, None, None),
        call.repo.add(['latest', '20.2.0']),
        call.repo.commit('20.2.0', 'Alice', 'alice@test.com'),
        call.repo.push(branch='gh-pages'),
        call.repo.checkout('master')
    ]


@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_no_commits_since_latest_tag(clone_from_github_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = []
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(repo_mock, 'repo')

    google_api_nodejs_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('20.1.0')
    ]


@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_different_authors_since_latest_tag(clone_from_github_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = ['alice@test.com', 'bob@test.com']
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(repo_mock, 'repo')

    google_api_nodejs_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('20.1.0')
    ]


@patch('tasks.google_api_nodejs_client.os.path.expanduser')
@patch('tasks.google_api_nodejs_client.date')
@patch('tasks.google_api_nodejs_client.open', new_callable=mock_open)
@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_force(clone_from_github_mock,
                       check_output_mock,
                       open_mock,
                       date_mock,
                       expanduser_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = ['alice@test.com', 'bob@test.com']
    repo_mock.diff_name_status.return_value = [
        ('apis/foo/v1.ts', _git.Status.ADDED),
        ('apis/baz/v1.ts', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = '20.1.0'
    open_package_json_mock = mock_open(read_data=('{"version": "20.1.0"}'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_npmrc_mock = mock_open()
    open_index_md_mock = mock_open(
        read_data=('...\n\n'
                   '### ...\n\n'
                   '* [v20.1.0 (latest)](...)\n'
                   '...\n'))
    open_mock.side_effect = [
        open_package_json_mock.return_value,
        open_package_json_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_npmrc_mock.return_value,
        open_index_md_mock.return_value,
        open_index_md_mock.return_value
    ]
    date_mock.today.return_value.strftime.return_value = '1 September 2017'
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    google_api_nodejs_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT, force=True)
    # We don't bother verifying all calls in this case, since we only want to
    # verify that the different authors check was passed.
    assert repo_mock.mock_calls == [
        call.latest_tag(),
        call.authors_since('20.1.0'),
        call.diff_name_status(rev='20.1.0'),
        call.commit('20.2.0', 'Alice', 'alice@test.com'),
        call.tag('20.2.0'),
        call.push(),
        call.push(tags=True),
        call.checkout('gh-pages'),
        call.add(['latest', '20.2.0']),
        call.commit('20.2.0', 'Alice', 'alice@test.com'),
        call.push(branch='gh-pages'),
        call.checkout('master')
    ]


@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_latest_version_mismatch(clone_from_github_mock,
                                         check_output_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = ['alice@test.com']
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = '20.0.0'

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(repo_mock, 'repo')

    with pytest.raises(Exception) as excinfo:
        google_api_nodejs_client.release(
            '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT)
    assert str(excinfo.value) == (
        'latest tag does not match the latest package version on npm:'
        ' 20.1.0 != 20.0.0')
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('20.1.0'),
        call.check_output(['npm', 'view', 'googleapis', 'version'])
    ]


@patch('tasks.google_api_nodejs_client.os.path.expanduser')
@patch('tasks.google_api_nodejs_client.date')
@patch('tasks.google_api_nodejs_client.open', new_callable=mock_open)
@patch('tasks.google_api_nodejs_client.check_output')
@patch('tasks.google_api_nodejs_client._git.clone_from_github')
def test_release_invalid_index_md(clone_from_github_mock,
                                  check_output_mock,
                                  open_mock,
                                  date_mock,
                                  expanduser_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '20.1.0'
    repo_mock.authors_since.return_value = ['alice@test.com', 'alice@test.com']
    repo_mock.diff_name_status.return_value = [
        ('apis/foo/v1.ts', _git.Status.ADDED),
        ('apis/baz/v1.ts', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = '20.1.0'
    open_package_json_mock = mock_open(read_data=('{"version": "20.1.0"}'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_npmrc_mock = mock_open()
    open_index_md_mock = mock_open(read_data=('...\n'))
    open_mock.side_effect = [
        open_package_json_mock.return_value,
        open_package_json_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_npmrc_mock.return_value,
        open_index_md_mock.return_value,
    ]
    date_mock.today.return_value.strftime.return_value = '1 September 2017'
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(open_mock, 'open')
    manager.attach_mock(repo_mock, 'repo')
    manager.attach_mock(open_package_json_mock, 'open_package_json')
    manager.attach_mock(open_changelog_md_mock, 'open_changelog_md')
    manager.attach_mock(open_npmrc_mock, 'open_npmrc')
    manager.attach_mock(open_index_md_mock, 'open_index_md')

    with pytest.raises(Exception) as excinfo:
        google_api_nodejs_client.release(
            '/tmp', common.GITHUB_ACCOUNT, _NPM_ACCOUNT)
    assert str(excinfo.value) == 'index.md has an unexpected format'
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-nodejs-client',
                               '/tmp/google-api-nodejs-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('20.1.0'),
        call.check_output(['npm', 'view', 'googleapis', 'version']),
        call.repo.diff_name_status(rev='20.1.0'),
        call.open('/tmp/google-api-nodejs-client/package.json'),
        call.open_package_json().__enter__(),
        call.open_package_json().read(),
        call.open_package_json().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/package.json', 'w'),
        call.open_package_json().__enter__(),
        call.open_package_json().write('{\n  "version": "20.2.0"\n}'),
        call.open_package_json().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/CHANGELOG.md'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().read(),
        call.open_changelog_md().__exit__(None, None, None),
        call.open('/tmp/google-api-nodejs-client/CHANGELOG.md', 'w'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().write(('##### 20.2.0 - 1 September 2017\n\n'
                                        '###### Backwards compatible changes\n'
                                        '- Added `foo`\n'
                                        '- Updated `baz`\n\n'
                                        '...\n')),
        call.open_changelog_md().__exit__(None, None, None),
        call.check_output(['npm', 'install'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['node', '--max_old_space_size=2000', '/usr/bin/npm',
                           'run', 'build'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'test'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.commit('20.2.0', 'Alice', 'alice@test.com'),
        call.repo.tag('20.2.0'),
        call.repo.push(),
        call.repo.push(tags=True),
        call.open('/home/test/.npmrc', 'w'),
        call.open_npmrc().__enter__(),
        call.open_npmrc().write(
            '//registry.npmjs.org/:_authToken=auth_token\n'),
        call.open_npmrc().__exit__(None, None, None),
        call.check_output(['npm', 'publish'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['npm', 'run', 'doc'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.repo.checkout('gh-pages'),
        call.check_output(['rm', '-rf', 'latest'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['cp', '-r', 'doc/googleapis/20.2.0'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.check_output(['cp', '-r', 'doc/googleapis/20.2.0', '20.2.0'],
                          cwd='/tmp/google-api-nodejs-client'),
        call.open('/tmp/google-api-nodejs-client/index.md'),
        call.open_index_md().__enter__(),
        call.open_index_md().readlines(),
        call.open_index_md().__exit__(None, None, None),
    ]
