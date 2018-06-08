#!/usr/bin/python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import requests
import json
import hashlib
import sys
import os
from optparse import OptionParser
import wget
import time

__version__ = '1.0.0'
__title__ = 'zenodo_get'
__summary__ = 'Zenodo record downloader.'
__uri__ = 'https://gitlab.com/dvolgyes/zenodo_get'
__license__ = 'AGPL v3'
__author__ = 'David Völgyes'
__email__ = 'david.volgyes@ieee.org'
__doi__ = '10.5281/zenodo.1261812'
__description__ = """
This program is meant to download complete Zenodo records based
on the Zenodo record ID or the DOI. The primary goal is to easy access
to large records with dozens of files.
"""
__bibtex__ = """@misc{david_volgyes_2018_1261812,
  author  = {David Völgyes},
  title   = {Zenodo_get: a downloader for Zenodo records.},
  month   = june,
  year    = 2018,
  doi     = {%s},
  url     = {https://doi.org/%s}
}""" % (__doi__, __doi__)
__reference__ = """David Völgyes. (2018, June 4). \
Zenodo_get: a downloader for Zenodo records (Version %s).
Zenodo. https://doi.org/%s""" % (__version__, __doi__)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def check_hash(filename, checksum):
    algorithm, value = checksum.split(':')
    if not os.path.exists(filename):
        return value, 'invalid'
    h = hashlib.new(algorithm)
    with open(filename, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            h.update(data)
    digest = h.hexdigest()
    return value, digest


if __name__ == '__main__':

    parser = OptionParser(
             usage='%prog [options] RECORD_OR_DOI',
             version='%prog {}'.format(__version__)
             )

    parser.add_option('-c', '--cite',
                      dest='cite',
                      action='store_true',
                      default=False,
                      help='print citation information')

    parser.add_option('-r', '--record',
                      action='store',
                      type='string',
                      dest='record',
                      help='Zenodo record ID',
                      default=None)

    parser.add_option('-d', '--doi',
                      action='store',
                      type='string',
                      dest='doi',
                      help='Zenodo DOI',
                      default=None)

    parser.add_option('-m', '--md5',
                      action='store_true',
                      # ~type=bool,
                      dest='md5',
                      help='Create md5sums.txt for verification.',
                      default=False)

    parser.add_option('-w', '--wget',
                      action='store',
                      type='string',
                      dest='wget',
                      help='Create URL list for download managers. '
                      '(Files will not be downloaded.)',
                      default=None)

    parser.add_option('-e', '--continue-on-error',
                      action='store_true',
                      dest='error',
                      help='Continue with next file if error happens.',
                      default=False)

    parser.add_option('-k', '--keep',
                      action='store_true',
                      dest='keep',
                      help='Keep files with invalid checksum.'
                      ' (Default: delete them.)',
                      default=False)

    parser.add_option('-n', '--do-not-continue',
                      action='store_false',
                      dest='cont',
                      help='Do not continue previous download attempt.'
                      ' (Default: continue.)',
                      default=True)

    parser.add_option('-R', '--retry',
                      action='store',
                      type=int,
                      dest='retry',
                      help='Retry on error N more times.',
                      default=0)

    parser.add_option('-p', '--pause',
                      action='store',
                      type=float,
                      dest='pause',
                      help='Wait N second before retry attempt, e.g. 0.5',
                      default=0.5)

    (options, args) = parser.parse_args()

    if options.cite:
        print('Reference for this software:')
        print(__reference__)
        print()
        print('Bibtex format:')
        print(__bibtex__)
        sys.exit(0)

    if len(args) > 0:
        try:
            t = int(args[0])
            options.record = args[0]
        except ValueError:
            options.doi = args[0]
    elif options.doi is None and options.record is None:
        parser.print_help()
        sys.exit(0)

    if options.doi is not None:
        url = options.doi
        if not url.startswith('http'):
            url = 'https://doi.org/'+url
        try:
            r = requests.get(url)
        except:
            eprint('Connection error. Please, check the DOI/ID, and try again later.')
            sys.exit(1)
        if not r.ok:
            eprint('DOI could not be resolved. Try again, or use record ID.')
            sys.exit(1)
        recordID = r.url.split('/')[-1]
    else:
        recordID = options.record
    recordID = recordID.strip()

    url = 'https://zenodo.org/api/records/'
    r = requests.get(url+recordID)
    if r.ok:
        js = json.loads(r.text)
        files = js['files']
        total_size = sum(f['size'] for f in files)

        if options.md5 is not None:
            with open('md5sums.txt', 'wt') as md5file:
                for f in files:
                    fname = f['key']
                    checksum = f['checksum'].split(':')[-1]
                    md5file.write('{}  {}\n'.format(checksum, fname))

        if options.wget is not None:
            if options.wget == '-':
                for f in files:
                    link = f['links']['self']
                    print(link)
            else:
                with open(options.wget, 'wt') as wgetfile:
                    for f in files:
                        link = f['links']['self']
                        wgetfile.write('{}\n'.format(link,))
        else:
            eprint('Total size: {:.1f} MB'.format(total_size/2**20,))
            for f in files:
                link = f['links']['self']
                size = f['size']/2**20
                eprint()
                eprint('Link: {}   size: {:.1f} MB'.format(link, size))
                fname = f['key']
                checksum = f['checksum']

                remote_hash, local_hash = check_hash(fname, checksum)

                if remote_hash == local_hash and options.cont:
                    eprint('{} is already downloaded correctly.'.format(fname))
                    continue

                for _ in range(options.retry+1):
                    try:
                        filename = wget.download(link)
                    except Exception:
                        eprint('  Download error.')
                        time.sleep(options.pause)
                    else:
                        break
                else:
                    if not options.error:
                        eprint('  Too many errors, download is aborted.')
                        sys.exit(0)
                    eprint('  Too many errors,'
                           ' download continues with the next file.')
                    continue

                eprint()
                h1, h2 = check_hash(filename, checksum)
                if h1 == h2:
                    eprint('Checksum is correct. ({})'.format(h1,))
                else:
                    eprint('Checksum is INCORRECT!({} got:{})'.format(h1, h2))
                    if not options.keep:
                        eprint('  File is deleted.')
                        os.remove(filename)
                    else:
                        eprint('  File is NOT deleted!')
                    if not options.error:
                        sys.exit(1)
            eprint('All files have been downloaded.')
    else:
        eprint('Record could not get accessed.')
        sys.exit(1)
