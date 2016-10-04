import pyelastix

# To read the image data we use imageio
import imageio

# Pick one lib to visualize the result, matplotlib or visvis
#import visvis as plt
import matplotlib.pyplot as plt


# Read image data
im1 = imageio.imread('chelsea.png')
im2 = imageio.imread('chelsea_morph1.png')
#im2 = imageio.imread('https://dl.dropboxusercontent.com/u/1463853/images/chelsea_morph1.png')

# Select one channel (grayscale), and make float
im1 = im1[:,:,1].astype('float32')
im2 = im2[:,:,1].astype('float32')

# Get default params and adjust
params = pyelastix.get_default_params()
params.NumberOfResolutions = 3
print(params)

# Register!
im3, fields = pyelastix.register(im1, im2, params)
field = fields[0]  # There is one field with pairwise registration.

# Visualize the result
fig = plt.figure(1);
plt.clf()
plt.subplot(231); plt.imshow(im1)
plt.subplot(232); plt.imshow(im2)
plt.subplot(234); plt.imshow(im3)
plt.subplot(235); plt.imshow(field[0])
plt.subplot(236); plt.imshow(field[1])

# Enter mainloop
if hasattr(plt, 'use'):
    plt.use().Run()  # visvis
else:
    plt.show()  # mpl
