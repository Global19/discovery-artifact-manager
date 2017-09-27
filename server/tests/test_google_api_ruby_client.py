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

from tasks import _git, accounts, google_api_ruby_client
from tests import common

_RUBYGEMS_ACCOUNT = accounts.RubyGemsAccount('api_key')


@patch('tasks.google_api_ruby_client._commit_message.date')
@patch('tasks.google_api_ruby_client.check_output')
@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_update(clone_from_github_mock, check_output_mock, date_mock):
    repo_mock = Mock()
    repo_mock.diff_name_status.return_value = [
        ('generated/google/apis/foo_v1.rb', _git.Status.ADDED),
        ('generated/google/apis/bar_v1.rb', _git.Status.UPDATED),
        ('generated/google/apis/baz_v1.rb', _git.Status.DELETED)
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    date_mock.today.return_value.isoformat.return_value = '2000-01-01'

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(repo_mock, 'repo')

    google_api_ruby_client.update('/tmp', common.GITHUB_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.check_output(['bundle', 'install', '--path', 'vendor/bundle'],
                          cwd='/tmp/google-api-ruby-client'),
        call.check_output(['rm', '-rf', 'generated'],
                          cwd='/tmp/google-api-ruby-client'),
        call.check_output(['./script/generate'],
                          cwd='/tmp/google-api-ruby-client'),
        call.repo.diff_name_status(staged=False),
        call.check_output(['bundle', 'exec', 'rake', 'spec'],
                          cwd='/tmp/google-api-ruby-client'),
        call.repo.add(['api_names_out.yaml', 'generated']),
        call.repo.commit(('Autogenerated update (2000-01-01)\n'
                          '\nAdd:\n- foo_v1\n'
                          '\nDelete:\n- baz_v1\n'
                          '\nUpdate:\n- bar_v1'),
                         'Alice',
                         'alice@test.com'),
        call.repo.push()
    ]


@patch('tasks.google_api_ruby_client.check_output')
@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_update_no_changes(clone_from_github_mock, check_output_mock):
    repo_mock = Mock()
    repo_mock.diff_name_status.return_value = []
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(repo_mock, 'repo')

    google_api_ruby_client.update('/tmp', common.GITHUB_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.check_output(['bundle', 'install', '--path', 'vendor/bundle'],
                          cwd='/tmp/google-api-ruby-client'),
        call.check_output(['rm', '-rf', 'generated'],
                          cwd='/tmp/google-api-ruby-client'),
        call.check_output(['./script/generate'],
                          cwd='/tmp/google-api-ruby-client'),
        call.repo.diff_name_status(staged=False)
    ]


@patch('tasks.google_api_ruby_client.os.chmod')
@patch('tasks.google_api_ruby_client.os.path.expanduser')
@patch('tasks.google_api_ruby_client.open', new_callable=mock_open)
@patch('tasks.google_api_ruby_client.check_output')
@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_release_minor(clone_from_github_mock,
                       check_output_mock,
                       open_mock,
                       expanduser_mock,
                       chmod_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '0.13.6'
    repo_mock.authors_since.return_value = ['alice@test.com', 'alice@test.com']
    repo_mock.diff_name_status.return_value = [
        ('generated/google/apis/foo_v1.rb', _git.Status.ADDED),
        ('generated/google/apis/bar_v1.rb', _git.Status.DELETED),
        ('generated/google/apis/baz_v1.rb', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = 'google-api-client (0.13.6)'
    open_version_rb_mock = mock_open(
        read_data=('...\n'
                   'module Google\n'
                   '    module Apis\n'
                   '        # Client library version\n'
                   '        VERSION = \'0.13.6\'\n'
                   '    ...\n'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_credentials_mock = mock_open()
    open_mock.side_effect = [
        open_version_rb_mock.return_value,
        open_version_rb_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_credentials_mock.return_value
    ]
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(open_mock, 'open')
    manager.attach_mock(repo_mock, 'repo')
    manager.attach_mock(chmod_mock, 'chmod')
    manager.attach_mock(open_version_rb_mock, 'open_version_rb')
    manager.attach_mock(open_changelog_md_mock, 'open_changelog_md')
    manager.attach_mock(open_credentials_mock, 'open_credentials')

    google_api_ruby_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _RUBYGEMS_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('0.13.6'),
        call.check_output(['gem', 'search', '-e', '-r', 'google-api-client']),
        call.repo.diff_name_status(rev='0.13.6'),
        call.open('/tmp/google-api-ruby-client/lib/google/apis/version.rb'),
        call.open_version_rb().__enter__(),
        call.open_version_rb().read(),
        call.open_version_rb().__exit__(None, None, None),
        call.open('/tmp/google-api-ruby-client/lib/google/apis/version.rb'),
        call.open_version_rb().__enter__(),
        call.open_version_rb().write(('...\n'
                                      'module Google\n'
                                      '    module Apis\n'
                                      '        # Client library version\n'
                                      '        VERSION = \'0.14.0\'\n'
                                      '    ...\n')),
        call.open_version_rb().__exit__(None, None, None),
        call.open('/tmp/google-api-ruby-client/CHANGELOG.md'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().read(),
        call.open_changelog_md().__exit__(None, None, None),
        call.open('/tmp/google-api-ruby-client/CHANGELOG.md', 'w'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().write(('# 0.14.0\n'
                                        '* Breaking changes:\n'
                                        '  * Deleted `bar_v1`\n'
                                        '* Backwards compatible changes:\n'
                                        '  * Added `foo_v1`\n'
                                        '  * Updated `baz_v1`\n\n'
                                        '...\n')),
        call.open_changelog_md().__exit__(None, None, None),
        call.check_output(['bundle', 'install', '--path', 'vendor/bundle'],
                          cwd='/tmp/google-api-ruby-client'),
        call.check_output(['bundle', 'exec', 'rake', 'spec'],
                          cwd='/tmp/google-api-ruby-client'),
        call.repo.commit('0.14.0', 'Alice', 'alice@test.com'),
        call.repo.tag('0.14.0'),
        call.repo.push(),
        call.repo.push(tags=True),
        call.check_output(['./script/package'],
                          cwd='/tmp/google-api-ruby-client'),
        call.open('/home/test/.gem/credentials', 'w'),
        call.open_credentials().__enter__(),
        call.open_credentials().write('---\n:rubygems_api_key: api_key\n'),
        call.open_credentials().__exit__(None, None, None),
        call.chmod('/home/test/.gem/credentials', 0o600),
        call.check_output(['gem', 'push', 'pkg/google-api-client-0.14.0.gem'],
                          cwd='/tmp/google-api-ruby-client')
    ]


@patch('tasks.google_api_ruby_client.os.chmod')
@patch('tasks.google_api_ruby_client.os.path.expanduser')
@patch('tasks.google_api_ruby_client.open', new_callable=mock_open)
@patch('tasks.google_api_ruby_client.check_output')
@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_release_patch(clone_from_github_mock,
                       check_output_mock,
                       open_mock,
                       expanduser_mock,
                       chmod_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '0.13.6'
    repo_mock.authors_since.return_value = ['alice@test.com', 'alice@test.com']
    repo_mock.diff_name_status.return_value = [
        ('generated/google/apis/foo_v1.rb', _git.Status.ADDED),
        ('generated/google/apis/baz_v1.rb', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = 'google-api-client (0.13.6)'
    open_version_rb_mock = mock_open(
        read_data=('...\n'
                   'module Google\n'
                   '    module Apis\n'
                   '        # Client library version\n'
                   '        VERSION = \'0.13.6\'\n'
                   '    ...\n'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_credentials_mock = mock_open()
    open_mock.side_effect = [
        open_version_rb_mock.return_value,
        open_version_rb_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_credentials_mock.return_value
    ]
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(open_mock, 'open')
    manager.attach_mock(repo_mock, 'repo')
    manager.attach_mock(chmod_mock, 'chmod')
    manager.attach_mock(open_version_rb_mock, 'open_version_rb')
    manager.attach_mock(open_changelog_md_mock, 'open_changelog_md')
    manager.attach_mock(open_credentials_mock, 'open_credentials')

    google_api_ruby_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _RUBYGEMS_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('0.13.6'),
        call.check_output(['gem', 'search', '-e', '-r', 'google-api-client']),
        call.repo.diff_name_status(rev='0.13.6'),
        call.open('/tmp/google-api-ruby-client/lib/google/apis/version.rb'),
        call.open_version_rb().__enter__(),
        call.open_version_rb().read(),
        call.open_version_rb().__exit__(None, None, None),
        call.open('/tmp/google-api-ruby-client/lib/google/apis/version.rb'),
        call.open_version_rb().__enter__(),
        call.open_version_rb().write(('...\n'
                                      'module Google\n'
                                      '    module Apis\n'
                                      '        # Client library version\n'
                                      '        VERSION = \'0.13.7\'\n'
                                      '    ...\n')),
        call.open_version_rb().__exit__(None, None, None),
        call.open('/tmp/google-api-ruby-client/CHANGELOG.md'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().read(),
        call.open_changelog_md().__exit__(None, None, None),
        call.open('/tmp/google-api-ruby-client/CHANGELOG.md', 'w'),
        call.open_changelog_md().__enter__(),
        call.open_changelog_md().write(('# 0.13.7\n'
                                        '* Backwards compatible changes:\n'
                                        '  * Added `foo_v1`\n'
                                        '  * Updated `baz_v1`\n\n'
                                        '...\n')),
        call.open_changelog_md().__exit__(None, None, None),
        call.check_output(['bundle', 'install', '--path', 'vendor/bundle'],
                          cwd='/tmp/google-api-ruby-client'),
        call.check_output(['bundle', 'exec', 'rake', 'spec'],
                          cwd='/tmp/google-api-ruby-client'),
        call.repo.commit('0.13.7', 'Alice', 'alice@test.com'),
        call.repo.tag('0.13.7'),
        call.repo.push(),
        call.repo.push(tags=True),
        call.check_output(['./script/package'],
                          cwd='/tmp/google-api-ruby-client'),
        call.open('/home/test/.gem/credentials', 'w'),
        call.open_credentials().__enter__(),
        call.open_credentials().write('---\n:rubygems_api_key: api_key\n'),
        call.open_credentials().__exit__(None, None, None),
        call.chmod('/home/test/.gem/credentials', 0o600),
        call.check_output(['gem', 'push', 'pkg/google-api-client-0.13.7.gem'],
                          cwd='/tmp/google-api-ruby-client')
    ]


@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_release_no_commits_since_latest_tag(clone_from_github_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '1.0.0'
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(repo_mock, 'repo')

    with pytest.raises(Exception) as excinfo:
        google_api_ruby_client.release(
            '/tmp', common.GITHUB_ACCOUNT, _RUBYGEMS_ACCOUNT)
    assert str(excinfo.value) == ('latest tag does not match the pattern'
                                  r' "^0\.([0-9]+)\.([0-9]+)$": 1.0.0')
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
    ]


@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_release_different_authors_since_latest_tag(clone_from_github_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '0.13.6'
    repo_mock.authors_since.return_value = ['alice@test.com', 'bob@test.com']
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(repo_mock, 'repo')

    google_api_ruby_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _RUBYGEMS_ACCOUNT)
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('0.13.6')
    ]


@patch('tasks.google_api_ruby_client.os.chmod')
@patch('tasks.google_api_ruby_client.os.path.expanduser')
@patch('tasks.google_api_ruby_client.open', new_callable=mock_open)
@patch('tasks.google_api_ruby_client.check_output')
@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_release_force(clone_from_github_mock,
                       check_output_mock,
                       open_mock,
                       expanduser_mock,
                       chmod_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '0.13.6'
    repo_mock.authors_since.return_value = ['alice@test.com', 'alice@test.com']
    repo_mock.diff_name_status.return_value = [
        ('generated/google/apis/foo_v1.rb', _git.Status.ADDED),
        ('generated/google/apis/baz_v1.rb', _git.Status.UPDATED),
    ]
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = 'google-api-client (0.13.6)'
    open_version_rb_mock = mock_open(
        read_data=('...\n'
                   'module Google\n'
                   '    module Apis\n'
                   '        # Client library version\n'
                   '        VERSION = \'0.13.6\'\n'
                   '    ...\n'))
    open_changelog_md_mock = mock_open(read_data='...\n')
    open_credentials_mock = mock_open()
    open_mock.side_effect = [
        open_version_rb_mock.return_value,
        open_version_rb_mock.return_value,
        open_changelog_md_mock.return_value,
        open_changelog_md_mock.return_value,
        open_credentials_mock.return_value
    ]
    expanduser_mock.side_effect = lambda x: '/home/test' + x[1:]

    google_api_ruby_client.release(
        '/tmp', common.GITHUB_ACCOUNT, _RUBYGEMS_ACCOUNT, force=True)
    # We don't bother verifying all calls in this case, since we only want to
    # verify that the different authors check was passed.
    assert repo_mock.mock_calls == [
        call.latest_tag(),
        call.authors_since('0.13.6'),
        call.diff_name_status(rev='0.13.6'),
        call.commit('0.13.7', 'Alice', 'alice@test.com'),
        call.tag('0.13.7'),
        call.push(),
        call.push(tags=True),
    ]


@patch('tasks.google_api_ruby_client.check_output')
@patch('tasks.google_api_ruby_client._git.clone_from_github')
def test_release_latest_version_mismatch(clone_from_github_mock,
                                         check_output_mock):
    repo_mock = Mock()
    repo_mock.latest_tag.return_value = '0.13.6'
    repo_mock.authors_since.return_value = ['alice@test.com']
    side_effect = common.clone_from_github_mock_side_effect(repo_mock)
    clone_from_github_mock.side_effect = side_effect
    check_output_mock.return_value = 'google-api-client (1.0.0)'

    manager = Mock()
    manager.attach_mock(clone_from_github_mock, 'clone_from_github')
    manager.attach_mock(check_output_mock, 'check_output')
    manager.attach_mock(repo_mock, 'repo')

    with pytest.raises(Exception) as excinfo:
        google_api_ruby_client.release(
            '/tmp', common.GITHUB_ACCOUNT, _RUBYGEMS_ACCOUNT)
    assert str(excinfo.value) == (
        'latest tag does not match the latest package version on'
        ' RubyGems: 0.13.6 != 1.0.0')
    assert manager.mock_calls == [
        call.clone_from_github('google/google-api-ruby-client',
                               '/tmp/google-api-ruby-client',
                               github_account=common.GITHUB_ACCOUNT),
        call.repo.latest_tag(),
        call.repo.authors_since('0.13.6'),
        call.check_output(['gem', 'search', '-e', '-r', 'google-api-client']),
    ]
