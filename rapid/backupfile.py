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

import multiprocessing
import tempfile
import os

import gio

import logging
logger = multiprocessing.get_logger()

import rpdmultiprocessing as rpdmp
import rpdfile
import problemnotification as pn
import config


from gettext import gettext as _


class BackupFiles(multiprocessing.Process):
    def __init__(self, path, name,
                 batch_size_MB, results_pipe, terminate_queue, 
                 run_event):
        multiprocessing.Process.__init__(self)
        self.results_pipe = results_pipe
        self.terminate_queue = terminate_queue
        self.batch_size_bytes = batch_size_MB * 1048576 # * 1024 * 1024
        self.path = path
        self.mount_name = name
        self.run_event = run_event
        
    def check_termination_request(self):
        """
        Check to see this process has not been requested to immediately terminate
        """
        if not self.terminate_queue.empty():
            x = self.terminate_queue.get()
            # terminate immediately
            logger.info("Terminating file backup")
            return True
        return False
        
        
    def update_progress(self, amount_downloaded, total):
        # first check if process is being terminated
        self.amount_downloaded = amount_downloaded
        if not self.terminate_queue.empty():
            # it is - cancel the current copy
            self.cancel_copy.cancel()
        else:
            if not self.total_reached:
                chunk_downloaded = amount_downloaded - self.bytes_downloaded
                if (chunk_downloaded > self.batch_size_bytes) or (amount_downloaded == total):
                    self.bytes_downloaded = amount_downloaded
                    
                    if amount_downloaded == total:
                        # this function is called a couple of times when total is reached
                        self.total_reached = True
                        
                    self.results_pipe.send((rpdmp.CONN_PARTIAL, (rpdmp.MSG_BYTES, (self.scan_pid, self.pid, self.total_downloaded + amount_downloaded, chunk_downloaded))))
                    if amount_downloaded == total:
                        self.bytes_downloaded = 0
    
    def progress_callback(self, amount_downloaded, total):
        self.update_progress(amount_downloaded, total)
        

    def run(self):
        
        self.cancel_copy = gio.Cancellable()
        self.bytes_downloaded = 0
        self.total_downloaded = 0
        
        while True:
            
            self.amount_downloaded = 0
            move_succeeded, rpd_file, path_suffix, backup_duplicate_overwrite = self.results_pipe.recv()
            if rpd_file is None:
                # this is a termination signal
                return None
            # pause if instructed by the caller
            self.run_event.wait()
                
            if self.check_termination_request():
                return None
                
            backup_succeeded = False
            self.scan_pid = rpd_file.scan_pid
            
            if move_succeeded:
                self.total_reached = False
                    
                source = gio.File(path=rpd_file.download_full_file_name)
                
                if path_suffix is None:
                    dest_base_dir = self.path
                else:
                    dest_base_dir = os.path.join(self.path, path_suffix)
                    
                
                dest_dir = os.path.join(dest_base_dir, rpd_file.download_subfolder)
                backup_full_file_name = os.path.join(
                                    dest_dir, 
                                    rpd_file.download_name)            
                
                subfolder = gio.File(path=dest_dir)
                if not subfolder.query_exists(cancellable=None):
                    # create the subfolders on the backup path
                    try:
                        subfolder.make_directory_with_parents(cancellable=gio.Cancellable())
                    except gio.Error, inst:
                        # There is a tiny chance directory may have been created by
                        # another process between the time it takes to query and
                        # the time it takes to create a new directory. 
                        # Ignore such errors.
                        if inst.code <> gio.ERROR_EXISTS:
                            logger.error("Failed to create backup subfolder: %s", dest_dir)
                            logger.error(inst)
                            rpd_file.add_problem(None, pn.BACKUP_DIRECTORY_CREATION, self.mount_name)
                            rpd_file.add_extra_detail('%s%s' % (pn.BACKUP_DIRECTORY_CREATION, self.mount_name), inst)
                            rpd_file.error_title = _('Backing up error')
                            rpd_file.error_msg = \
                                 _("Destination directory could not be created: %(directory)s\n") % \
                                  {'directory': subfolder,  } + \
                                 _("Source: %(source)s\nDestination: %(destination)s") % \
                                  {'source': rpd_file.download_full_file_name, 
                                   'destination': backup_full_file_name} + "\n" + \
                                 _("Error: %(inst)s") % {'inst': inst}

                dest = gio.File(path=backup_full_file_name)
                if backup_duplicate_overwrite:
                    flags = gio.FILE_COPY_OVERWRITE
                else:
                    flags = gio.FILE_COPY_NONE            
                    
                try:
                    source.copy(dest, self.progress_callback, flags, 
                                        cancellable=self.cancel_copy)
                    backup_succeeded = True
                except gio.Error, inst:
                    fileNotBackedUpMessageDisplayed = True
                    rpd_file.add_problem(None, pn.BACKUP_ERROR, self.mount_name)
                    rpd_file.add_extra_detail('%s%s' % (pn.BACKUP_ERROR, self.mount_name), inst)
                    rpd_file.error_title = _('Backing up error')
                    rpd_file.error_msg = \
                            _("Source: %(source)s\nDestination: %(destination)s") % \
                             {'source': rpd_file.download_full_file_name, 'destination': backup_full_file_name} + "\n" + \
                            _("Error: %(inst)s") % {'inst': inst}
                    logger.error("%s:\n%s", rpd_file.error_title, rpd_file.error_msg)

                if not backup_succeeded:
                    if rpd_file.status ==  config.STATUS_DOWNLOAD_FAILED:
                        rpd_file.status = config.STATUS_DOWNLOAD_AND_BACKUP_FAILED
                    else:
                        rpd_file.status = config.STATUS_BACKUP_PROBLEM
            
            self.total_downloaded += rpd_file.size
            bytes_not_downloaded = rpd_file.size - self.amount_downloaded
            if bytes_not_downloaded:
                self.results_pipe.send((rpdmp.CONN_PARTIAL, (rpdmp.MSG_BYTES, (self.scan_pid, self.pid, self.total_downloaded, bytes_not_downloaded))))
                
            self.results_pipe.send((rpdmp.CONN_PARTIAL, (rpdmp.MSG_FILE,
                                   (backup_succeeded, rpd_file))))
            


            


