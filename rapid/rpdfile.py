#!/usr/bin/python
# -*- coding: latin1 -*-

### Copyright (C) 2011 Damon Lynch <damonlynch@gmail.com>

### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; either version 2 of the License, or
### (at your option) any later version.

### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.

### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import gtk

import time, datetime

import multiprocessing, logging
logger = multiprocessing.get_logger()

import pyexiv2

import paths

from gettext import gettext as _

import config
import metadataphoto
import metadatavideo

import problemnotification as pn

import thumbnail as tn


RAW_EXTENSIONS = ['arw', 'dcr', 'cr2', 'crw',  'dng', 'mos', 'mef', 'mrw', 
                  'nef', 'orf', 'pef', 'raf', 'raw', 'rw2', 'sr2', 'srw']
                        
NON_RAW_IMAGE_EXTENSIONS = ['jpg', 'jpe', 'jpeg', 'tif', 'tiff']

PHOTO_EXTENSIONS = RAW_EXTENSIONS + NON_RAW_IMAGE_EXTENSIONS

if metadatavideo.DOWNLOAD_VIDEO:
    # some distros do not include the necessary libraries that Rapid Photo Downloader 
    # needs to be able to download videos
    VIDEO_EXTENSIONS = ['3gp', 'avi', 'm2t', 'mov', 'mp4', 'mpeg','mpg', 'mod', 
                        'tod']
    VIDEO_THUMBNAIL_EXTENSIONS = ['thm']                        
else:
    VIDEO_EXTENSIONS = []
    VIDEO_THUMBNAIL_EXTENSIONS = []


FILE_TYPE_PHOTO = 0
FILE_TYPE_VIDEO = 1


def file_type(file_extension):
    """
    Uses file extentsion to determine the type of file - photo or video.
    
    Returns True if yes, else False.
    """
    if file_extension in PHOTO_EXTENSIONS:
        return FILE_TYPE_PHOTO
    elif file_extension in VIDEO_EXTENSIONS:
        return FILE_TYPE_VIDEO
    return None
    
def get_rpdfile(extension, name, display_name, path, size, 
                file_system_modification_time, 
                scan_pid, file_id):
                    
    if extension in VIDEO_EXTENSIONS:
        return Video(name, display_name, path, size,
                     file_system_modification_time, 
                     scan_pid, file_id)
    else:
        # assume it's a photo - no check for performance reasons (this will be
        # called many times)
        return Photo(name, display_name, path, size,
                     file_system_modification_time, 
                     scan_pid, file_id)

class FileTypeCounter:
    def __init__(self):
        self._counter = dict()
        
    def add(self, file_type):
        self._counter[file_type] = self._counter.setdefault(file_type, 0) + 1
        
    def file_types_present(self):
        """ 
        returns a string to be displayed to the user that can be used
        to show if a value refers to photos or videos or both, or just one
        of each
        """
        
        no_videos = self._counter.setdefault(FILE_TYPE_VIDEO, 0)
        no_images = self._counter.setdefault(FILE_TYPE_PHOTO, 0)
        
        if (no_videos > 0) and (no_images > 0):
            v = _('photos and videos')
        elif (no_videos == 0) and (no_images == 0):
            v = _('photos or videos')
        elif no_videos > 0:
            if no_videos > 1:
                v = _('videos')
            else:
                v = _('video')
        else:
            if no_images > 1:
                v = _('photos')
            else:
                v = _('photo')
        return v    
        
    def count_files(self):
        i = 0
        for key in self._counter:
            i += self._counter[key]
        return i
        
    def summarize_file_count(self):
        #Number of files, e.g. "433 photos and videos" or "23 videos".
        #Displayed in the progress bar at the top of the main application
        #window.
        file_types_present = self.file_types_present()
        file_count_summary = _("%(number)s %(filetypes)s") % \
                              {'number':self.count_files(),
                               'filetypes': file_types_present} 
        return (file_count_summary, file_types_present)
        
