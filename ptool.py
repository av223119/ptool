#!/usr/bin/env python3

import argparse
import os
import pyexiv2
import subprocess
import sys
from collections import Counter

def upto60(x):
    return x if len(x)<60 else '…%s' % x[-59:]

class Photo:
    def __init__(self, path: str):
        self.r = pyexiv2.ImageMetadata(path)
        self.r.read()

    def get(self, key: str, default=None):
        return self.r[key].value if key in self.r else default


class BasicProcessor:
    sieve = lambda _, x: x.endswith('.jpg')

    def __init__(self, root: str):
        for path, dirs, files in os.walk(root):
            for f in files:
                ff = os.path.join(path, f)
                if self.sieve(ff):
                    self.process(ff)


class Cams(BasicProcessor):
    """ Collects camera maker / model stats """
    stat = {}

    def process(self, f):
        p = Photo(f)
        maker = p.get('Exif.Image.Make', '<UNDEF>').strip()
        model = p.get('Exif.Image.Model', '<UNDEF>').strip()
        self.stat.setdefault(maker, Counter())
        self.stat[maker][model] += 1

    def __str__(self):
        r = ''
        for maker in sorted(self.stat.keys()):
            for model in sorted(self.stat[maker].keys()):
                r += f'{maker: >25} | {model: >40} | {self.stat[maker][model]:<5}\n'
        return r


class Nocam(BasicProcessor):
    """ Finds photos w/o camera maker/model """
    lst = []

    def process(self, f):
        p = Photo(f)
        if p.get('Exif.Image.Make') is None or p.get('Exif.Image.Model') is None:
            self.lst.append(f)

    def __str__(self):
        return '\n'.join(self.lst)


class Hugin(BasicProcessor):
    """ Finds Hugin-processed photos """
    lst = {}

    def process(self, f):
        p = Photo(f)
        software = p.get('Exif.Image.Software', '')
        if 'Hugin' in software:
            self.lst[f] = software

    def __str__(self):
        return '\n'.join(f'{upto60(k): >60} | {v: <30}' for k, v in self.lst.items())


class Nogps(BasicProcessor):
    """ Find photos without GPS tag """
    lst = []

    def process(self, f):
        p = Photo(f)
        if p.get('Exif.GPSInfo.GPSLatitude') is None or p.get('Exif.GPSInfo.GPSLongitude') is None:
            self.lst.append(f)

    def __str__(self):
        return '\n'.join(self.lst)

_parser = argparse.ArgumentParser()
_parser.add_argument('root', action='store', type=str)
_parser.add_argument('--cams', dest='mode', action='store_const', const=Cams)
_parser.add_argument('--nocam', dest='mode', action='store_const', const=Nocam)
_parser.add_argument('--hugin', dest='mode', action='store_const', const=Hugin)
_parser.add_argument('--nogps', dest='mode', action='store_const', const=Nogps)

if __name__ == '__main__':
    args = _parser.parse_args()
    print(args.mode(args.root))

#    #if maker+model == 'QCOM-AAQCAM-AA':
#    #    print('XXX: file <%s>' % ff)
#    #if maker+model == '<UNDEF><UNDEF>':
#    #    print('XXX: file <%s>' % ff)


    #d1 = res['Exif.Photo.PixelXDimension'].value
    #d2 = res['Exif.Photo.PixelYDimension'].value
    #quot = max(d1, d2) / min(d1, d2)
    #if (quot > 1.8) and ('pano' not in ff):
    #    sizes[ff] = quot
