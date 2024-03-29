# automatically generated by the FlatBuffers compiler, do not modify

# namespace: gen_events

import flatbuffers
from flatbuffers.compat import import_numpy
np = import_numpy()

class PluginTerminateEvent(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAs(cls, buf, offset=0):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = PluginTerminateEvent()
        x.Init(buf, n + offset)
        return x

    @classmethod
    def GetRootAsPluginTerminateEvent(cls, buf, offset=0):
        """This method is deprecated. Please switch to GetRootAs."""
        return cls.GetRootAs(buf, offset)
    # PluginTerminateEvent
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # PluginTerminateEvent
    def EventCreateTs(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # PluginTerminateEvent
    def TargetPluginName(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # PluginTerminateEvent
    def TargetPluginUuid(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

def PluginTerminateEventStart(builder): builder.StartObject(3)
def Start(builder):
    return PluginTerminateEventStart(builder)
def PluginTerminateEventAddEventCreateTs(builder, eventCreateTs): builder.PrependUOffsetTRelativeSlot(0, flatbuffers.number_types.UOffsetTFlags.py_type(eventCreateTs), 0)
def AddEventCreateTs(builder, eventCreateTs):
    return PluginTerminateEventAddEventCreateTs(builder, eventCreateTs)
def PluginTerminateEventAddTargetPluginName(builder, targetPluginName): builder.PrependUOffsetTRelativeSlot(1, flatbuffers.number_types.UOffsetTFlags.py_type(targetPluginName), 0)
def AddTargetPluginName(builder, targetPluginName):
    return PluginTerminateEventAddTargetPluginName(builder, targetPluginName)
def PluginTerminateEventAddTargetPluginUuid(builder, targetPluginUuid): builder.PrependUOffsetTRelativeSlot(2, flatbuffers.number_types.UOffsetTFlags.py_type(targetPluginUuid), 0)
def AddTargetPluginUuid(builder, targetPluginUuid):
    return PluginTerminateEventAddTargetPluginUuid(builder, targetPluginUuid)
def PluginTerminateEventEnd(builder): return builder.EndObject()
def End(builder):
    return PluginTerminateEventEnd(builder)