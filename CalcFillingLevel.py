#!/bin/python3

import numpy as np
import trimesh
from trimesh.voxel import creation
from operator import add
import matplotlib.pyplot as plt
import csv
import os

#
#   Class holding generic tank information
#
class Info:
    #   tank system name (Platin / Carat)
    system = ""

    #   tank name, default to volume
    name = ""

    #   maximal volume in liter
    volume = 0

    #   scale gradient so the final volume matches the official
    #   maximum volume
    scaleToVolume = False

    def __init__(self, system, volume, name=None, scaleToVolume=True):
        self.system = system
        self.scaleToVolume = scaleToVolume
        self.volume = volume
        if name == None:
            self.name = str(volume)
        else:
            self.name = name

    def __str__(self):
        return "sys:{} name:{} volume:{} stv:{};".format(self.system, self.name, self.volume, self.scaleToVolume)

#
#   Class holding all information about one tank
#   possibly consisting of multiple parts (class part)
class TankInfo(Info):
    #   list of used parts when the tank consists of multiple tanks
    #   lists all names as often as used. Example: Platin 10K = ["3750","2500","3750"]
    parts = []

    def __init__(self, system, volume, name=None, scaleToVolume=True, parts=[]):
        self.parts = parts
        Info.__init__(self, system, volume, name, scaleToVolume)

    def __str__(self):
        partString = " ".join([str(a) for a in self.parts])
        return "{} parts:{};".format(Info.__str__(self), partString)

#
#   Part of a graf tank
#   Describes a tank that is only part of a bigger structure
#   This part has its own .stl file
class Part(Info):
    name = ""
    system = ""
    volume = 0
    count = 0

    def __init__(self, volume, system, count=1, name=None, scaleToVolume=True):
        self.count = count
        Info.__init__(self, system, volume, name, scaleToVolume)

    def equals(self, other):
        return (self.name == other.name and self.volume == other.volume and self.system == other.system)

    def __str__(self):
        return "{} cnt:{};".format(Info.__str__(self), self.count)


#
#   Directories
#
OUTPUT = "output"
DATA = "data"


#
#   Collect all tank types with settings
#
#
#
#
#
tanks = []
# Platin
tanks.append(TankInfo("Platin", 1500, scaleToVolume=False))
tanks.append(TankInfo("Platin", 3000, scaleToVolume=False))
tanks.append(TankInfo("Platin", 5000, scaleToVolume=False))
tanks.append(TankInfo("Platin", 7500, scaleToVolume=False))

# Platin XL
tanks.append(TankInfo("PlatinXL", 10000, scaleToVolume=False, parts=[Part(3750,"PlatinXL",2,scaleToVolume=False),Part(2500,"PlatinXL",1)]))
tanks.append(TankInfo("PlatinXL", 15000, scaleToVolume=False, parts=[Part(3750,"PlatinXL",2,scaleToVolume=False),Part(2500,"PlatinXL",3)]))

# Platin XXL
# consist of two parts:
# 3750  = a 3750l tank with access (used at both ends)
# 2500  = a 1500l tank without access (used in the middle)
for i in [20,25,30,35,40,45,50,55,60,65]:
    middleTanks = int((i*1000-2*3750)/2500)
    tanks.append(TankInfo("PlatinXXL", i*1000, scaleToVolume=False, parts=[Part(3750,"PlatinXL",2,scaleToVolume=False),Part(2500,"PlatinXL",middleTanks)]))

# Carat
tanks.append(TankInfo("Carat", 2700, scaleToVolume=True))
tanks.append(TankInfo("Carat", 3750, scaleToVolume=True))
tanks.append(TankInfo("Carat", 4800, scaleToVolume=True))
tanks.append(TankInfo("Carat", 6500, scaleToVolume=True))

# Carat XL
tanks.append(TankInfo("CaratXL", 8500, scaleToVolume=True))
tanks.append(TankInfo("CaratXL", 10000, scaleToVolume=True))

