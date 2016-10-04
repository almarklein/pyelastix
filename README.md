# pyelastix
Thin wrapper around elastix - a toolbox for rigid and nonrigid registration of images

----

get_advanced_params()

    Get struct with parameters that most users do not want to think about.
    

get_default_params(type='BSPLINE')
    
    Get struct with parameters that users may want to tweak. The given
    ``type`` specifies the type of allowed transform, and can be
    'RIGID', 'AFFINE', 'BSPLINE'.
    

get_elastix_exes()

    Get the executables for elastix and transformix. Raises an error
    if they cannot be found.
    

get_tempdir()

    Get the temporary directory where pyelastix stores its temporary
    files. The directory is specific to the current process and the
    calling thread. Generally, the user does not need this; directories
    are automatically cleaned up. Though Elastix log files are also
    written here.
    

register(im1, im2, params, exact_params=False, verbose=1)
    
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
        extending values to lists if a value needs to be given for each
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
    
    

