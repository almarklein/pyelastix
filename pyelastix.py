# Copyright (c) 2010-2016, Almar Klein
# This code is subject to the MIT license

"""
PyElastix - Python wrapper for the Elastix nonrigid registration toolkit

This Python module wraps the Elastix registration toolkit. For it to
work, the Elastix command line application needs to be installed on
your computer. You can obtain a copy at http://elastix.isi.uu.nl/.
Further, this module depends on numpy.

https://github.com/almarklein/pyelastix
"""

from __future__ import print_function, division 

__version__ = '1.1'

import os
import re
import sys
import time
import ctypes
import tempfile
import threading
import subprocess

import numpy as np


# %% Code for determining whether a pid is active
# taken from: http://www.madebuild.org/blog/?p=30

# GetExitCodeProcess uses a special exit code to indicate that the process is
# still running.
_STILL_ACTIVE = 259
 
def _is_pid_running(pid):
    """Get whether a process with the given pid is currently running.
    """
    if sys.platform.startswith("win"):
        return _is_pid_running_on_windows(pid)
    else:
        return _is_pid_running_on_unix(pid)
 
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


# %% Code for detecting the executablews


def _find_executables(name):
    """ Try to find an executable.
    """
    exe_name = name + '.exe' * sys.platform.startswith('win')
    env_path = os.environ.get(name.upper()+ '_PATH', '')
    
    possible_locations = []
    def add(*dirs):
        for d in dirs:
            if d and d not in possible_locations and os.path.isdir(d):
                possible_locations.append(d)
    
    # Get list of possible locations
    add(env_path)
    try:
        add(os.path.dirname(os.path.abspath(__file__)))
    except NameError:  # __file__ may not exist
        pass
    add(os.path.dirname(sys.executable))
    add(os.path.expanduser('~'))
    
    # Platform specific possible locations
    if sys.platform.startswith('win'):
        add('c:\\program files', os.environ.get('PROGRAMFILES'),
            'c:\\program files (x86)', os.environ.get('PROGRAMFILES(x86)'))
    else:
        possible_locations.extend(['/usr/bin','/usr/local/bin','/opt/local/bin'])
    
    def do_check_version(exe):
        try:
            return subprocess.check_output([exe, '--version']).decode().strip()
        except Exception:
            # print('not a good exe', exe)
            return False
    
    # If env path is the exe itself ...
    if os.path.isfile(env_path):
        ver = do_check_version(env_path)
        if ver:
            return env_path, ver
    
    # First try to find obvious locations
    for d in possible_locations:
        for exe in [os.path.join(d, exe_name), os.path.join(d, name, exe_name)]:
            if os.path.isfile(exe):
                ver = do_check_version(exe)
                if ver:
                    return exe, ver
    
    # Maybe the exe is on the PATH
    ver = do_check_version(exe_name)
    if ver:
        return exe_name, ver
        
    # Try harder
    for d in possible_locations:
        for sub in reversed(sorted(os.listdir(d))):
            if sub.startswith(name):
                exe = os.path.join(d, sub, exe_name)
                if os.path.isfile(exe):
                    ver = do_check_version(exe)
                    if ver:
                        return exe, ver
    
    return None, None


EXES = []

def get_elastix_exes():
    """ Get the executables for elastix and transformix. Raises an error
    if they cannot be found.
    """
    if EXES:
        if EXES[0]:
            return EXES
        else:
            raise RuntimeError('No Elastix executable.')
    
    # Find exe
    elastix, ver = _find_executables('elastix')
    if elastix:
        base, ext = os.path.splitext(elastix)
        base = os.path.dirname(base)
        transformix = os.path.join(base, 'transformix' + ext)
        EXES.extend([elastix, transformix])
        print('Found %s in %r' % (ver, elastix))
        return EXES
    else:
        raise RuntimeError('Could not find Elastix executable. Download '
                           'Elastix from http://elastix.isi.uu.nl/. Pyelastix '
                           'looks for the exe in a series of common locations. '
                           'Set ELASTIX_PATH if necessary.')
    

# %% Code for maintaing the temp dirs


