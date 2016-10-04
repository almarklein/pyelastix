import imageio
import visvis as vv

import pyelastix

im1 = imageio.imread('chelsea.png')[:,:,1].astype('float32')
im2 = imageio.imread('chelsea_morph1.png')[:,:,1].astype('float32')
#im2 = imageio.imread('https://dl.dropboxusercontent.com/u/1463853/images/chelsea_morph1.png')

params = pyelastix.get_default_params()
params.MaximumNumberOfIterations = 100
print(params)

im3, fields = pyelastix.register(im1, im2, params)
field = fields[0]  # There is one field with pairwise registration.

fig = vv.figure(1);
vv.clf()
vv.subplot(231); vv.imshow(im1)
vv.subplot(232); vv.imshow(im2)
vv.subplot(234); vv.imshow(im3)
vv.subplot(235); vv.imshow(field[0])
vv.subplot(236); vv.imshow(field[1])

axes = [ac.GetAxes() for ac in fig.children]
for a in axes:
    a.camera = axes[0].camera

vv.use().Run()
