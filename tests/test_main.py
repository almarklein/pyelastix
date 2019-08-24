import pytest
import imageio
from skimage import transform
# import matplotlib.pyplot as plt

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
    image_fixed = imageio.imread('imageio:checkerboard.png')

    image_moving = transform.rotate(image_fixed,
                                    angle=30,
                                    resize=True)
    image_moving = transform.rescale(image_moving,
                                     scale=1.5,
                                     mode='constant',
                                     multichannel=True)

    # Select one channel (grayscale), and make float
    image_fixed = image_fixed.astype('float32')
    image_moving = image_moving.astype('float32')

    # Get default params and adjust
    params = pyelastix.get_default_params(type='AFFINE')
    params.NumberOfResolutions = 2
    print(params)

    # Register
    image_registered, field = pyelastix.register(
        image_fixed, image_moving, params)

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
