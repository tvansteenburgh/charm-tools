#!/usr/bin/python
#
#    pull-source - Fetch source for charm, layers, and interfaces
#
#    Copyright (C) 2016  Canonical Ltd.
#    Author: Tim Van Steenburgh <tvansteenburgh@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Downloads the source code for a charm, layer, or interface.

The "thing-to-download" can be specified using any of the following forms:

 - [cs:]charm
 - [cs:]series/charm
 - [cs:]~user/charm
 - [cs:]~user/series/charm
 - layer:layer-name
 - interface:interface-name

If a download directory is not specified, the following environment vars
will be used to determine the download location:

 - For charms, $JUJU_REPOSITORY
 - For layers, $LAYER_PATH
 - For interfaces, $INTERFACE_PATH

If a download location can not be determined from environment variables,
the current working directory will be used.

The download is aborted if the destination directory already exists.

"""

import argparse
import logging
import os
import sys
import textwrap

from .build import fetchers
from fetchers import (
    CharmstoreDownloader,
    FETCHERS,
    get,
)


log = logging.getLogger(__name__)

LAYER_PREFIX = 'layer:'
INTERFACE_PREFIX = 'interface:'
CHARM_PREFIX = 'cs:'

ERR_DIR_EXISTS = "Aborting, destination directory exists"


class CharmstoreRepoDownloader(CharmstoreDownloader):
    EXTRA_INFO_URL = CharmstoreDownloader.STORE_URL + '/meta/extra-info'

    def fetch(self, dir_):
        url = self.EXTRA_INFO_URL.format(self.entity)
        repo_url = get(url).json().get('bzr-url')
        if repo_url:
            try:
                fetcher = fetchers.get_fetcher(repo_url)
            except fetchers.FetchError:
                log.debug(
                    "No fetcher for %s, downloading from charmstore",
                    repo_url)
                return super(CharmstoreRepoDownloader, self).fetch(dir_)
            else:
                return fetcher.fetch(dir_)

        return super(CharmstoreRepoDownloader, self).fetch(dir_)

FETCHERS.insert(0, CharmstoreRepoDownloader)


def download_item(item, dir_):
    series_dir = None

    if item.startswith(LAYER_PREFIX):
        dir_ = dir_ or os.environ.get('LAYER_PATH')
    elif item.startswith(INTERFACE_PREFIX):
        dir_ = dir_ or os.environ.get('INTERFACE_PATH')
    else:
        dir_ = dir_ or os.environ.get('JUJU_REPOSITORY')
        if not item.startswith(CHARM_PREFIX):
            item = CHARM_PREFIX + item

        url_parts = item[len(CHARM_PREFIX):].split('/')
        charm_name = url_parts[-1]
        if len(url_parts) == 2 and not url_parts[0].startswith('~'):
            series_dir = url_parts[0]
        elif len(url_parts) == 3:
            series_dir = url_parts[1]

    dir_ = dir_ or os.getcwd()
    dir_ = os.path.abspath(os.path.expanduser(dir_))

    if series_dir:
        series_path = os.path.join(dir_, series_dir)
        if not os.path.exists(series_path):
            os.mkdir(series_path)
        dir_ = series_path

    try:
        fetcher = fetchers.get_fetcher(item)
        if isinstance(fetcher, fetchers.InterfaceFetcher):
            target = fetcher.target(dir_)
            if target.exists():
                return "{}: {}".format(ERR_DIR_EXISTS, target)
        else:
            final_dest_dir = os.path.join(dir_, charm_name)
            if os.path.exists(final_dest_dir):
                return "{}: {}".format(ERR_DIR_EXISTS, final_dest_dir)

        dest = fetcher.fetch(dir_)
    except fetchers.FetchError:
        return "Can't find source for {}".format(item)

    print('Downloaded {} to {}'.format(item, dest))


def setup_parser():
    parser = argparse.ArgumentParser(
        prog='charm pull-source',
        description=textwrap.dedent(__doc__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'item',
        help='Name of the charm, layer, or interface to download.'
    )
    parser.add_argument(
        'dir', nargs='?',
        help='Directory in which to place the downloaded source.',
    )
    parser.add_argument(
        '-v', '--verbose',
        help='Show verbose output',
        action='store_true', default=False,
    )

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            format='%(levelname)s %(filename)s: %(message)s',
            level=logging.DEBUG,
        )
    else:
        logging.basicConfig(
            format='%(levelname)s: %(message)s',
            level=logging.WARN,
        )

    return download_item(args.item, args.dir)


if __name__ == "__main__":
    sys.exit(main())