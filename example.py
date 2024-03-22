import pyrotlib
import json
import math

com = "COM20"


with pyrotlib.RotationTable(com, verbose=True) as rot:
    print("Connected.")

    ax = rot.getAxisStatus(pyrotlib.AxisName.EL)
    print(ax)
    
    rot.referenceAxis(pyrotlib.AxisName.EL)
    
    rot.moveToAngle(math.pi/2)
    
    print("Done.")
