import math
import serial
import dataclasses
import enum
import json
import time
import traceback

BAUDRATE = 115200
REVERSE_ANGLE_DEG = -15
CMD_OK = "OK"


def enc(dat: str):
    return bytes(dat, encoding='utf-8')


class AxisName(enum.Enum):
    AZ = "AZ"
    EL = "EL"


@dataclasses.dataclass
class Axis:
    StepPin: int
    DirectionPin: int
    HallPin: int
    ReferenceOffset: float

    TotalSteps: int
    MaxDPhiDt: float

    IsInit: bool
    Position: int
    LastStepTime: int

    IsReferenced: bool
    ReferencePosition: int


class RotationTable():

    def __init__(self, COMPORT: str, timeout: float = 5, verbose: bool = False):
        self.com = COMPORT
        self.timeout = timeout
        self.verbose = verbose

    def __enter__(self):

        self.conn = serial.Serial(self.com, BAUDRATE, timeout=self.timeout)

        self.__sendLine(f"test")

        start = time.time()
        while (time.time()-start < self.timeout):
            buf = self.__receiveLine()

            if CMD_OK in buf:
                return self

        raise TimeoutError()

    def __exit__(self, tp, value, tb):

        if self.verbose:
            print("connection closed")

        if tp is not None:
            print(traceback.format_exc())
        self.conn.close()

        return True

    def __sendLine(self, cmd):
        cmd_format = enc(f"{cmd}\n")
        if self.verbose:
            print(">", repr(cmd_format))

        self.conn.write(cmd_format)

    def __receiveLine(self, isTimeout=True):

        if isTimeout:
            start = time.time()

            while (time.time()-start < self.timeout):
                buf = str(self.conn.readline(), encoding="utf-8")
                if len(buf) > 0:
                    break

            if len(buf) == 0:
                raise TimeoutError()
        else:
            buf = str(self.conn.readline(), encoding="utf-8")

        if self.verbose:
            print("<", repr(buf))

        return buf

    def test(self):
        self.__sendLine(f"test")

        return CMD_OK in self.__receiveLine()

    def getAxisStatus(self, ax: AxisName):

        self.__sendLine(f"status {ax.value}")
        return Axis(**json.loads(self.__receiveLine()))

    def readHall(self, ax: AxisName, Nmean: int = 100):
        self.__sendLine(f"readhall {ax.value} {Nmean}")

        return float(self.__receiveLine())

    def steps(self, ax: AxisName, Nsteps: int, isReverse: bool = False, isBlocking=True):

        if Nsteps < 0:
            Nsteps *= -1
            isReverse = True

        self.__sendLine(f"steps {ax.value} {Nsteps} {isReverse}")

        if isBlocking:
            while True:
                if CMD_OK in self.__receiveLine(isTimeout=False):
                    return

    def referenceAxis(self, ax: AxisName, isReverseBeforehand: bool = False, sTimeout: int = 120):
        if isReverseBeforehand:
            axisDat = self.getAxisStatus(ax)

            stepsRev = int(REVERSE_ANGLE_DEG/360.0*axisDat.TotalSteps)

            self.steps(ax, stepsRev)

        self.__sendLine(f"reference {ax.value}")

        if sTimeout > 0:

            start = time.time()
            while (time.time()-start < sTimeout):
                if CMD_OK in self.__receiveLine():
                    return True
            return False

        while True:
            if CMD_OK in self.__receiveLine():
                return True

    def moveTo(self, ax: AxisName, position: int, currentPos: int = None):

        if currentPos is None:
            stat = self.getAxisStatus(ax)

            currentPos = stat.Position

        if self.verbose:
            print(f"current pos {currentPos}, desired position: {position}")

        if position-currentPos == 0:
            return
        self.steps(ax, int(position-currentPos))

    def moveToAngle(self, ax: AxisName, angle: float):
        """
        Moves to a given angular position. Makes sure that there is no revolution
        over the reference position.

        Parameters
        ----------
        ax : AxisName
            The desired Axis.
        angle : float
            The desired angle. In rad.
        """
        axDat = self.getAxisStatus(ax)

        angleN = angle % (2*math.pi)

        if angleN <= math.pi:
            stepDiff = angleN / (2*math.pi) * axDat.TotalSteps
            pos = axDat.ReferencePosition + stepDiff

        else:
            stepDiff = (2*math.pi-angleN) / (2*math.pi) * axDat.TotalSteps
            pos = axDat.ReferencePosition - stepDiff

        if self.verbose:
            print(
                f"Current pos {axDat.Position} Desired position: {pos}",
                f"RefPos: {axDat.ReferencePosition} StepDiff: {stepDiff}")

        self.moveTo(ax, pos)
