import logging

import numpy as np
from ophyd import Component as Cpt
from ophyd.signal import EpicsSignal
from prettytable import PrettyTable

from pcdsdevices.epics_motor import IMS

from .device import GroupDevice
from .interface import BaseInterface

logger = logging.getLogger(__name__)


alpha_r = 63 * np.pi/180  # rail angle 90-27 degrees
r = 2960.0  # first rail distance from the sample at the gon interaction point to the rail rod at 27deg
R = 6735.0 #second rail distance from the sample at the gon interaction point to the rail rod at 27 degrees
alpha_cos = np.cos(27 * np.pi/180) #variable to claculate the distance when the IP is shifted along the beam direction


def ThetaToMotors(theta, samz_offset=0):
    """
    Calculates lengths x1, x2, and dz from theta. Theta is the angle in radians of the LADM relative to the beamline.
    x1 is the position of the first (shorter) rail, and x2 is the position of the second (longer) rail. 
    dz is the relative position.
    """
    theta = theta * np.pi/180  # change to radian
    x1 = (r) * np.sin(theta)/(np.sin(alpha_r) * np.sin(alpha_r+theta))
    x2 = (R) * np.sin(theta)/(np.sin(alpha_r) * np.sin(alpha_r+theta))
    dz = (r)/np.sin(alpha_r)-x1 * np.sin(alpha_r)/np.sin(theta)
    if theta == 0:
        dz = 0
    return x1, x2, dz


def y1ToGamma(y1):
    """
    Calculates the vertical angle gamma=arctan(y1/r) in radians, the angle measured with 0 perpendicular to the beamline.
    y1 is the y position of the first (shorter) rail. 
    """
    gamma = np.arctan((y1)/(r))
    gamma = gamma * 180/np.pi
    return gamma


def y2ToGamma(y2):
    """
    Calculates the vertical angle gamma=arctan(y2/r) in radians, the angle measured with 0 perpendicular to the beamline.
    y2 is the y position of the second (longer) rail. 
    """
    gamma = np.arctan((y2)/(R))
    gamma = gamma * 180/np.pi
    return gamma


def GammaToMotors(gamma):
    """
    Calculates the y positions of the first and second rails, 'y1' and 'y2', and their difference 'dy'
    """
    gamma = gamma * np.pi/180
    y1 = (r) * np.tan(gamma)
    y2 = (R) * np.tan(gamma)
    dy = y2 - y1
    return y1, y2, dy


def x1ToTheta(x1, samz_offset=0):
    """
    Calculates angle theta in radians using rail position x1 and samz_offset
    """
    theta = np.arctan(x1 * (np.sin(alpha_r))**2 /
                      (r-samz_offset * alpha_cos-x1 * np.sin(2 * alpha_r)/2))
    theta = theta * 180/np.pi
    return theta


def x2ToTheta(x2, samz_offset=0):
    """
    Calculates angle theta in radians using rail position x2 and samz_offset
    """
    theta = np.arctan(x2 * (np.sin(alpha_r))**2 /
                      (R-samz_offset * alpha_cos-x2 * np.sin(2 * alpha_r)/2))
    theta = theta * 180/np.pi
    return theta


def xTox12(x):
    """
    Calculates 'x12' , the distance between rails 1 and 2 using 'x' and the reference rail angle alpha_r (27 degrees)
    """
    x12 = x/np.sin(alpha_r)
    return x12


def xToz(x):
    """
    Calculates the rail reference position 'z' from 'x' position when the rail is at the reference angle alpha_r (27 degrees)
    """
    z = x/np.tan(alpha_r)
    return z


def MotorsTox(x1, x2, z):
    """
    Calculates x_x1, x_x2, and x_z from x1, x2, and z trigonomic relationships with rail angle alpha_r
    """
    x_x1 = x1 * np.sin(alpha_r)
    x_x2 = x2 * np.sin(alpha_r)
    x_z = z * np.tan(alpha_r)
    return x_x1, x_x2, x_z


def ThetaToMotors_print(theta):
    """
    Prints locations x1 (rail 1), x2 (rail 2), and z are moving to
    """
    x1, x2, z = ThetaToMotors(theta)
    print(f"Move x1 to {x1}"
          f"Move x2 to {x2}"
          f"Move z to {z}"
          )


