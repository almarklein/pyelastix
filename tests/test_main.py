import pytest
import imageio
from skimage import transform, color

import pyelastix


# TODO: add test to check how elastix detection works
# TODO: add test with 3D images
# TODO: add test with series
# TODO: add test with bspline transform


def test_register_affine_gray():
    # Get fixed image
    image_fixed = imageio.imread('imageio:chelsea.png')
    image_fixed = color.rgb2gray(image_fixed)

    # Generate moving image
    image_moving = transform.rotate(image_fixed,
                                    angle=15,
                                    resize=True)

    # Convert both images to float32
    image_fixed = image_fixed.astype('float32')
    image_moving = image_moving.astype('float32')

    # Initialize and adjust the parameters
    params = pyelastix.get_default_params(type='AFFINE')

    params.FixedInternalImagePixelType = "float"
    params.MovingInternalImagePixelType = "float"
    params.ResultImagePixelType = "float"

    params.NumberOfResolutions = 3
    params.MaximumNumberOfIterations = 1000

    # Register
    image_registered, field = pyelastix.register(
        image_moving, image_fixed, params)

    # Check the results
    assert image_registered == pytest.approx(image_fixed, rel=1)
