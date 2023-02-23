# ---
# jupyter:
#   jupytext:
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Movement
#
# You can move, rotate and mirror ComponentReference as well as `Port`, `Polygon`, `ComponentReference`, `Label`, and `Group`

# %% attributes={"classes": [], "id": "", "n": "1"} tags=[]
import gdsfactory as gf

gf.config.rich_output()

PDK = gf.get_generic_pdk()
PDK.activate()

# Start with a blank Component
c = gf.Component("demo_movement")

# Create some more Components with shapes
T = gf.components.text("hello", size=10, layer=(1, 0))
E = gf.components.ellipse(radii=(10, 5), layer=(2, 0))
R = gf.components.rectangle(size=(10, 3), layer=(3, 0))

# Add the shapes to D as references
text = c << T
ellipse = c << E
rect1 = c << R
rect2 = c << R

c

# %% attributes={"classes": [], "id": "", "n": "13"} tags=[]
c = gf.Component("move_one_ellipse")
e1 = c << gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e2 = c << gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e1.movex(10)
c

# %% tags=[]
c = gf.Component("move_one_ellipse_xmin")
e1 = c << gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e2 = c << gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e2.xmin = e1.xmax
c

# %% [markdown]
# Now you can practice move and rotate the objects.

# %% tags=[]
c = gf.Component("two_ellipses_on_top_of_each_other")
E = gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e1 = c << E
e2 = c << E
c

# %% tags=[]
c = gf.Component("ellipse_moved")
e = gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e1 = c << e
e2 = c << e
e2.move(origin=[5, 5], destination=[10, 10])  # Translate by dx = 5, dy = 5
c

# %% tags=[]
c = gf.Component("ellipse_moved_v2")
e = gf.components.ellipse(radii=(10, 5), layer=(2, 0))
e1 = c << e
e2 = c << e
e2.move([5, 5])  # Translate by dx = 5, dy = 5
c

# %% attributes={"classes": [], "id": "", "n": "2"} tags=[]
c = gf.Component("rectangles")
r = gf.components.rectangle(size=(10, 5), layer=(2, 0))
rect1 = c << r
rect2 = c << r

rect1.rotate(45)  # Rotate the first straight by 45 degrees around (0,0)
rect2.rotate(
    -30, center=[1, 1]
)  # Rotate the second straight by -30 degrees around (1,1)
c

# %% tags=[]
c = gf.Component("mirror_demo")
text = c << gf.components.text("hello")
text.mirror(p1=[1, 1], p2=[1, 3])  # Reflects across the line formed by p1 and p2
c

# %% tags=[]
c = gf.Component("hello")
text = c << gf.components.text("hello")
c

# %% [markdown]
# Each Component and ComponentReference object has several properties which can be
# used
# to learn information about the object (for instance where it's center coordinate
# is).  Several of these properties can actually be used to move the geometry by
# assigning them new values.
#
# Available properties are:
#
# - `xmin` / `xmax`: minimum and maximum x-values of all points within the object
# - `ymin` / `ymax`: minimum and maximum y-values of all points within the object
# - `x`: centerpoint between minimum and maximum x-values of all points within the
# object
# - `y`: centerpoint between minimum and maximum y-values of all points within the
# object
# - `bbox`: bounding box (see note below) in format ((xmin,ymin),(xmax,ymax))
# - `center`: center of bounding box

# %% attributes={"classes": [], "id": "", "n": "3"} tags=[]
print("bounding box:")
print(
    text.bbox
)  # Will print the bounding box of text in terms of [(xmin, ymin), (xmax, ymax)]
print("xsize and ysize:")
print(text.xsize)  # Will print the width of text in the x dimension
print(text.ysize)  # Will print the height of text in the y dimension
print("center:")
print(text.center)  # Gives you the center coordinate of its bounding box
print("xmax")
print(text.xmax)  # Gives you the rightmost (+x) edge of the text bounding box

# %% [markdown]
# Let's use these properties to manipulate our shapes to arrange them a little
# better

# %% attributes={"classes": [], "id": "", "n": "4"} tags=[]
c = gf.Component("canvas")
text = c << gf.components.text("hello")
E = gf.components.ellipse(radii=(10, 5), layer=(3, 0))
R = gf.components.rectangle(size=(10, 5), layer=(2, 0))
rect1 = c << R
rect2 = c << R
ellipse = c << E

c

# %% tags=[]
# First let's center the ellipse
ellipse.center = [
    0,
    0,
]  # Move the ellipse such that the bounding box center is at (0,0)

# Next, let's move the text to the left edge of the ellipse
text.y = (
    ellipse.y
)  # Move the text so that its y-center is equal to the y-center of the ellipse
text.xmax = ellipse.xmin  # Moves the ellipse so its xmax == the ellipse's xmin

# Align the right edge of the rectangles with the x=0 axis
rect1.xmax = 0
rect2.xmax = 0

# Move the rectangles above and below the ellipse
rect1.ymin = ellipse.ymax + 5
rect2.ymax = ellipse.ymin - 5

c

# %% [markdown]
# In addition to working with the properties of the references inside the
# Component,
# we can also manipulate the whole Component if we want.  Let's try mirroring the
# whole Component `D`:

# %% attributes={"classes": [], "id": "", "n": "5"} tags=[]
print(c.xmax)  # Prints out '10.0'

c2 = c.mirror((0, 1))  # Mirror across line made by (0,0) and (0,1)
c2

# %% [markdown]
# A bounding box is the smallest enclosing box which contains all points of the geometry.

# %% tags=[]
c = gf.Component("hi_bbox")
text = c << gf.components.text("hi")
bbox = text.bbox
c << gf.components.bbox(bbox=bbox, layer=(2, 0))
c

# %% attributes={"classes": [], "id": "", "n": "6"} tags=[]
# gf.get_padding_points can also add a bbox with respect to the bounding box edges
c = gf.Component("sample_padding")
text = c << gf.components.text("bye")
device_bbox = text.bbox
c.add_polygon(gf.get_padding_points(text, default=1), layer=(2, 0))
c

# %% [markdown]
# When we query the properties of D, they will be calculated with respect to this
# bounding-rectangle.  For instance:

# %% attributes={"classes": [], "id": "", "n": "7"} tags=[]
print("Center of Component c:")
print(c.center)

print("X-max of Component c:")
print(c.xmax)

# %% tags=[]
D = gf.Component("rect")
R = gf.components.rectangle(size=(10, 3), layer=(2, 0))
rect1 = D << R
D

# %% [markdown]
# You can chain many of the movement/manipulation functions because they all return the object they manipulate.
#
# For instance you can combine two expressions:

# %% attributes={"classes": [], "id": "", "n": "8"} tags=[]
rect1.rotate(angle=37)
rect1.move([10, 20])
D

# %% [markdown]
# ...into this single-line expression

# %% attributes={"classes": [], "id": "", "n": "9"} tags=[]
D = gf.Component("single_expression")
R = gf.components.rectangle(size=(10, 3), layer=(2, 0))
rect1 = D << R
rect1.rotate(angle=37).move([10, 20])
D
