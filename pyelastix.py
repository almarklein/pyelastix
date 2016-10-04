""" Module pyElastix

Python wrapper for the Elastix toolkit.


Introduction
------------

Wraps the Elastix registration toolkit. The elastix command line
application needs to be installed on your computer. You can obtain
a copy at [http://elastix.isi.uu.nl/].

The implementation in this module is written to depend on as little
packages as possible. In the pirt package, this class is wrapped to 
provide an interface that's easier to use and fits in the pirt 
framework.


Elastix executables
-------------------

On initialization, this module tries to detect the elastix and 
transformix executables on your computer. If this fails, it will
simply use the executable names, which will work if these are on
your PATH. 

You can also set the full path of the executables using the module
constants ELASTIX_EXE and TRANSFORMIX_EXE.


Example
-------

# Create Elastix instance
from elastix import Elastix
reg = Elastix()

# Get params and change a few values
params = reg.get_default_params('bspline')
params.MaximumNumberOfIterations = 200
params.FinalGridSpacingInVoxels = 10

# Apply the registration (im1 and im2 can be 2D or 3D)
im1_deformed, field = reg.register(im1, im2, params)

# field is a tuple with arrays describing the deformation for each
# dimension (x-y-z order).


Copyright
---------

This module is distributed under the (new) BSD license.
Copyright (C) 2010, Almar Klein. 

(Just to be clear, I am not one of the main authors of Elastix; that is
Stefan Klein)

"""

from __future__ import absolute_import, print_function, division 

#   Copyright (c) 2010, Almar Klein
#   All rights reserved.
#
#   This code is subject to the (new) BSD license:
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY 
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import os, sys, time
import platform, ctypes
import threading
import subprocess
import re
import numpy as np

# Try importing Aarray class from different sources
try:
    from pypoints import Aarray
except ImportError:
    try:
        from pirt import Aarray
    except ImportError:
        try:
            from visvis import Aarray
        except ImportError:
            Aarray = None


## Code for determining whether a pid is active
# taken from: http://www.madebuild.org/blog/?p=30

# GetExitCodeProcess uses a special exit code to indicate that the process is
# still running.
_STILL_ACTIVE = 259
 
def is_pid_running(pid):
    return (_is_pid_running_on_windows(pid) if platform.system() == "Windows"
        else _is_pid_running_on_unix(pid))
 
