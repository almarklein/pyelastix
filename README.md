# PyElastix - Python wrapper for the Elastix nonrigid registration toolkit

This Python module wraps the [Elastix](http://elastix.isi.uu.nl/)
registration toolkit. Elastix is a powerful tool, suitable for 2D and 3D
images, capable of rigid as well as non-rigid (i.e. elastic) image
registration.

For an overview of other image registration projects in Python,
see http://pyimreg.github.io.

## Installation

Install this library using `pip install pyelastix` or
`conda install pyelastix -c conda-forge`. This module depends on numpy.

Further, the Elastix command-line application needs to be installed on
your computer. You can obtain a copy at http://elastix.isi.uu.nl/.

This module tries to detect the Elastix executable in a series of common
locations, such as program directories, the user directory, and next to
this module. The executable (or the directory that contains it) can also
be provided by setting the `ELASTIX_PATH` environment variable.

## How it works

This module writes the images to register to disk, calls Elastix to do
the registration, and reads the resulting data. The temporary data is
automatically cleaned up. This approach keeps this module relatively
easy, while providing the full power of the awesome Elastix registration
toolkit.

## Example

```py
# Given im1 and im2 images stored as numpy arrays ...

import pyelastix

# Get params and change a few values
params = pyelastix.get_default_params()
params.MaximumNumberOfIterations = 200
params.FinalGridSpacingInVoxels = 10

# Apply the registration (im1 and im2 can be 2D or 3D)
im1_deformed, field = pyelastix.register(im1, im2, params)
```

See `example.py` for a more complete example.

## API

----

### `Parameters()`

Struct object to represent the parameters for the Elastix
registration toolkit. Sets of parameters can be combined by
addition. (When adding `p1 + p2`, any parameters present in both
objects will take the value that the parameter has in `p2`.)

Use `get_default_params()` to get a Parameters struct with sensible
default values.

### `get_advanced_params()`

Get `Parameters` struct with parameters that most users do not
want to think about.

### `get_default_params(type='BSPLINE')`

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

### `get_elastix_exes()`

Get the executables for elastix and transformix. Raises an error
if they cannot be found.

### `get_tempdir()`

Get the temporary directory where pyelastix stores its temporary
files. The directory is specific to the current process and the
calling thread. Generally, the user does not need this; directories
are automatically cleaned up. Though Elastix log files are also
written here.

### `register(im1, im2, params, exact_params=False, verbose=1)`

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

If `im1` is a list of images, performs a groupwise registration.
In this case the resulting `field` is a list of fields, each
indicating the deformation to the "average" image.