def _clear_dir(dirName):
    """ Remove a directory and it contents. Ignore any failures.
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


def get_tempdir():
    """ Get the temporary directory where pyelastix stores its temporary
    files. The directory is specific to the current process and the
    calling thread. Generally, the user does not need this; directories
    are automatically cleaned up. Though Elastix log files are also
    written here.
    """
    tempdir = os.path.join(tempfile.gettempdir(), 'pyelastix')
    
    # Make sure it exists
    if not os.path.isdir(tempdir):
        os.makedirs(tempdir)
    
    # Clean up all directories for which the process no longer exists
    for fname in os.listdir(tempdir):
        dirName = os.path.join(tempdir, fname)
        # Check if is right kind of dir
        if not (os.path.isdir(dirName) and  fname.startswith('id_')):
            continue
        # Get pid and check if its running
        try:
            pid = int(fname.split('_')[1])
        except Exception:
            continue
        if not _is_pid_running(pid):
            _clear_dir(dirName)
    
    # Select dir that included process and thread id
    tid = id(threading.current_thread() if hasattr(threading, 'current_thread')
                                        else threading.currentThread())
    dir = os.path.join(tempdir, 'id_%i_%i' % (os.getpid(), tid))
    if not os.path.isdir(dir):
        os.mkdir(dir)
    return dir


def _clear_temp_dir():
    """ Clear the temporary directory.
    """
    tempdir = get_tempdir()
    for fname in os.listdir(tempdir):
        try:
            os.remove( os.path.join(tempdir, fname) )
        except Exception:
            pass


def _get_image_paths(im1, im2):
    """ If the images are paths to a file, checks whether the file exist
    and return the paths. If the images are numpy arrays, writes them
    to disk and returns the paths of the new files.
    """
    
    paths = []
    for im in [im1, im2]:
        if im is None:
            # Groupwise registration: only one image (ndim+1 dimensions)
            paths.append(paths[0])
            continue
        
        if isinstance(im, str):
            # Given a location
            if os.path.isfile(im1):
                paths.append(im)
            else:
                raise ValueError('Image location does not exist.')
        
        elif isinstance(im, np.ndarray):
            # Given a numpy array
            id = len(paths)+1
            p = _write_image_data(im, id)
            paths.append(p)
        
        else:
            # Given something else ...
            raise ValueError('Invalid input image.')
    
    # Done
    return tuple(paths)


# %% Some helper stuff

def _system3(cmd, verbose=False):
    """ Execute the given command in a subprocess and wait for it to finish.
    A thread is run that prints output of the process if verbose is True.
    """
    
    # Init flag
    interrupted = False
    
    # Create progress
    if verbose > 0:
        progress = Progress()
    
    stdout = []
    def poll_process(p):
        while not interrupted:
            msg = p.stdout.readline().decode()
            if msg:
                stdout.append(msg)
                if 'error' in msg.lower():
                    print(msg.rstrip())
                    if verbose == 1:
                        progress.reset()
                elif verbose > 1:
                    print(msg.rstrip())
                elif verbose == 1:
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
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, 0, pid)
            kernel32.TerminateProcess(handle, 0)
            #os.system("TASKKILL /PID " + str(pid) + " /F")
    
    # All good?
    if interrupted:
        raise RuntimeError('Registration process interrupted by the user.')
    if p.returncode:
        stdout.append(p.stdout.read().decode())
        print(''.join(stdout))
        raise RuntimeError('An error occured during the registration.')


def _get_dtype_maps():
    """ Get dictionaries to map numpy data types to ITK types and the 
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

DTYPE_NP2ITK, DTYPE_ITK2NP = _get_dtype_maps()


class Progress:
    
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
    

# %% The Elastix registration class


def register(im1, im2, params, exact_params=False, verbose=1):
    """ register(im1, im2, params, exact_params=False, verbose=1)
    
    Perform the registration of `im1` to `im2`, using the given 
    parameters. Returns `(im1_deformed, field)`, where `field` is a
    tuple with arrays describing the deformation for each dimension
    (x-y-z order, in world units).
    
    Parameters:
    
    * im1 (ndarray or file location):
        The moving image (the one to deform).
    * im2 (ndarray or file location):
        The static (reference) image.
    * params (dict or Parameters):
        The parameters of the registration. Default parameters can be
        obtained using the `get_default_params()` method. Note that any
        parameter known to Elastix can be added to the parameter
        struct, which enables tuning the registration in great detail.
        See `get_default_params()` and the Elastix docs for more info.
    * exact_params (bool):
        If True, use the exact given parameters. If False (default)
        will process the parameters, checking for incompatible
        parameters, extending values to lists if a value needs to be
        given for each dimension.
    * verbose (int):
        Verbosity level. If 0, will not print any progress. If 1, will
        print the progress only. If 2, will print the full output
        produced by the Elastix executable. Note that error messages
        produced by Elastix will be printed regardless of the verbose
        level.
    """
    
    # Clear dir
    tempdir = get_tempdir()
    _clear_temp_dir()
    
    # Reference image
    refIm = im1
    if isinstance(im1, (tuple,list)):
        refIm = im1[0]
    
    # Check parameters
    if not exact_params:
        params = _compile_params(params, refIm)
    if isinstance(params, Parameters):
        params = params.as_dict()
    
    # Groupwise?
    if im2 is None:
        # todo: also allow using a constraint on the "last dimension"
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
    path_im1, path_im2 = _get_image_paths(im1, im2)
    
    # Determine path of parameter file and write params
    path_params = _write_parameter_file(params)
    
    # Get path of trafo param file
    path_trafo_params = os.path.join(tempdir, 'TransformParameters.0.txt')
    
    # Register
    if True:
        
        # Compile command to execute
        command = [get_elastix_exes()[0],
                   '-m', path_im1, '-f', path_im2, 
                   '-out', tempdir, '-p', path_params]
        if verbose:
            print("Calling Elastix to register images ...")
        _system3(command, verbose)
        
        # Try and load result
        try:
            a = _read_image_data('result.0.mhd')
        except IOError as why:
            tmp = "An error occured during registration: " + str(why)
            raise RuntimeError(tmp)
    
    # Find deformation field
    if True:
        
        # Compile command to execute
        command = [get_elastix_exes()[1],
                   '-def', 'all', '-out', tempdir, '-tp', path_trafo_params]
        _system3(command, verbose)
        
        # Try and load result
        try:
            b = _read_image_data('deformationField.mhd')
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
    
    if im2 is not None:
        fields = fields[0]  # For pairwise reg, return 1 field, not a list
    
    # Clean and return
    _clear_temp_dir()
    return a, fields