# Carat XXL
# consist of multipe parts
# names are from the revit file
# C   = 10 m^3  # single hole middle part
# A1  = 14 m^3  # start part with small dual hole middle part
# A2  =  8 m^3  # just the half sphere start part
# B   = 18 m^3  # start part with long dual hole middle part
tanks.append(TankInfo("CaratXXL", 16000, scaleToVolume=True))
for i in [22,26,32,36,42,46,52,56,62,66,72,76,82,86,92,96,102,106,112,116,122]:
    parts = [Part(8000,"CaratXXL",1,"A2")]
    end = None
    if (i-8)%10 == 4:
        # add A1
        end = Part(14000,"CaratXXL",1,"A1")
    elif (i-8)%10 == 8:
        # add B1
        end = Part(18000,"CaratXXL",1,"B")
    else:
        print("tank building error")
        exit()

    parts.append(end)
    parts.append(Part(10000,"CaratXXL",(i*1000-end.volume-8000)//10000,"C"))
    tanks.append(TankInfo("CaratXXL", i*1000, scaleToVolume=False, parts=parts))

for tank in tanks:
    print(tank)







#
#   Read the mesh from file system and do small repairs
#   All meshes are not watertight, so normal volume calculation wont work
def readMesh(tank):
    mesh = trimesh.load_mesh(os.path.join(DATA, tank.system, tank.name + ".stl"))
    trimesh.caching.Cache.clear(mesh)
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fill_holes(mesh) # trimesh repair isnt helping
    mesh.remove_duplicate_faces()
    mesh.remove_unreferenced_vertices()
    mesh.remove_infinite_values()
    mesh.rezero()
    # print("Watertight: " + str(mesh.is_watertight))
    # print("Volume: " + str(mesh.is_volume))
    print("Bounds: " + str(mesh.bounds[1]-mesh.bounds[0]))
    return mesh

#
#   Convert the mesh (consisting of triangles) to a voxel matrix
#   Voxels in this matrix are True when cut by a face in the original mesh
def toVoxel(mesh):
    # voxel size in dm
    voxel_size = 0.1
    if any(map(lambda l: l > 1000.0, mesh.bounds[1]-mesh.bounds[0])):
        voxel_size = 10 # voxel size in mm
    if any(map(lambda l: l < 10.0, mesh.bounds[1]-mesh.bounds[0])):
        voxel_size = 0.01 # voxel size in m

    # voxelize
    trimesh.caching.Cache.clear(mesh)
    return trimesh.voxel.creation.voxelize(mesh, voxel_size)

#
#   Puts single plane of voxels on top of the tank to close holes
#   This is needed for the iterative filling algorithm
def closeTop(voxels):
    # copy for to remove reference
    top_closed_mat = np.copy(voxels.matrix)

    # set top voxel True
    top_closed_mat[:,:,top_closed_mat.shape[2]-1] = True

    # create new trimesh
    top_closed = trimesh.voxel.base.VoxelGrid(trimesh.voxel.encoding.DenseEncoding(top_closed_mat))
    print("voxels mit top: " + str(top_closed.filled_count))
    return top_closed

#
#   Set the negativ tank volume (all voxels outside the tank) to False
#   with an iterative algorithm. Returns the filled tank
#   (inside True, outside False)
def fillIter(src):
    dest = np.ones(src.shape, dtype=bool)

    # list with voxels to check
    point_list = [(0,0,0)]

    # do as long there are still unchecked voxels
    while (len(point_list) > 0):
        new_list = []
        for point in point_list:
            # 6 voxel neigborhood
            for relativ in [[0,0,-1],[0,0,1],[0,-1,0],[0,1,0],[-1,0,0],[1,0,0]]:
                # x+1 x-1 y+1 y-1 z+1 z-1
                coord = list(map(add, point, relativ))

                # map index check
                if ((coord[0] >= src.shape[0]) or (coord[0] < 0)): continue
                if ((coord[1] >= src.shape[1]) or (coord[1] < 0)): continue
                if ((coord[2] >= src.shape[2]) or (coord[2] < 0)): continue

                # When src matrix voxel False --> air
                if (src[coord[0]][coord[1]][coord[2]] == False):

                    # set src  matrix voxel True --> last time checked
                    src[coord[0]][coord[1]][coord[2]] = True   # set pixel true to mark

                    # set dest matrix voxel False --> Air
                    dest[coord[0]][coord[1]][coord[2]] = False # set pixel false for negativ
                    new_list.append(coord)

        # new list for next iteration
        point_list = new_list
        #print("list new: " + str(len(new_list)))
    return dest

#
#   Fill tank centimeter by centimeter and log the volume
#
def fillHeight(voxels, tank):
    # volume stepwise
    sum_z = 0
    sumList = []
    zList = []
    for z in range(voxels.matrix.shape[2]):
        # level sum of filled tank
        level_sum = np.sum(voxels.matrix[:,:,z])

        # add to sum  of levels
        sum_z = sum_z + level_sum/1000#*(voxel_size**3)
        sumList.append(int(sum_z))
        #print("lvl: " + str(z) + " sum: " + str(level_sum*(voxel_size**3)))

        # z coordinate scaled to voxel (cm)
        zList.append(z)

    return sumList

#
#   Runs all needed steps to get the volume stepwise at the z axis
#   reads the mesh, translates it to voxel representation, closes the
#   object with planar face, calculates all internal voxels and in the
#   end counts the volume up in z axis centimeter steps
def calcGradient(tank):
    print("CalcGradient for {} {}".format(tank.system, tank.name))

    #
    #    read mesh
    mesh = readMesh(tank)

    #
    #   voxelize mesh
    while True:
        try:
            voxeled = toVoxel(mesh)
            break
        except (RuntimeError, MemoryError, IndexError):
            pass


    mesh = None
    print("original voxels: " + str(voxeled.filled_count))

    #
    #   close top
    closed = closeTop(voxeled)
    voxeled = None

    #
    #   fill tank
    topFilledMat = np.copy(closed.matrix)
    topFilledMat = fillIter(topFilledMat)
    top_filled = trimesh.voxel.base.VoxelGrid(trimesh.voxel.encoding.DenseEncoding(topFilledMat))

    #
    #   remove top
    filledMat = np.copy(top_filled.matrix)
    filledMat[:,:,filledMat.shape[2]-1] = False # remove top z voxels
    filled = trimesh.voxel.base.VoxelGrid(trimesh.voxel.encoding.DenseEncoding(filledMat))
    print("voxels filled: " + str(filled.filled_count))

    curve = fillHeight(filled, tank)
    return curve

#
#   Plot the tank gradient
#   plot 1: fill height / volume
#   plot 2: fill height / volume gradient
def plotGradient(sumList, tank):
    # plot the rising volume over the filling height
    zList = list(range(len(sumList)))
    plt.rcParams["figure.figsize"] = (15,8)
    fig, (ax1, ax2) = plt.subplots(1, 2)
    ax1.set_title("volume")
    ax1.plot(zList, sumList)
    ax1.set_ylabel('volume in liter')
    ax1.set_xlabel('z in cm')
    ax1.hlines(tank.volume, 0, len(sumList)*1.1, label=("volume " + str(tank.volume/1000) + "m^3"), colors=['green'], linestyles=['dashed'])

    # plot the volume gradient over the filling height
    gradient = np.gradient(np.asarray(sumList))
    ax2.set_title("gradient")
    ax2.plot(zList, gradient)
    ax2.set_ylabel('liter/cm')
    ax2.set_xlabel('z in cm')
    title = tank.system + "_" + tank.name
    fig.suptitle(title)
    fig.savefig(os.path.join(OUTPUT, title + '.png'))
    plt.close(fig)


#
#   Scales the given filling curve to the expected tank volume
#   This removes most inaccuracies from not considering the tank
#   material thickness and the low resolution
def scaleCurveToVolume(curve, tank):
    if tank.scaleToVolume:
        factor=tank.volume/float(curve[-1])
        print("factor: " + str(factor) + " oldmax: " + str(curve[-1]))
        curve=list(map(lambda x: int(x*factor), curve))
    return curve


#
#   Main code
#   Runs for all tanks declared at the top. Writes the volume gradient to the
#   "output" csv file. When the tank consists of multiple parts those are summed
#   up to get the volume. All parts are added to the "partCache" to remember
#   already processes parts

if not os.path.exists(OUTPUT):
    os.mkdir(OUTPUT)

rows = []
partCache = []
for tank in tanks:
    # csv row (centimeterwise numbers)
    curve = []

    # when tank consist of parts
    if len(tank.parts) > 0:
        # measure every part
        for part in tank.parts:
            partCurve = None

            # check whether this part was already measured
            for cached in partCache:
                if cached[0].equals(part):
                    partCurve = cached[1]
                    break

            # no cached result
            if partCurve == None:
                partCurve = calcGradient(part)
                partCurve = scaleCurveToVolume(partCurve, part)
                partCache.append((part, partCurve))

            # add to curve
            if curve == []:
                curve = partCurve # init row
                curve = list(map(lambda x: x*part.count, curve))
            else: # add itemwise
                if len(curve) < len(partCurve): curve.extend([curve[-1]]*(len(partCurve)-len(curve)))
                if len(curve) > len(partCurve): partCurve.extend([partCurve[-1]]*(len(curve)-len(partCurve)))
                for i in range(len(curve)):
                    curve[i] = curve[i] + partCurve[i]*part.count
    else:
        # no parts
        curve = calcGradient(tank)

    # correct the function by scaling to the real volume
    curve = scaleCurveToVolume(curve, tank)

    # save plot of the curve
    plotGradient(curve, tank)

    # add to csv collection
    name = tank.system + tank.name
    row = [name]
    row.extend(curve)
    rows.append(row)

# write curves to csv
f = open(os.path.join(OUTPUT, 'output.csv'), 'w')
writer = csv.writer(f)
for row in rows:
    writer.writerow(row)

f.close()