def _is_pid_running_on_unix(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
 
def _is_pid_running_on_windows(pid):
    import ctypes.wintypes
 
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(1, 0, pid)
    if handle == 0:
        return False
 
    # If the process exited recently, a pid may still exist for the handle.
    # So, check if we can get the exit code.
    exit_code = ctypes.wintypes.DWORD()
    is_running = (
        kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0)
    kernel32.CloseHandle(handle)
 
    # See if we couldn't get the exit code or the exit code indicates that the
    # process is still running.
    return is_running or exit_code.value == _STILL_ACTIVE


## Helper functions and classes


def _find_executables():
    """ _find_executables()
    
    Tries to find the elastix and transformix executables.
    
    """
    
    # Get list of possible locations
    if sys.platform.startswith('win'):
        possible_locations = [  'c:\\program files\\elastix', 
                                'c:\\program files (x86)\\elastix']
        for s in ['PROGRAMFILES', 'PROGRAMFILES(x86)']:
            tmp = os.environ.get(s)
            if tmp:
                possible_locations.append(os.path.join(tmp, 'elastix'))
        elastix_name = 'elastix.exe'
        transformix_name = 'transformix.exe'
    else:
        possible_locations = [  '/usr/bin','/usr/local/bin','/opt/local/bin',
                                '/usr/elastix', '/usr/local/elastix',
                                '/usr/bin/elastix', '/usr/local/bin/elastix']
        elastix_name = 'elastix'
        transformix_name = 'transformix'
    
    # Possible location might also be the location of this file ...
    possible_locations.append( os.path.dirname(os.path.abspath(__file__)) )
    
    # Set default (for if we could not find the absolute location)
    elastix_exe = elastix_name
    transformix_exe = transformix_name
    
    # Test
    for p in possible_locations:
        p1 = os.path.join(p, elastix_name)
        p2 = os.path.join(p, transformix_name)
        if os.path.isfile(p1):
            elastix_exe = p1
        if os.path.isfile(p2):
            transformix_exe = p2
    
    # Post process
    if ' ' in elastix_exe:
        elastix_exe = '"%s"' % elastix_exe
    if ' ' in transformix_exe:
        transformix_exe = '"%s"' % transformix_exe
    
    # Done
    return elastix_exe, transformix_exe


def _clear_dir(dirName):
    """ _clear_dir(dirName)
    
    Remove a directory and it contents. Ignore any failures.
    
    """
    # If we got here, clear dir  
    for fname in os.listdir(dirName):
        try:
            os.remove( os.path.join(dirName, fname) )
        except Exception:
            pass
    try:
        os.rmdir(dirName)
    except Exception:
        pass


def _find_tempdir():
    """ _find_tempdir()
    
    Establishes the directory to store temporaty files. 
    This also cleans up any elastix tempdirs of processes that no longer 
    exist.
    
    """
    
    # Establish default temp directory
    if sys.platform.startswith('win'):
        # Detect base temp dir
        tempdir = ''
        for foo in ['tmp', 'Tmp', 'temp', 'Temp']:
            if os.path.isdir('c:/' + foo):
                tempdir = 'c:/' + foo
                break
        else:
            tempdir = 'c:/tmp'        
        
        # Get pyElastix part
        tempdir += '/pyElastix'
        
    else:
        # Linux, Mac
        tempdir = '/var/tmp/pyElastix'
    
    # Make sure it exists and return
    if not os.path.isdir(tempdir):
        os.makedirs(tempdir)
    
    # Clean up all directories for which the process no longer exists
    for fname in os.listdir(tempdir):
        dirName = os.path.join(tempdir, fname)
        # Check if is right kind of dir
        if not (os.path.isdir(dirName) and  fname.startswith('pid')):
            continue
        # Get pid and check if its running
        try:
            pid = int(fname[3:])
        except Exception:
            continue
        if not is_pid_running(pid):
            _clear_dir(dirName)
    
    # Get the name of the final dir to store our files
    tempdir = os.path.join(tempdir, 'pid%i' % os.getpid())
    
    return tempdir


def _get_dtype_maps():
    """ _get_dtype_maps()
    
    Get dictionaries to map numpy data types to ITK types and the 
    other way around.
    
    """
    
    # Define pairs
    tmp = [ (np.float32, 'MET_FLOAT'),  (np.float64, 'MET_DOUBLE'),
            (np.uint8, 'MET_UCHAR'),    (np.int8, 'MET_CHAR'),
            (np.uint16, 'MET_USHORT'),  (np.int16, 'MET_SHORT'),
            (np.uint32, 'MET_UINT'),    (np.int32, 'MET_INT'),
            (np.uint64, 'MET_ULONG'),   (np.int64, 'MET_LONG') ]
    
    # Create dictionaries
    map1, map2 = {}, {}
    for np_type, itk_type in tmp:
        map1[np_type.__name__] = itk_type
        map2[itk_type] = np_type.__name__
    
    # Done
    return map1, map2

    

def system3(cmd, verbose=False):
    """ system3(cmd, verbose=False)
    
    Execute the given command in a subprocess and wait for it to finish.
    A thread is run that prints output of the process if verbose is True.
    
    """
    
    # Init flag
    interrupted = False
    
    # Create progress
    if verbose > 0:
        progress = Progress()
    
    def poll_process(p):
        # Keep reading stdout
        while not interrupted:
            msg = p.stdout.readline()
            if msg:
                if 'error' in msg.lower():
                    print(msg.rstrip())
                    if verbose==1:
                        progress.reset()
                elif verbose>1:
                    print(msg.rstrip())
                elif verbose==1:
                    progress.update(msg)
            else:
                break
            time.sleep(0.01)
        
        #print("thread exit")
    
    # Start process that runs the command
    p = subprocess.Popen(cmd, shell=True, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    
    # Keep reading stdout from it
    # thread.start_new_thread(poll_process, (p,))  Python 2.x
    my_thread = threading.Thread(target=poll_process, args=(p,))
    my_thread.setDaemon(True)
    my_thread.start()
    
    # Wait here
    try:
        while p.poll() is None:
            time.sleep(0.01)
    except KeyboardInterrupt:
        # Set flag
        interrupted = True
        # Kill subprocess
        pid = p.pid
        if hasattr(os,'kill'):
            import signal
            os.kill(pid, signal.SIGKILL)
        elif sys.platform.startswith('win'):
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, 0, pid)
            kernel32.TerminateProcess(handle, 0)
            #os.system("TASKKILL /PID " + str(pid) + " /F")
    
    # All good?
    if interrupted:
        raise RuntimeError('Registration process interrupted by the user.')
    if p.returncode:
        print(p.stdout.read())
        raise RuntimeError('An error occured during the registration.')



class Parameters:
    """ Parameters()
    
    To represent the parameters for the elastix registration toolkit.
    Sets of parameters can be combined by addition. (When adding "p1+p2",
    any parameters present in both objects will take the value that the
    parameter has in p2.)
    
    """
    
    def as_dict(self):
        """ as_dict()
        
        Returns the parameters as a dictionary. 
        
        """
        tmp = {}
        tmp.update(self.__dict__)
        return tmp
    
    def __repr__(self):
        return '<Parameters instance with %i parameters>' % len(self.__dict__)
    
    def __str__(self):
        
        # Get alignment value
        c = 0
        for key in self.__dict__:
            c = max(c, len(key))
        
        # How many chars left (to print on less than 80 lines)
        charsLeft = 79 - (c+6)
        
        s = '<%i parameters>\n' % len(self.__dict__)
        for key in self.__dict__.keys():
            valuestr = repr(self.__dict__[key])
            if len(valuestr) > charsLeft:
                valuestr = valuestr[:charsLeft-3] + '...'
            s += key.rjust(c+4) + ": %s\n" % (valuestr)
        return s
    
    def __add__(self, other):
        p = Parameters()
        p.__dict__.update(self.__dict__)
        p.__dict__.update(other.__dict__)
        return p


class Progress:
    """ Progress()
    
    To show progress during the registration.
    
    """
    
    def __init__(self):
        self._level = 0
        self.reset()
    
    def update(self, s):
        
        # Detect resolution
        if s.startswith('Resolution:'):
            self._level = self.get_int( s.split(':')[1] )
        
        # Check if nr
        if '\t' in s:
            iter = self.get_int( s.split('\t',1)[0] )
            if iter:
                self.show_progress(iter)
    
    def get_int(self, s):
        nr = 0
        try:
            nr = int(s)
        except Exception:
            pass
        return nr
    
    def reset(self):
        self._message = ''
        print()
    
    def show_progress(self, iter):
        
        # Remove previous message
        rem = '\b' * (len(self._message)+1)
        
        # Create message, and print
        self._message = 'resolution %i, iter %i' % (self._level, iter)
        print(rem + self._message)
    

## The Elastix registration class


class Elastix(object):
    """ Elastix()
    
    Creates an Elastix registration object. The implementation in this 
    module is written to depend on as little packages as possible. In 
    the pirt package, this class is wrapped to provide an interface 
    that's easier to use and fits in the pirt framework.
    
    Use get_default_parameters() and get_advanced_parameters() to get 
    structs with parameters (which can be combined by adding them).
    
    Call register() to apply the registration and obtain the result.
    
    """
    
    def __init__(self):
        pass
    
    
    def register(self, im1, im2, params, exact_params=False, verbose=1):
        """ register(self, im1, im2, params, exact_params=False, verbose=1)
        
        Perform the registration of im1 to im2, using the given 
        dictionary of parameters.
        
        Returns (im1_deformed, field), where field is a tuple with arrays
        describing the deformation for each dimension (x-y-z order, in 
        world units).
        
        
        Parameters
        ----------
        im1 : ndarray or file location
            The moving image (the one to deform)
        im2 : ndarray or file location
            The static (reference) image
        params : dict or instance_returned by get*params()
            The parameters of the registration. Default parameters can be
            obtained using the get_default_params() method. Note that any
            parameter known to elastix can be added to the returned 
            parameter structure, which enables tuning the registration in 
            great detail. See below for a description on some common 
            parameters.
        exact_params : bool
            If True, use the exact given parameters. If False (default) will
            process the parameters, checking for incompatible parameters,
            extending values to list if a value needs to be given for each
            dimension.
        verbose : int
            Verbose level. If 0, will not print any progress. If 1, will
            print the progress only. If 2, will print the full output
            produced by the elastix executable. Note that error messages
            produced by elastix will be printed regardless of the verbose 
            level.
        
        
        Registration parameters 
        -----------------------
        This lists some of the default parameters, for more details
        we refer to the elastix manual.
        
        Transform : {'BSplineTransform', 'EulerTransform', 'AffineTransform'}
            The transformation to apply. Chosen by the argument of 
            get_default_params.
        FinalGridSpacingInPhysicalUnits : int
            When using the BSplineTransform, the final spacing of the grid.
            This controls the smoothness of the final deformation.
        AutomaticScalesEstimation : bool
            When using a rigid or affine transform. Scales the affine matrix
            elements compared to the translations, to make sure they are in
            the same range. In general, it's best to use automatic scales
            estimation.
        AutomaticTransformInitialization : bool
            When using a rigid or affine transform. Automatically guess an
            initial translation by aligning the geometric centers of the 
            fixed and moving.
        NumberOfResolutions : int
            Most registration algorithms adopt a multiresolution approach
            to direct the solution towards a global optimum and to speed
            up the process. This parameter specifies the number of scales
            to apply the registration at. (default 4)
        MaximumNumberOfIterations  : int
            Maximum number of iterations in each resolution level.
            200-2000 works usually fine for nonrigid registration.
            The more, the better, but the longer computation time.
            This is an important parameter! (default 500)
        
        """
        
        # Clear dir
        self._clear_temp_dir()
        
        # Reference image
        refIm = im1
        if isinstance(im1, (tuple,list)):
            refIm = im1[0]
        
        # Check parameters
        if not exact_params:
            params = self._compile_params(params, refIm)
        if isinstance(params, Parameters):
            params = params.as_dict()
        
        # Groupwise?
        if im2 is None:
            # todo: also allow using a constraint on the "last dimensin"
            if not isinstance(im1, (tuple,list)):
                raise ValueError('im2 is None, but im1 is not a list.')
            #
            ims = im1
            ndim = ims[0].ndim
            # Create new image that is a combination of all images
            N = len(ims)
            new_shape = (N,) + ims[0].shape
            im1 = np.zeros(new_shape, ims[0].dtype)
            for i in range(N):
                im1[i] = ims[i]
            # Set parameters
            #params['UseCyclicTransform'] = True # to be chosen by user
            params['FixedImageDimension'] = im1.ndim
            params['MovingImageDimension'] = im1.ndim
            params['FixedImagePyramid'] = 'FixedSmoothingImagePyramid'
            params['MovingImagePyramid'] = 'MovingSmoothingImagePyramid'
            params['Metric'] = 'VarianceOverLastDimensionMetric'
            params['Transform'] = 'BSplineStackTransform'
            params['Interpolator'] = 'ReducedDimensionBSplineInterpolator'
            params['SampleLastDimensionRandomly'] = True
            params['NumSamplesLastDimension'] = 5
            params['SubtractMean'] = True
            # No smoothing along that dimenson
            pyramidsamples = []
            for i in range(params['NumberOfResolutions']):
                pyramidsamples.extend( [0]+[2**i]*ndim )
            pyramidsamples.reverse()
            params['ImagePyramidSchedule'] = pyramidsamples
        
        # Get paths of input images
        path_im1, path_im2 = self._get_image_paths(im1, im2)
        
        # Determine path of parameter file and write params
        path_params = self._write_parameter_file(params)
        
        # Get path of trafo param file
        path_trafo_params = os.path.join(TEMPDIR, 'TransformParameters.0.txt')
        
        # Register
        if True:
            
            # Compile command to execute
            command = ELASTIX_EXE
            command += ' -m %s -f %s -out %s -p %s' % (
                path_im1, path_im2, TEMPDIR, path_params)
            
            # Execute command
            if verbose:
                print("Calling Elastix to register images ...")
            system3(command, verbose)
            
            # Try and load result
            try:
                a = self._read_image_data('result.0.mhd')
            except IOError as why:
                tmp = "An error occured during registration: " + str(why)
                raise RuntimeError(tmp)
        
        # Find deformation field
        if True:
            
            # Compile command to execute
            command = TRANSFORMIX_EXE
            command += ' -def all -out %s -tp %s' % (
                TEMPDIR, path_trafo_params)
            
            # Execute command
            system3(command, verbose)
            
            # Try and load result
            try:
                b = self._read_image_data('deformationField.mhd')
            except IOError as why:
                tmp = "An error occured during transformation: " + str(why)
                raise RuntimeError(tmp)
        
        # Get deformation fields (for each image)
        if im2 is None:
            fields = [b[i] for i in range(b.shape[0])]
        else:
            fields = [b]
        
        # Pull apart deformation fields in multiple images
        for i in range(len(fields)):
            field = fields[i]
            if field.ndim == 2:
                field = [field[:,d] for d in range(1)]
            elif field.ndim == 3:
                field = [field[:,:,d] for d in range(2)]
            elif field.ndim == 4:
                field = [field[:,:,:,d] for d in range(3)]
            elif field.ndim == 5:
                field = [field[:,:,:,:,d] for d in range(4)]
            fields[i] = tuple(field)
        
        # Clean and return
        self._clear_temp_dir()
        return a, fields
    
    
    def _clear_temp_dir(self):
        """ _clear_temp_dir()
        
        Clear the temporary directory.
        
        """
        for fname in os.listdir(TEMPDIR):
            try:
                os.remove( os.path.join(TEMPDIR, fname) )
            except Exception:
                pass
    
    
    def _get_image_paths(self, im1, im2):
        """ _get_image_paths(self, im1, im2)
        
        If the images are paths to a file, checks whether the file
        exist and return the paths.
        
        If the images are numpy arrays, writes them to disk and returns
        the paths of the new files.
        
        """
        
        paths = []
        for im in [im1, im2]:
            if im is None:
                # Groupwise registration: only one image (ndim+1 dimensions)
                paths.append(paths[0])
                continue
            
            if isinstance(im, basestring):
                # Given a location
                if os.path.isfile(im1):
                    paths.append(im)
                else:
                    raise ValueError('Image location does not exist.')
            
            elif isinstance(im, np.ndarray):
                # Given a numpy array
                id = len(paths)+1
                p = self._write_image_data(im, id)
                paths.append(p)
            
            else:
                # Given something else ...
                raise ValueError('Invalid input image.')
        
        # Done
        return tuple(paths)
    
    
    def _write_image_data(self, im, id):
        """ _write_image_data(self, im, id)
        
        Write a numpy array to disk in the form of a .raw and .mhd file.
        The id is the image sequence number (1 or 2).
        
        Returns the path of the mhd file.
        
        """
        im = im* (1.0/3000)
        # Create text
        lines = [   "ObjectType = Image",
                    "NDims = <ndim>",
                    "BinaryData = True",
                    "BinaryDataByteOrderMSB = False",
                    "CompressedData = False",
                    #"TransformMatrix = <transmatrix>",
                    "Offset = <origin>",
                    "CenterOfRotation = <centrot>",
                    "ElementSpacing = <sampling>",
                    "DimSize = <shape>",
                    "ElementType = <dtype>",
                    "ElementDataFile = <fname>",
                    "" ]
        text = '\n'.join(lines)
        
        # Determine file names
        fname_raw_ = 'im%i.raw' % id
        fname_raw = os.path.join(TEMPDIR, fname_raw_)
        fname_mhd = os.path.join(TEMPDIR, 'im%i.mhd' % id)
        
        # Get shape, sampling and origin
        shape = im.shape
        if hasattr(im, 'sampling'): sampling = im.sampling
        else: sampling = [1 for s in im.shape]
        if hasattr(im, 'origin'): origin = im.origin
        else: origin = [0 for s in im.shape]
        
        # Make all shape stuff in x-y-z order and make it string
        shape = ' '.join([str(s) for s in reversed(shape)])
        sampling = ' '.join([str(s) for s in reversed(sampling)])
        origin = ' '.join([str(s) for s in reversed(origin)])
        
        # Get data type
        dtype_itk = DTYPE_NP2ITK.get(im.dtype.name, None)
        if dtype_itk is None:
            raise ValueError('Cannot convert data of this type: '+ str(im.dtype))
        
        # Set mhd text
        text = text.replace('<fname>', fname_raw_)
        text = text.replace('<ndim>', str(im.ndim))
        text = text.replace('<shape>', shape)
        text = text.replace('<sampling>', sampling)
        text = text.replace('<origin>', origin)
        text = text.replace('<dtype>', dtype_itk)
        text = text.replace('<centrot>', ' '.join(['0' for s in im.shape]))
        if im.ndim==2:
            text = text.replace('<transmatrix>', '1 0 0 1')
        elif im.ndim==3:
            text = text.replace('<transmatrix>', '1 0 0 0 1 0 0 0 1')
        elif im.ndim==4:
            pass # ???
        
        # Write data file
        f = open(fname_raw, 'wb')
        try:
            f.write(im.data)
        finally:
            f.close()
        
        # Write mhd file
        f = open(fname_mhd, 'wb')
        try:
            f.write(text.encode('utf-8'))
        finally:
            f.close()
        
        # Done, return path of mhd file
        return fname_mhd
    
    
    def _read_image_data(self, mhd_file):
        """ _read_image_data(mhd_file)
        
        Read the resulting image data and return it as a numpy array.
        
        """
        
        # Load description from mhd file
        fname = TEMPDIR + '/' + mhd_file
        des = open(fname, 'r').read()
        
        # Get data filename and load raw data
        match = re.findall('ElementDataFile = (.+?)\n', des)
        fname = TEMPDIR + '/' + match[0]
        data = open(fname, 'rb').read()
        
        # Determine dtype
        match = re.findall('ElementType = (.+?)\n', des)
        dtype_itk = match[0].upper().strip()
        dtype = DTYPE_ITK2NP.get(dtype_itk, None)
        if dtype is None:
            raise RuntimeError('Unknown ElementType: ' + dtype_itk)
        
        # Create numpy array, try making Aarray
        a = np.frombuffer(data, dtype=dtype)
        
        # Determine shape, sampling and origin of the data
        match = re.findall('DimSize = (.+?)\n', des)
        shape = [int(i) for i in match[0].split(' ')]
        #
        match = re.findall('ElementSpacing = (.+?)\n', des)
        sampling = [float(i) for i in match[0].split(' ')]
        #
        match = re.findall('Offset = (.+?)\n', des)
        origin = [float(i) for i in match[0].split(' ')]
        
        # Reverse shape stuff to make z-y-x order
        shape = [s for s in reversed(shape)]
        sampling = [s for s in reversed(sampling)]
        origin = [s for s in reversed(origin)]
        
        # Take vectors/colours into account
        N = reduce(lambda x,y:x*y, shape)
        if N != a.size:
            extraDim = int( a.size / N )
            shape = tuple(shape) + (extraDim,)
            sampling = tuple(sampling) + (1.0,)
            origin = tuple(origin) + (0,)
        
        # Check shape
        N = reduce(lambda x,y:x*y, shape)
        if N != a.size:
            raise RuntimeError('Cannot apply shape to data.')
        else:
            a.shape = shape
            if Aarray:
                a = Aarray(a, sampling, origin)
        
        # Done
        return a
    
    
    def _compile_params(self, params, im1):
        """ _compile_params(params, im1)
        
        Compile the params dictionary:
          * Combine parameters from different sources
          * Perform checks to prevent non-compatible parameters
          * Extend parameters that need a list with one element per dimension
        
        """
        
        # Compile parameters
        p = self._get_fixed_params(im1) + self.get_advanced_params()
        p = p + params
        params = p.as_dict()
        
        # Check parameter dimensions
        if isinstance(im1, np.ndarray):
            lt = (list, tuple)
            for key in [    'FinalGridSpacingInPhysicalUnits',
                            'FinalGridSpacingInVoxels' ]:
                if key in params.keys() and not isinstance(params[key], lt):
                    params[key] = [params[key]] * im1.ndim
        
        # Check parameter removal
        if 'FinalGridSpacingInVoxels' in params:
            if 'FinalGridSpacingInPhysicalUnits' in params:
                params.pop('FinalGridSpacingInPhysicalUnits')
        
        # Done
        return params
    
    
    def _write_parameter_file(self, params):
        """ _write_parameter_file(params)
        
        Write the parameter file in the format that elaxtix likes.
        
        """
        
        # Get path
        path = os.path.join(TEMPDIR, 'params.txt')
        
        # Define helper function
        def valToStr(val):
            if val in [True, False]:
                return '"%s"' % str(val).lower()
            elif isinstance(val, int):
                return str(val)
            elif isinstance(val, float):
                tmp = str(val)
                if not '.' in tmp:
                    tmp += '.0'
                return tmp
            elif isinstance(val, basestring):
                return '"%s"' % val
        
        # Compile text
        text = ''
        for key in params:
            val = params[key]
            # Make a string of the values
            if isinstance(val, (list, tuple)):
                vals = [valToStr(v) for v in val]
                val_ = ' '.join(vals)
            else:
                val_ = valToStr(val)
            # Create line and add
            line = '(%s %s)' % (key, val_)
            text += line + '\n'
        
        # Write text
        f = open(path, 'wb')
        try:
            f.write(text.encode('utf-8'))
        finally:
            f.close()
        
        # Done
        return path
    
    
    def _get_fixed_params(self, im):
        """ _get_fixed_params(self, im)
        
        Parameters that the user has no influence on. Mostly chosen
        bases on the input images.
        
        """
        
        p = Parameters()
        
        if not isinstance(im, np.ndarray):
            return p
        
        # Dimension of the inputs
        p.FixedImageDimension = im.ndim
        p.MovingImageDimension = im.ndim
        
        # Always write result, so I can verify
        p.WriteResultImage = True
        
        # How to write the result
        tmp = DTYPE_NP2ITK[im.dtype.name]
        p.ResultImagePixelType = tmp.split('_')[-1].lower()
        p.ResultImageFormat = "mhd"
        
        # Done
        return p
    
    
    def get_advanced_params(self):
        """ get_advanced_params()
        
        Parameters that most users do not want to think about.
        
        """
        
        p = Parameters()
        
        # Internal format used during the registration process
        p.FixedInternalImagePixelType = "float"
        p.MovingInternalImagePixelType = "float"
        
        # Image direction
        p.UseDirectionCosines = True
        
        # In almost all cases you'd want multi resolution
        p.Registration = 'MultiResolutionRegistration'
        
        # Pyramid options
        # *RecursiveImagePyramid downsamples the images
        # *SmoothingImagePyramid does not downsample
        p.FixedImagePyramid = "FixedRecursiveImagePyramid"
        p.MovingImagePyramid = "MovingRecursiveImagePyramid"
        
        # Whether transforms are combined by composition or by addition.
        # It does not influence the results very much.
        p.HowToCombineTransforms = "Compose"
        
        # For out of range pixels
        p.DefaultPixelValue = 0
        
        # Interpolator used during interpolation and its order
        # 1 means linear interpolation, 3 means cubic.
        p.Interpolator = "BSplineInterpolator"
        p.BSplineInterpolationOrder = 1
        
        # Interpolator used during interpolation of final level, and its order
        p.ResampleInterpolator = "FinalBSplineInterpolator"
        p.FinalBSplineInterpolationOrder = 3
        
        # According to the manual, there is currently only one resampler
        p.Resampler = "DefaultResampler"
        
        # Done
        return p
    
    
    def get_default_params(self, type):
        """ get_default_params(type)
        
        Interesting parameters.
        
        """
        
        # Init
        p = Parameters()
        type = type.upper()
        
        
        # ===== Metric to use =====
        p.Metric = 'AdvancedMattesMutualInformation'
        
        # Number of grey level bins in each resolution level,
        # for the mutual information. 16 or 32 usually works fine.
        # sets default value for NumberOf[Fixed/Moving]HistogramBins
        p.NumberOfHistogramBins = 32
        
        # Taking samples for mutual information
        p.ImageSampler = 'RandomCoordinate'
        p.NumberOfSpatialSamples = 2048
        p.NewSamplesEveryIteration = True
        
        
        # ====== Transform to use ======
        
        # The number of levels in the image pyramid
        p.NumberOfResolutions = 4
        
        if type in ['B', 'BSPLINE', 'B-SPLINE']:
            
            # Bspline transform
            p.Transform = 'BSplineTransform'
            
            # The final grid spacing (at the smallest level)
            p.FinalGridSpacingInPhysicalUnits = 16
        
        if type in ['RIGID', 'EULER', 'AFFINE']:
            
            # Affine or Euler transform
            if type in ['RIGID', 'EULER']:
                p.Transform = 'EulerTransform'
            else:
                p.Transform = 'AffineTransform'
            
            # Scales the affine matrix elements compared to the translations, 
            # to make sure they are in the same range. In general, it's best to
            # use automatic scales estimation.
            p.AutomaticScalesEstimation = True
            
            # Automatically guess an initial translation by aligning the
            # geometric centers of the fixed and moving.
            p.AutomaticTransformInitialization = True
        
        
        # ===== Optimizer to use =====
        p.Optimizer = 'AdaptiveStochasticGradientDescent'
        
        # Maximum number of iterations in each resolution level:
        # 200-2000 works usually fine for nonrigid registration.
        # The more, the better, but the longer computation time.
        # This is an important parameter!
        p.MaximumNumberOfIterations = 500
        
        # The step size of the optimizer, in mm. By default the voxel size is used.
        # which usually works well. In case of unusual high-resolution images
        # (eg histology) it is necessary to increase this value a bit, to the size
        # of the "smallest visible structure" in the image:
        #p.MaximumStepLength = 1.0 Default uses voxel spaceing
        
        # Another optional parameter for the AdaptiveStochasticGradientDescent
        #p.SigmoidInitialTime = 4.0
        
        
        # ===== Also interesting parameters =====
        
        #p.FinalGridSpacingInVoxels = 16
        #p.GridSpacingSchedule = [4.0, 4.0, 2.0, 1.0]
        #p.ImagePyramidSchedule = [8 8  4 4  2 2  1 1]
        #p.ErodeMask = "false"
        
        # Done
        return p


## Obtain constants

# Paths to executables
ELASTIX_EXE, TRANSFORMIX_EXE = _find_executables()

# Temp directory
TEMPDIR = _find_tempdir()

# data type maps
DTYPE_NP2ITK, DTYPE_ITK2NP = _get_dtype_maps()
