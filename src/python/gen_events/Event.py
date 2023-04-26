# automatically generated by the FlatBuffers compiler, do not modify

# namespace: gen_events

import flatbuffers
from flatbuffers.compat import import_numpy
np = import_numpy()

class Event(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAs(cls, buf, offset=0):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = Event()
        x.Init(buf, n + offset)
        return x

    @classmethod
    def GetRootAsEvent(cls, buf, offset=0):
        """This method is deprecated. Please switch to GetRootAs."""
        return cls.GetRootAs(buf, offset)
    # Event
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # Event
    def EventType(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Uint8Flags, o + self._tab.Pos)
        return 0

    # Event
    def Event(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            from flatbuffers.table import Table
            obj = Table(bytearray(), 0)
            self._tab.Union(obj, o)
            return obj
        return None

def EventStart(builder): builder.StartObject(2)
def Start(builder):
    return EventStart(builder)
def EventAddEventType(builder, eventType): builder.PrependUint8Slot(0, eventType, 0)
def AddEventType(builder, eventType):
    return EventAddEventType(builder, eventType)
def EventAddEvent(builder, event): builder.PrependUOffsetTRelativeSlot(1, flatbuffers.number_types.UOffsetTFlags.py_type(event), 0)
def AddEvent(builder, event):
    return EventAddEvent(builder, event)
def EventEnd(builder): return builder.EndObject()
def End(builder):
    return EventEnd(builder)