class LADM(BaseInterface, GroupDevice):
    """
    Class to control the LADM. Includes Single motors and beamstops.
    
    The LADM is the Large Angle Detector Mover in XCS.
    It's the large device that sweeps across the instrument's floor in a wide angle, and moves along 2 linear rails.
    It can be used to position and reposition a detector at various angles relative
    to the sample position. The reference position to define rail distances is when the LADM is at 27 degrees, 
    where 0 degrees is when the LADM is positioned parallel to the beamline. 
    See the LADM Confluence page for diagrams and details: 
    #https://confluence.slac.stanford.edu/spaces/XCS/pages/288031127/2.13+Large+Angle+Detector+Mover+LADM

    Parameters
    ----------
    prefix : str
        Base PV for the LADM

    name : str
        Alias for the device
    """

    # Motors
    x1 = Cpt(IMS, ':MMS:01', name="x1", kind='normal',
             doc='X1 Upstream')
    x2 = Cpt(IMS, ':MMS:04', name="x2", kind='normal',
             doc='X2 Downstream')
    y1 = Cpt(IMS, ':MMS:03', name="y1", kind='normal',
             doc='Y1 Upstream')
    y2 = Cpt(IMS, ':MMS:05', name="y2", kind='normal',
             doc='Y2 Downstream')
    z = Cpt(IMS, ':MMS:02', name="z", kind='normal',
            doc='Z Upstream')
    bs6_r = Cpt(IMS, ':MMS:12', name="bs6_r", kind='normal',
                doc='Beam Stop In Out 1')
    bs6_t = Cpt(IMS, ':MMS:11', name="bs6_t", kind='normal',
                doc='Beam Stop Trans 1')
    bs2_r = Cpt(IMS, ':MMS:13', name="bs2_r", kind='normal',
                doc='Beam Stop In Out 2')
    bs2_t = Cpt(IMS, ':MMS:14', name="bs2_t", kind='normal',
                doc='Beam Stop Trans 2')
    bs10_r = Cpt(IMS, ':MMS:15', name="bs10_r", kind='normal',
                 doc='Beam Stop In Out 3')
    bs10_t = Cpt(IMS, ':MMS:16', name="bs10_t", kind='normal',
                 doc='Beam Stop Trans 2')
    det_x = Cpt(IMS, ':MMS:06', name="det_x", kind='normal',
                doc='Detector Motor x')
    det_y = Cpt(IMS, ':MMS:07', name="det_y", kind='normal',
                doc='Detector Motor y')

    theta_pv = EpicsSignal('XCS:VARS:LAM:Theta', name='LADM_theta')
    gamma_pv = EpicsSignal('XCS:VARS:LAM:Gamma', name='LADM_gamma')

    tab_component_names = True
    tab_whitelist = ['status', 'ThetaToMotors_print',
                     'moveTheta', 'waitAll', 'wmTheta',
                     'wmGamma', 'mvrGamma', 'setTheta',
                     'moveX', 'tweakH', 'mvrV', 'wmX',
                     'ca_theta', 'stop'
                     ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.theta = None  # VirtualMotor
        self.XT = None  # VirtualMotor
        self.gamma = None
        self.__lowlimX = None
        self.__hilimX = None

    def __theta_movement(self, theta, samz_offset=0):
        x1_var, x2_var, z_var = ThetaToMotors(theta, samz_offset)
        z_now = self.z.wm()
        try:
            if z_now < z_var:
                print(f"Moving z to {z_var}")
                self.z.mv(z_var)
                self.z.wait()
                print("Done")
                print(f"Moving x1 to {x1_var} and x2 to {x2_var}")
                self.x1.mv(x1_var)
                self.x2.mv(x2_var)
                self.waitAll()
                print("Done")
            else:
                print(f"Moving x1 to {x1_var} and x2 to {x2_var}")
                self.x1.mv(x1_var)
                self.x2.mv(x2_var)
                self.x1.wait()
                self.x2.wait()
                print(f"moving z to {z_var}")
                self.z.mv(z_var)
                self.waitAll()
                print("Done")
        except KeyboardInterrupt:
            self.stop()
        finally:
            self.theta_pv.put(self.wmTheta())

    def status(self):
        motors = {"x1": self.x1,
                  "y1": self.y1,
                  "x2": self.x2,
                  "y2": self.y2,
                  "z": self.z
                  }
        table = PrettyTable()
        table.field_names = ["Motor", "User", "Dial"]
        table.add_row(["Theta", self.theta.position, "-"])
        table.add_row(["XT", self.XT.position, "-"])
        for key, value in motors.items():
            m = motors[key]
            table.add_row([key, m.wm(), m.dial_position.get()])
        print(table.get_string(title="LADM Status"))

    def ThetaToMotors_print(self, theta):
        x1_var, x2_var, z_var = ThetaToMotors(theta)
        message = (f"""
                   Move x1 to {x1_var}.
                   Move x2 to {x2_var}.
                   Move z to {z_var}.
                   """
                   )
        print(message)

    def moveTheta(self, theta, samz_offset=0):
        print(self.theta.position())
        theta_now = self.theta.position()
        if theta_now is np.nan:
            theta1 = x1ToTheta(self.x1.wm(), samz_offset)
            theta2 = x2ToTheta(self.x2.wm(), samz_offset)
            x1_th1, x2_th1, z_th1 = ThetaToMotors(theta1)
            x1_th2, x2_th2, z_th2 = ThetaToMotors(theta2)
            message = (f"""
                       theta(x1) = {theta1}.
                       Should move x2 to {x2_th1}.
                       Should move z to {z_th1}.
                       theta(x2)= {theta2}.
                       Should move x1 to {x1_th2}.
                       Should move z to {z_th2}
                       """
                       )
            return message

        else:
            if abs(theta-theta_now) <= 28:
                self.__theta_movement(theta, samz_offset)
            else:
                theta_1 = (theta + theta_now)/2
                self.__theta_movement(theta_1, samz_offset)
                self.theta.wait()
                self.__theta_movement(theta, samz_offset)
        self.status()

    def waitAll(self):
        self.z.wait()
        self.x1.wait()
        self.x2.wait()

    def wmTheta(self, samz_offset=0):
        theta1 = x1ToTheta(self.x1.wm(), samz_offset)
        theta2 = x2ToTheta(self.x2.wm(), samz_offset)
        tolerance = 0.01
        if samz_offset > 0:
            thetar = np.arctan((self.x2.wm() - self.x1.wm())/(R-r))
            theta = thetar * 180/np.pi
            ca_samz_offset = -((self.x1.wm() * (np.sin(alpha_r))**2 /
                                np.tan(thetar)) - r + self.x1.wm() *
                               np.sin(2*alpha_r)/2)/alpha_cos
            message = (f"""
                       {theta1}(by x1)/theta2(by x2)/sample z at {samz_offset}
                       or
                       theta {theta} at sample z offset {ca_samz_offset}
                        """)
            print(message)
            return theta1, theta2, samz_offset, ca_samz_offset
        elif abs(theta1 - theta2) < tolerance:
            return theta1
        else:
            return np.nan

    def wmGamma(self):
        gamma1 = y1ToGamma(self.y1.wm())
        gamma2 = y1ToGamma(self.y2.wm())
        gamma = gamma2-gamma1
        message = f"gamma = {gamma}(y1 = {self.y1.wm()}/y2 = {self.y2.wm()})"
        print(message)
        return gamma, message

    def mvrGamma(self, theta, wait=False):
        y1_var, y2_var, dy = GammaToMotors(theta)
        # gamma1 = y1ToGamma(self.y1.wm())
        # gamma2 = y1ToGamma(self.y2.wm())
        self.y1.mvr(y1_var, wait=wait)
        self.y2.mvr(y2_var, wait=wait)

    def setTheta(self, value):
        """ set x1, x2 and  z for Theta value """
        x1_var, x2_var, z_var = ThetaToMotors(value)
        self.x1.set(x1_var)
        self.x2.set(x2_var)
        self.z.set(z_var)

    def moveX(self, x):
        """
        whole ladm move horizontally and keep same Z distance from diff
        """
        if ((x <= self.__lowlimX) or (x >= self.__hilimX)):
            logger.debug(f"""Asked to move {self.XT.name}
                           outside limit, aborting""")
        else:
            try:
                x1_var = xTox12(x)
                x2_var = x1_var
                z_var = xToz(x)
                z_now = self.z.wm()
                if z_var > z_now:
                    print(f"Moving z to o {z_var}")
                    self.z.mv(z_var)
                    self.z.wait()
                    print(f"Moving x1 to {x1_var} and x2 to {x2_var}")
                    self.x1.mv(x1_var)
                    self.x2.mv(x2_var)
                else:
                    print(f"Moving x1 to {x1_var} and x2 to {x2_var}")
                    self.x1.mv(x1_var)
                    self.x2.mv(x2_var)
                    self.x1.wait()
                    self.x2.wait()
                    print(f"Moving z to {z_var}")
            except KeyboardInterrupt:
                self.stop()

    def tweakH(self, x):
        """
        whole ladm move horizontally and keep same Z distance from diff
        """
        try:
            x1_var = xTox12(x)
            x2_var = xTox12(x)
            z_var = xToz(x)
            z_now = self.z.wm()
            if z_var > z_now:
                print(f"Moving z to {z_var}")
                self.z.mvr(z_var - z_now)
                self.z.wait()
                print("Done")
                print(f"Moving x1 to {x1_var} and x2 to {x2_var}")
                self.x1.mvr(x1_var)
                self.x2.mvr(x2_var)
                print("Done")
            else:
                print(f"Moving x1 to {x1_var} and x2 to {x2_var}")
                self.x1.mvr(x1_var)
                self.x2.mvr(x2_var)
                self.x1.wait()
                self.x2.wait()
                print("Done")
                print(f"Moving z to {z_var}")
                self.z.mvr(z_var - z_now)
                print("Done")
        except KeyboardInterrupt:
            self.stop()

    def mvrV(self, y):
        """ ladm move vertically  """
        try:
            self.y1.mvr(y)
            self.y2.mvr(y)
        except KeyboardInterrupt:
            self.stop()

    def wmX(self):
        x1_var = self.x1.wm()
        x2_var = self.x2.wm()
        z_var = self.z.wm()
        x_x1, x_x2, x_z = MotorsTox(x1_var, x2_var, z_var)
        db_x1 = EpicsSignal(self.x1.prefix+'.RDBD', name='db_x1').get()
        db_x2 = EpicsSignal(self.x2.prefix+'.RDBD', name='db_x2').get()
        tolerance = db_x1 + db_x2
        if (abs(x_x1 - x_x2) <= tolerance):
            z_theo = xToz(x_x1)
            db_z = EpicsSignal(self.z.prefix+'.RDBD', name='db_z').get()
            if abs(z_var - z_theo) < 2 * db_z:
                return x_x1
            else:
                return np.nan
        else:
            return np.nan

    def ca_theta(self, cal_theta, samz_offset=0):
        """
        calculation relative x and z postion at certain theta
        ca_theta(theta,samz_offset(downstream offset / mm))
        """
        cal_thetarad = cal_theta * np.pi/180
        cal_x1 = ((r - samz_offset * alpha_cos) *
                  np.sin(cal_thetarad) / (np.sin(alpha_r) *
                  np.sin(alpha_r + cal_thetarad)))
        cal_x2 = ((R - samz_offset * alpha_cos) *
                  np.sin(cal_thetarad)/(np.sin(alpha_r) *
                  np.sin(alpha_r + cal_thetarad)))
        cal_dz = ((r - samz_offset * alpha_cos) /
                  np.sin(alpha_r) - cal_x1 *
                  np.sin(alpha_r)/np.sin(cal_thetarad))
        caTable = PrettyTable()
        caTable.field_names = ["Theta", "x1", "x2", "delta z",
                               "sample z offset"]
        caTable.add_row([cal_theta, cal_x1, cal_x2, cal_dz, samz_offset])
        print(caTable)
        return cal_theta, cal_x1, cal_x2, cal_dz, samz_offset

    def _setX(self, value):
        x1_var = xTox12(value)
        x2_var = xTox12(value)
        z_var = xToz(value)
        self.x1.set(x1_var)
        self.x2.set(x2_var)
        self.z.set(z_var)

    def _set_lowlimX(self, value):
        self.__lowlimX = value

    def _set_hilimX(self, value):
        self.__hilimX = value

    def _get_lowlimX(self):
        return self.__lowlimX

    def _get_hilimX(self):
        return self.__hilimX

    def stop(self):
        self.x1.stop()
        self.x2.stop()
        self.y1.stop()
        self.y2.stop()
        self.z.stop()

    def __call__(self):
        self.status()