def _write_image_data(im, id):
    """ Write a numpy array to disk in the form of a .raw and .mhd file.
    The id is the image sequence number (1 or 2). Returns the path of
    the mhd file.
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
    tempdir = get_tempdir()
    fname_raw_ = 'im%i.raw' % id
    fname_raw = os.path.join(tempdir, fname_raw_)
    fname_mhd = os.path.join(tempdir, 'im%i.mhd' % id)
    
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


def _read_image_data( mhd_file):
    """ Read the resulting image data and return it as a numpy array.
    """
    tempdir = get_tempdir()
    
    # Load description from mhd file
    fname = tempdir + '/' + mhd_file
    des = open(fname, 'r').read()
    
    # Get data filename and load raw data
    match = re.findall('ElementDataFile = (.+?)\n', des)
    fname = tempdir + '/' + match[0]
    data = open(fname, 'rb').read()
    
    # Determine dtype
    match = re.findall('ElementType = (.+?)\n', des)
    dtype_itk = match[0].upper().strip()
    dtype = DTYPE_ITK2NP.get(dtype_itk, None)
    if dtype is None:
        raise RuntimeError('Unknown ElementType: ' + dtype_itk)
    
    # Create numpy array
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
    N = np.prod(shape)
    if N != a.size:
        extraDim = int( a.size / N )
        shape = tuple(shape) + (extraDim,)
        sampling = tuple(sampling) + (1.0,)
        origin = tuple(origin) + (0,)
    
    # Check shape
    N = np.prod(shape)
    if N != a.size:
        raise RuntimeError('Cannot apply shape to data.')
    else:
        a.shape = shape
        a = Image(a)
        a.sampling = sampling
        a.origin = origin
    return a

class Image(np.ndarray):
    
    def __new__(cls, array):
        try:
            ob = array.view(cls)
        except AttributeError:  # pragma: no cover
            # Just return the original; no metadata on the array in Pypy!
            return array
        return ob


# %% Code related to parameters

class Parameters:
    """ Struct object to represent the parameters for the Elastix
    registration toolkit. Sets of parameters can be combined by
    addition. (When adding `p1 + p2`, any parameters present in both
    objects will take the value that the parameter has in `p2`.)
    
    Use `get_default_params()` to get a Parameters struct with sensible
    default values.
    """
    
    def as_dict(self):
        """ Returns the parameters as a dictionary. 
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


def _get_fixed_params(im):
    """ Parameters that the user has no influence on. Mostly chosen
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


def get_advanced_params():
    """ Get `Parameters` struct with parameters that most users do not
    want to think about.
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


def get_default_params(type='BSPLINE'):
    """ get_default_params(type='BSPLINE')
    
    Get `Parameters` struct with parameters that users may want to tweak.
    The given `type` specifies the type of allowed transform, and can
    be 'RIGID', 'AFFINE', 'BSPLINE'.
    
    For detail on what parameters are available and how they should be used,
    we refer to the Elastix documentation. Here is a description of the
    most common parameters:
    
    * Transform (str):
        Can be 'BSplineTransform', 'EulerTransform', or
        'AffineTransform'. The transformation to apply. Chosen based on `type`.
    * FinalGridSpacingInPhysicalUnits (int):
        When using the BSplineTransform, the final spacing of the grid.
        This controls the smoothness of the final deformation.
    * AutomaticScalesEstimation (bool):
        When using a rigid or affine transform. Scales the affine matrix
        elements compared to the translations, to make sure they are in
        the same range. In general, it's best to use automatic scales
        estimation.
    * AutomaticTransformInitialization (bool):
        When using a rigid or affine transform. Automatically guess an
        initial translation by aligning the geometric centers of the 
        fixed and moving.
    * NumberOfResolutions (int):
        Most registration algorithms adopt a multiresolution approach
        to direct the solution towards a global optimum and to speed
        up the process. This parameter specifies the number of scales
        to apply the registration at. (default 4)
    * MaximumNumberOfIterations (int):
        Maximum number of iterations in each resolution level.
        200-2000 works usually fine for nonrigid registration.
        The more, the better, but the longer computation time.
        This is an important parameter! (default 500).
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


def _compile_params(params, im1):
    """ Compile the params dictionary:
    * Combine parameters from different sources
    * Perform checks to prevent non-compatible parameters
    * Extend parameters that need a list with one element per dimension
    """
    
    # Compile parameters
    p = _get_fixed_params(im1) + get_advanced_params()
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


def _write_parameter_file(params):
    """ Write the parameter file in the format that elaxtix likes.
    """
    
    # Get path
    path = os.path.join(get_tempdir(), 'params.txt')
    
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
        elif isinstance(val, str):
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
