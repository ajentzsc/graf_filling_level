#!/bin/python3

import numpy as np
import trimesh
from trimesh.voxel import creation
from operator import add
import matplotlib.pyplot as plt
import csv

class Info:
    #   tank system name (Platin / Carat)
    system = ""

    #   tank name, default to volume
    name = ""

    #   maximal volume in liter
    volume = 0

    def __init__(self, system, volume, name=None):
        self.system = system
        self.volume = volume
        if name == None:
            self.name = str(volume)
        else:
            self.name = name

#
#   Class holding all information about one tank
#
class TankInfo(Info):
    #   scale gradient so the final volume matches the official
    #   maximum volume
    scaleToVolume = False

    #   list of used parts when the tank consists of multiple tanks
    #   lists all names as often as used. Example: Platin 10K = ["3750","2500","3750"]
    parts = []

    def __init__(self, system, volume, scaleToVolume=False, name=None, parts=[]):
        self.scaleToVolume = scaleToVolume
        self.parts = parts
        Info.__init__(self, system, volume, name)


class Part(Info):
    name = ""
    system = ""
    volume = 0
    count = 0

    def __init__(self, volume, system, count=1, name=None):
        self.count = count
        Info.__init__(self, system, volume, name)

    def equals(self, other):
        return (self.name == other.name and self.volume == other.volume and self.system == other.system)

#
#   Collect all tank types with settings
#
tanks = []
# Platin
tanks.append(TankInfo("Platin", 1500, False))
tanks.append(TankInfo("Platin", 3000, False))
tanks.append(TankInfo("Platin", 5000, False))
tanks.append(TankInfo("Platin", 7500, False))

# Platin XL
tanks.append(TankInfo("PlatinXL", 10000, False, parts=[Part(3750,"PlatinXL",2),Part(2500,"PlatinXL",1)]))
tanks.append(TankInfo("PlatinXL", 15000, False, parts=[Part(3750,"PlatinXL",2),Part(2500,"PlatinXL",3)]))

# Platin XXL
for i in [20,25,30,35,40,45,50,55,60,65]:
    middleTanks = int((i*1000-2*3750)/2500)
    tanks.append(TankInfo("PlatinXXL", i*1000, False, parts=[Part(3750,"PlatinXL",2),Part(2500,"PlatinXL",middleTanks)]))

# Carat
tanks.append(TankInfo("Carat", 2700, True))
tanks.append(TankInfo("Carat", 3750, True))
tanks.append(TankInfo("Carat", 4800, True))
tanks.append(TankInfo("Carat", 6500, True))

# Carat XL
tanks.append(TankInfo("CaratXL", 8500, True))
tanks.append(TankInfo("CaratXL", 10000, True))

# Carat XXL TODO
#   C   = 10 m^3
#   A1  = 14 m^3 (TODO)
#   A2  =  8 m^3 (TODO)
#   B   = 18 m^3 (TODO)
# tanks.append(carat16k = TankInfo("CaratXXL", 16000, True))
# for i in [22,26,32,36,42,46,52,56,62,66,72,76,82,86,92,96,102,106,112,116,122]:
#     tanks.append(TankInfo("PlatinXXL", 20000, False, parts=["3750","2500"*middleTanks,"3750"]))

#
#   Read the mesh from file system and do small repairs
#   All meshes are not watertight, so normal volume calculation wont work
def readMesh(tank):
    mesh = trimesh.load_mesh("data/" + str(tank.system) + "/" + str(tank.name) + ".stl")
    trimesh.caching.Cache.clear(mesh)
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fill_holes(mesh) # trimesh repair isnt helping
    mesh.remove_duplicate_faces()
    mesh.remove_unreferenced_vertices()
    mesh.remove_infinite_values()
    mesh.rezero()
    print(len(trimesh.repair.broken_faces(mesh)))
    print("Watertight: " + str(mesh.is_watertight))
    print("Volume: " + str(mesh.is_volume))
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
    print("starting point: 0,0,0")
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
def fillHeight(voxels, tank, plot):
    # volume stepwise
    sum_z = 0
    sum_list = []
    z_list = []
    for z in range(voxels.matrix.shape[2]):
        # level sum of filled tank
        level_sum = np.sum(voxels.matrix[:,:,z])

        # add to sum  of levels
        sum_z = sum_z + level_sum/1000#*(voxel_size**3)
        sum_list.append(int(sum_z))
        #print("lvl: " + str(z) + " sum: " + str(level_sum*(voxel_size**3)))

        # z coordinate scaled to voxel (cm)
        z_list.append(z)

    if plot:
        plt.rcParams["figure.figsize"] = (12,8)
        plt.plot(z_list, sum_list)
        plt.ylabel('volume')
        plt.xlabel('z')
        plt.vlines(voxels.matrix.shape[2], 0, tank.volume*1.1, label='Oberkante ' + str(voxels.matrix.shape[2]) + "cm", colors=['red'], linestyles=['dashed'])
        plt.hlines(tank.volume, 0, voxels.matrix.shape[2], label=("Volumen " + str(tank.volume/1000) + "m^3"), colors=['green'], linestyles=['dashed'])
        plt.legend()
        plt.show()

        gradient = np.gradient(np.asarray(sum_list))
        plt.plot(z_list, gradient)
        plt.ylabel('liter/cm')
        plt.xlabel('z')
        plt.show()

    return sum_list

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

    curve = fillHeight(filled, tank, False)
    return curve


#
#   Main code
#   Runs for all tanks declared at the top. Writes the volume gradient to the
#   "output" csv file. When the tank consists of multiple parts those are summed
#   up to get the volume. All parts are added to the "partCache" to remember
#   already processes parts
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
                partCache.append((part, partCurve))

            # add to curve
            if curve == []:
                curve = partCurve # init row
                curve = list(map(lambda x: x*part.count, curve))
            else: # add itemwise
                if len(curve) < len(partCurve): curve.extend([0]*(len(partCurve)-len(curve)))
                if len(curve) > len(partCurve): partCurve.extend([0]*(len(curve)-len(partCurve)))
                for i in range(len(curve)):
                    curve[i] = curve[i] + partCurve[i]*part.count
    else:
        # no parts
        curve = calcGradient(tank)


    # add to csv collection
    name = tank.system + tank.name
    row = [name]
    row.extend(curve)
    rows.append(row)

f = open('output', 'w')
writer = csv.writer(f)
for row in rows:
    print("row: " + str(row))
    writer.writerow(row)

f.close()

print("runs!")