class RPDFile:
    """
    Base class for photo or video file, with metadata
    """

    def __init__(self, name, display_name, path, size, 
                 file_system_modification_time, 
                 scan_pid, file_id):
                     
        self.path = path

        self.name = name
        self.display_name = display_name

        self.full_file_name = os.path.join(path, name)
        
        self.size = size # type int
        
        self.modification_time = file_system_modification_time
        
        self.status = config.STATUS_NOT_DOWNLOADED
        self.problem = None # class Problem in problemnotifcation.py
                
        self._assign_file_type()
        
        self.scan_pid = scan_pid
        self.file_id = file_id
        self.unique_id = str(scan_pid) + ":" + file_id
        
        self.problem = None
        self.job_code = None
        
        # indicates whether to generate a thumbnail during the copy
        # files process
        self.generate_thumbnail = False
        
        # generated values
        
        self.temp_full_file_name = ''
        self.download_start_time = None
        
        self.download_subfolder = ''
        self.download_path = ''
        self.download_name = ''
        self.download_full_file_name = ''
        
        self.metadata = None
        
        # Values that will be inserted in download process --
        # (commented out because they're not needed until then)
        
        #self.sequences = None
        #self.download_folder
        #self.subfolder_pref_list = []
        #self.name_pref_list = []
        #strip_characters = False
        
        
    def _assign_file_type(self):
        self.file_type = None
        
    def initialize_problem(self):
        self.problem = pn.Problem()
        # these next values are used to display in the error log window
        # the information in them can vary from other forms of display of errors
        self.error_title = self.error_msg = self.error_extra_detail = ''
        
    def has_problem(self):
        if self.problem is None:
            return False
        else:
            return self.problem.has_problem()
        
    def add_problem(self, component, problem_definition, *args):
        if self.problem is None:
            self.initialize_problem()
        self.problem.add_problem(component, problem_definition, *args)
    
    def add_extra_detail(self, extra_detail, *args):
        self.problem.add_extra_detail(extra_detail, *args)
    

        
#~ exif_tags_needed = ('Exif.Photo.FNumber', 
                    #~ 'Exif.Photo.ISOSpeedRatings',
                    #~ 'Exif.Photo.ExposureTime',
                    #~ 'Exif.Photo.FocalLength',
                    #~ 'Exif.Image.Make',
                    #~ 'Exif.Image.Model',
                    #~ 'Exif.Canon.SerialNumber',
                    #~ 'Exif.Nikon3.SerialNumber'
                    #~ 'Exif.OlympusEq.SerialNumber',
                    #~ 'Exif.Olympus.SerialNumber',
                    #~ 'Exif.Olympus.SerialNumber2',
                    #~ 'Exif.Panasonic.SerialNumber',
                    #~ 'Exif.Fujifilm.SerialNumber',
                    #~ 'Exif.Image.CameraSerialNumber',
                    #~ 'Exif.Nikon3.ShutterCount',
                    #~ 'Exif.Canon.FileNumber',
                    #~ 'Exif.Canon.ImageNumber',
                    #~ 'Exif.Canon.OwnerName',
                    #~ 'Exif.Photo.DateTimeOriginal',
                    #~ 'Exif.Image.DateTime',
                    #~ 'Exif.Photo.SubSecTimeOriginal',
                    #~ 'Exif.Image.Orientation'
                   #~ )
                   
class Photo(RPDFile):
    
    title = _("photo")
    title_capitalized = _("Photo")
    
    def _assign_file_type(self):
        self.file_type = FILE_TYPE_PHOTO
        
    def load_metadata(self):
        
        self.metadata = metadataphoto.MetaData(self.full_file_name)
        try:
            self.metadata.read()
        except:
            logger.warning("Could not read metadata from %s" % self.full_file_name)
            return False
        else:
            return True
    
            
class Video(RPDFile):
    
    title = _("video")
    title_capitalized = _("Video")
    
    def _assign_file_type(self):
        self.file_type = FILE_TYPE_VIDEO
        
    def load_metadata(self):
        self.metadata = metadatavideo.VideoMetaData(self.full_file_name)
        return True
        
class SamplePhoto(Photo):
    def __init__(self, sample_name='IMG_0524.CR2', sequences=None):
        Photo.__init__(self, name=sample_name,
                       display_name=sample_name,
                       path='/media/EOS_DIGITAL/DCIM/100EOS5D',
                       size=23516764, 
                       file_system_modification_time=time.time(), 
                       scan_pid=2033,
                       file_id='9873afe')
        self.sequences = sequences
        self.metadata = metadataphoto.DummyMetaData()
        self.download_start_time = datetime.datetime.now()
        
class SampleVideo(Video):
    def __init__(self, sample_name='MVI_1379.MOV', sequences=None):
        Video.__init__(self, name=sample_name,
                       display_name=sample_name,
                       path='/media/EOS_DIGITAL/DCIM/100EOS5D',
                       size=823513764, 
                       file_system_modification_time=time.time(), 
                       scan_pid=2033,
                       file_id='9873qrsfe')
        self.sequences = sequences
        self.metadata = metadatavideo.DummyMetaData(filename=sample_name)
        self.download_start_time = datetime.datetime.now()