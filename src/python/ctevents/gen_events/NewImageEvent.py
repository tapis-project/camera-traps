# automatically generated by the FlatBuffers compiler, do not modify

# namespace: gen_events

import flatbuffers
from flatbuffers.compat import import_numpy
np = import_numpy()

class NewImageEvent(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAs(cls, buf, offset=0):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = NewImageEvent()
        x.Init(buf, n + offset)
        return x

    @classmethod
    def GetRootAsNewImageEvent(cls, buf, offset=0):
        """This method is deprecated. Please switch to GetRootAs."""
        return cls.GetRootAs(buf, offset)
    # NewImageEvent
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # NewImageEvent
    def EventCreateTs(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # NewImageEvent
    def ImageUuid(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # NewImageEvent
    def ImageFormat(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # NewImageEvent
    def Image(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        if o != 0:
            a = self._tab.Vector(o)
            return self._tab.Get(flatbuffers.number_types.Uint8Flags, a + flatbuffers.number_types.UOffsetTFlags.py_type(j * 1))
        return 0

    # NewImageEvent
    def ImageAsNumpy(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        if o != 0:
            return self._tab.GetVectorAsNumpy(flatbuffers.number_types.Uint8Flags, o)
        return 0

    # NewImageEvent
    def ImageLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0

    # NewImageEvent
    def ImageIsNone(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        return o == 0

def NewImageEventStart(builder): builder.StartObject(4)
def Start(builder):
    return NewImageEventStart(builder)
def NewImageEventAddEventCreateTs(builder, eventCreateTs): builder.PrependUOffsetTRelativeSlot(0, flatbuffers.number_types.UOffsetTFlags.py_type(eventCreateTs), 0)
def AddEventCreateTs(builder, eventCreateTs):
    return NewImageEventAddEventCreateTs(builder, eventCreateTs)
def NewImageEventAddImageUuid(builder, imageUuid): builder.PrependUOffsetTRelativeSlot(1, flatbuffers.number_types.UOffsetTFlags.py_type(imageUuid), 0)
def AddImageUuid(builder, imageUuid):
    return NewImageEventAddImageUuid(builder, imageUuid)
def NewImageEventAddImageFormat(builder, imageFormat): builder.PrependUOffsetTRelativeSlot(2, flatbuffers.number_types.UOffsetTFlags.py_type(imageFormat), 0)
def AddImageFormat(builder, imageFormat):
    return NewImageEventAddImageFormat(builder, imageFormat)
def NewImageEventAddImage(builder, image): builder.PrependUOffsetTRelativeSlot(3, flatbuffers.number_types.UOffsetTFlags.py_type(image), 0)
def AddImage(builder, image):
    return NewImageEventAddImage(builder, image)
def NewImageEventStartImageVector(builder, numElems): return builder.StartVector(1, numElems, 1)
def StartImageVector(builder, numElems):
    return NewImageEventStartImageVector(builder, numElems)
def NewImageEventEnd(builder): return builder.EndObject()
def End(builder):
    return NewImageEventEnd(builder)