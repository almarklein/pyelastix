import pytest
import imageio
from skimage import transform, color, util
import matplotlib.pyplot as plt

import pyelastix


# @pytest.fixture
# def image_fixed():
#     pass
#
#
# @pytest.fixture
# def image_moving():
#     pass


def test_register_affine_gray():
    image_fixed = imageio.imread('imageio:chelsea.png')
    image_fixed = color.rgb2gray(image_fixed)

    image_moving = transform.rotate(image_fixed,
                                    angle=15,
                                    resize=True)

    image_fixed = util.img_as_ubyte(image_fixed)
    image_moving = util.img_as_ubyte(image_moving)

    # image_moving = transform.rescale(image_moving,
    #                                  scale=1.5,
    #                                  mode='constant',
    #                                  multichannel=False)

    # Select one channel (grayscale), and make float
    image_fixed = image_fixed.astype('float32')
    image_moving = image_moving.astype('float32')

    # Get default params and adjust
    params = pyelastix.get_default_params(type='AFFINE')

    params.FixedInternalImagePixelType = "float"
    params.MovingInternalImagePixelType = "float"
    params.ResultImagePixelType = "float"

    # params.Transform = "AffineTransform"
    # params.HowToCombineTransforms = "Compose"
    # params.AutomaticTransformInitialization = "true"
    # params.AutomaticScalesEstimation = "true"

    # params.Registration = "MultiResolutionRegistration"
    # params.FixedImagePyramid = "FixedRecursiveImagePyramid"
    # params.MovingImagePyramid = "MovingRecursiveImagePyramid"

    params.NumberOfResolutions = 2
    params.MaximumNumberOfIterations = 500

    # params.ImageSampler = "RandomCoordinate"
    # params.FixedImageBSplineInterpolationOrder = 1
    # params.UseRandomSampleRegion = "false"
    # params.NumberOfSpatialSamples = 1024
    # params.NewSamplesEveryIteration = "true"
    # params.CheckNumberOfSamples = "true"
    # params.MaximumNumberOfSamplingAttempts = 10
    #
    # params.Metric = "AdvancedNormalizedCorrelation"

    print(params)

    # Register
    image_registered, field = pyelastix.register(
        image_moving, image_fixed, params)
        # image_fixed, image_moving, params)

    # TODO: finalize
    assert 1 == 1

    # Visualize the result
    # fig, axes = plt.subplots(2, 3)
    # axes = axes.ravel()
    # axes[0].imshow(image_fixed)
    # axes[1].imshow(image_moving)
    # axes[2].imshow(image_registered)
    # axes[3].imshow(field[0])
    # axes[4].imshow(field[1])
    #
    # plt.show()
