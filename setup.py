#!/usr/bin/env python
# -*- coding: latin1 -*-

from distutils.core import setup
from distutils.command.install_data import install_data
from distutils.dep_util import newer
from distutils.log import info

from rapid.config import version
import glob
import os

name = 'rapid-photo-downloader'

class InstallData(install_data):
    """ This class is largely copied from setup.py in Terminator 0.8.1 by Chris Jones <cmsj@tenshu.net>"""
    def run (self):
        self.data_files.extend (self._compile_po_files ())
        install_data.run (self)

    def _compile_po_files (self):
        data_files = []

        PO_DIR = 'po'
        for po in glob.glob (os.path.join (PO_DIR,'*.po')):
            lang = os.path.basename(po[:-3])
            mo = os.path.join('build', 'mo', lang, '%s.mo' % name)

            directory = os.path.dirname(mo)
            if not os.path.exists(directory):
                info('creating %s' % directory)
                os.makedirs(directory)

            if newer(po, mo):
                # True if mo doesn't exist
                cmd = 'msgfmt -o %s %s' % (mo, po)
                info('compiling %s -> %s' % (po, mo))
                if os.system(cmd) != 0:
                    raise SystemExit('Error while running msgfmt')

                dest = os.path.dirname(os.path.join('share', 'locale', lang, 'LC_MESSAGES', '%s.mo' % name))
                data_files.append((dest, [mo]))

        return data_files

package_data={'rapid': ['glade3/about.ui',
              'glade3/photo.svg',
              'glade3/photo66.png',
              'glade3/photo_icon.png',
              'glade3/prefs.ui',
              'glade3/rapid.ui',
              'glade3/errorlog.ui',
              'glade3/media-eject.png',
              'glade3/rapid-photo-downloader.svg',
              'glade3/rapid-photo-downloader-download-pending.png',
              'glade3/rapid-photo-downloader-downloaded-with-error.svg',
              'glade3/rapid-photo-downloader-downloaded-with-warning.svg',
              'glade3/rapid-photo-downloader-downloaded.svg',
              'glade3/rapid-photo-downloader-jobcode.svg',
              'glade3/thumbnails_icon.png',
              'glade3/video.svg',
              'glade3/video66.png',
              'glade3/zoom-in.png',
              'glade3/zoom-out.png',
              ]}

setup(name=name,
    version=version,
    description='Rapid Photo Downloader for Linux',
    license='GPL',
    author='Damon Lynch',
    author_email='damonlynch@gmail.com',
    maintainer='Damon Lynch',
    url='http://www.damonlynch.net/rapid',
    long_description=
"""Rapid Photo Downloader is written by a photographer for professional and
amateur photographers. It can  download photos and videos from multiple
cameras, memory cards and Portable Storage Devices simultaneously. It
provides many flexible, user-defined options for subfolder creation,
photo and video renaming, and backup.
""",
    packages = ['rapid'],
    package_data=package_data,
    scripts=['rapid-photo-downloader'],
    platforms=['linux'],
    data_files=[
        ('share/applications', ['data/rapid-photo-downloader.desktop']),
        ('share/pixmaps', ['data/icons/48x48/apps/rapid-photo-downloader.png', 'data/icons/rapid-photo-downloader.xpm']),
        ('share/icons/hicolor/16x16/apps', glob.glob('data/icons/16x16/apps/*.png')),
        ('share/icons/hicolor/22x22/apps', glob.glob('data/icons/22x22/apps/*.png')),
        ('share/icons/hicolor/24x24/apps', glob.glob('data/icons/24x24/apps/*.png')),
        ('share/icons/hicolor/48x48/apps', glob.glob('data/icons/48x48/apps/*.png')),
        ('/usr/share/kde4/apps/solid/actions/', ['data/kde/rapid-photo-downloader.desktop']),
        ('/usr/share/appdata/', ['data/rapid-photo-downloader.appdata.xml']),
    ],
    cmdclass={'install_data': InstallData}
)
