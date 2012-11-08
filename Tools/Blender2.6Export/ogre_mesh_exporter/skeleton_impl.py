# ##### BEGIN MIT LICENSE BLOCK #####
# Copyright (C) 2012 by Lih-Hern Pang

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# ##### END MIT LICENSE BLOCK #####

import bpy, mathutils

from ogre_mesh_exporter.log_manager import LogManager, Message

# helper function to convert boolean tuples to integer bitmask
def tupleBoolVectorToIntBitmask(tupleBool):
	result = 0
	for i, bool in enumerate(tupleBool):
		if (bool): result |= (1 << i)
	return result

class Bone():
	def __init__(self, name, pos, rot, parentIndex = -1, invMeshSpaceMatrix = None):
		self.mName = name
		self.mPosition = pos
		self.mRotation = rot
		self.mParentIndex = parentIndex
		self.mInvMeshSpaceMatrix = invMeshSpaceMatrix

class Skeleton():
	def __init__(self, name, armatureObject = None, targetMeshInverseMatrix = mathutils.Matrix.Identity(4), fixUpAxisToY = True):
		# List of bones.
		self.mBones = list()
		self.mName = name

		# Skip blender armature conversion if not set.
		if (armatureObject is None): return

		# build matrix transform to convert from armature space to mesh space.
		# NOTE: Blender matrix multiplication order is World = Parent * Child
		if (fixUpAxisToY): targetMeshInverseMatrix = mathutils.Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1))) * targetMeshInverseMatrix
		self.mArmatureToMeshMatrix = targetMeshInverseMatrix * armatureObject.matrix_world

		# iterate through each bone and initialize our own version.
		# all bones are converted into mesh relative space.
		# The reason for this is to observe situations where Armature is not
		# parent of mesh or mesh position is not at origin relative to Armature.
		# This method ensures that skeletal animation will always work regardless
		# of good/bad mesh<->skeletal setup.
		armature = armatureObject.data

		# get skeleton export settings.
		skeletonSettings = armature.ogre_mesh_exporter
		exportLayerMask = tupleBoolVectorToIntBitmask(skeletonSettings.exportLayerMaskVector) if (skeletonSettings.exportFilter == 'layers') else -1

		# first we convert all bones to mesh space.
		boneMatrixMeshSpaceList = list()
		boneMatrixInvMeshSpaceList = list()
		bBoneList = list()
		for bBone in armature.bones:
			# check that the bone is what we want to export.
			layersBitmask = tupleBoolVectorToIntBitmask(bBone.layers)
			if ((exportLayerMask & layersBitmask) == 0): continue

			matrix = self.mArmatureToMeshMatrix * bBone.matrix_local
			boneMatrixMeshSpaceList.append(matrix)
			boneMatrixInvMeshSpaceList.append(matrix.inverted())
			bBoneList.append(bBone)

		# then we convert bone to new parent space(base on mesh space) and do actual bone creation
		for index, bBone in enumerate(bBoneList):
			# attempt to find the next parent bone that actually gets exported.
			parentBone = bBone.parent
			while (True):
				try:
					parentIndex = bBoneList.index(parentBone)
					matrix = boneMatrixInvMeshSpaceList[parentIndex] * boneMatrixMeshSpaceList[index]
					break
				except ValueError:
					if (parentBone is None):
						parentIndex = -1
						matrix = boneMatrixMeshSpaceList[index]
						break
					parentBone = parentBone.parent

			bone = Bone(bBone.name, matrix.translation, matrix.to_quaternion().normalized(),
				parentIndex, boneMatrixInvMeshSpaceList[index])
			self.mBones.append(bone)

	def getBoneIndex(self, name):
		index = 0
		count = len(self.mBones)
		while (index < count):
			if (self.mBones[index].mName == name):
				return index
			index += 1
		return -1

	def serialize(self, file):
		file.write('<skeleton>\n')

		# write bones.
		file.write('\t<bones>\n')
		for index, bone in enumerate(self.mBones):
			position = tuple(bone.mPosition)
			angle = bone.mRotation.angle
			axis = tuple(bone.mRotation.axis)

			file.write('\t\t<bone id="%d" name="%s">\n' % (index, bone.mName))
			file.write('\t\t\t<position x="%.6f" y="%.6f" z="%.6f" />\n' % position)
			file.write('\t\t\t<rotation angle="%.6f">\n' % angle)
			file.write('\t\t\t\t<axis x="%.6f" y="%.6f" z="%.6f" />\n' % axis)
			file.write('\t\t\t</rotation>\n')
			file.write('\t\t</bone>\n')
		file.write('\t</bones>\n')

		# write bone hierarchies.
		file.write('\t<bonehierarchy>\n')
		for bone in self.mBones:
			if (bone.mParentIndex == -1): continue
			file.write('\t\t<boneparent bone="%s" parent="%s" />\n' %
				(bone.mName, self.mBones[bone.mParentIndex].mName))
		file.write('\t</bonehierarchy>\n')

		file.write('</skeleton>\n')

