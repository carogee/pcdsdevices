#from lightpath import LightpathState
from ophyd.device import Component as Cpt
from ophyd.device import FormattedComponent as FCpt

from .analog_signals import FDQ
from .device import GroupDevice
from .device import UpdateComponent as UpCpt
from .epics_motor import (IMS, BeckhoffAxis, BeckhoffAxisNoOffset,
                          EpicsMotorInterface)

import enum
import logging
import time
import typing
from collections import namedtuple

import numpy as np
from ophyd.device import Device
from ophyd.device import FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd.status import MoveStatus

from .beam_stats import BeamEnergyRequest
from .epics_motor import IMS, EpicsMotorInterface
from .interface import BaseInterface, FltMvInterface#, LightpathMixin
from .pseudopos import (PseudoPositioner, PseudoSingleInterface, SyncAxis,
                        SyncAxisOffsetMode)
from .pv_positioner import PVPositionerIsClose
from .signal import InternalSignal
from .utils import doc_format_decorator, get_status_float

logger = logging.getLogger(__name__)

# Constants
si_111_dspacing = 3.1356011499587773

# Defaults
default_dspacing = si_111_dspacing


class DCCMEnergy(FltMvInterface, PseudoPositioner):
    """
    DCCM energy motor.

    Calculates the current DCCM energy using the DCCM angle, and
    requests moves to the DCCM motors based on energy requests.

    Presents itself like a motor.

    Parameters
    ----------
    prefix : str
        The PV prefix of the DCCM motor, e.g. XPP:MON:MPZ:07A
    """
    # Pseudo motor and real motor
    energy = Cpt(
        PseudoSingleInterface,
        egu='keV',
        kind='hinted',
        limits=(4, 25),
        verbose_name='DCCM Photon Energy',
        doc=(
            'PseudoSingle that moves the calculated DCCM '
            'selected energy in keV.'
        ),
    )

    th1 = Cpt(BeckhoffAxis, "SP1L0:DCCM:MMS:TH1", doc="Bragg Upstream/TH1 Axis", kind="normal", name='th1')


    tab_component_names = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def forward(self, pseudo_pos: namedtuple) -> namedtuple:
        """
        PseudoPositioner interface function for calculating the setpoint.

        Converts the requested energy to theta 1 and theta 2 (Bragg angle).
        """
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        energy = pseudo_pos.energy
        theta = self.energyToSi111BraggAngle(energy)
        return self.RealPosition(theta=th1)

    def inverse(self, real_pos: namedtuple) -> namedtuple:
        """
        PseudoPositioner interface function for calculating the readback.

        Converts the real position of the DCCM theta motor to the calculated energy.
        """
        real_pos = self.RealPosition(*real_pos)
        theta = real_pos.th1
        energy = self.thetaToSi111energy(th1)
        return self.PseudoPosition(energy=energy)

    def energyToSi111BraggAngle(self, energy: float) -> float:
        """
        Converts energy to Bragg angle theta

        Parameters                                                                                                                                             
        ----------                                                                                                                                              
        energy : float                                                                                                                                          
            The photon energy (color) in keV.

        Returns
        ---------
        Bragg angle: float
            The angle in degrees
        """
        dspacing = 3.13560114
        bragg_angle = np.rad2deg(np.arcsin(12398.419/energy/(2*dspacing)))
        return bragg_angle

    def thetaToSi111energy(self, theta):
        """
        Converts dccm theta angle to energy.

        Parameters                                                                                                                                              
        ----------                                                                                                                                              
        energy : float
            The Bragg angle theta in degrees

        Returns:
        ----------
        energy: float
             The photon energy (color) in keV.
        """
        dspacing = 3.13560114
        energy = 12398.419/(2*dspacing*np.sin(np.deg2rad(theta)))
        return energy


class DCCMEnergyAcr(DCCMEnergy):                                                                                                                                                        
    """
    DCCM energy motor and the ACR beam energy request.

    Moves theta based on the requested energy using the values
    of the calculation constants, and reports the current energy
    based on the DCCM theta motor position.

    Also moves the ACR beam energy when a move is requested to the theta angle.
    Note that the vernier is in units of eV, while the energy
    calculations are in units of keV.

    Parameters
    ----------
    prefix : str
        The PV prefix of the DCCM motor, e.g. XPP:MON:MPZ:07A
    hutch : str, optional
        The hutch we're in. This informs us as to which vernier                                                                                                                         
        PVs to write to. If omitted, we can guess this from the                                                                                                                         
        prefix.                                                                                                                                                                         
    """                                                                                                                                                                                 
    acr_energy = FCpt(BeamEnergyRequest, '{hutch}', kind='normal',                                                                                                                      
                      doc='Requests ACR to move the Vernier.')                                                                                                                          
                                                                                                                                                                                        
    # These are duplicate warnings with main energy motor                                                                                                                               
    _enable_warn_constants: bool = False                                                                                                                                                
    hutch: str                                                                                                                                                                          
                                                                                                                                                                                        
    def __init__(                                                                                                                                                                       
        self,                                                                                                                                                                           
        prefix: str,                                                                                                                                                                    
        hutch: typing.Optional[str] = None,                                                                                                                                             
        **kwargs                                                                                                                                                                        
    ):                                                                                                                                                                                  
        # Put some effort into filling this automatically                                                                                                                               
        # CCM exists only in two hutches                                                                                                                                                
        if hutch is not None:                                                                                                                                                           
            self.hutch = hutch                                                                                                                                                          
        elif 'XPP' in prefix:                                                                                                                                                           
            self.hutch = 'XPP'                                                                                                                                                          
        elif 'XCS' in prefix:                                                                                                                                                           
            self.hutch = 'XCS'                                                                                                                                                          
        else:                                                                                                                                                                           
            self.hutch = 'TST'                                                                                                                                                          
        super().__init__(prefix, **kwargs)

    def forward(self, pseudo_pos: namedtuple) -> namedtuple:
        """                                                                                                                                                                                   
        PseudoPositioner interface function for calculating the setpoint.                                                                                                                     
                                                                                                                                                                                              
        Converts the requested energy to theta 1 and theta 2 (Bragg angle).                                                                                                                   
        """
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        energy = pseudo_pos.energy
        theta = self.energyToSi111BraggAngle(energy)
        return self.RealPosition(theta=th1)

    def inverse(self, real_pos: namedtuple) -> namedtuple:
        """                                                                                                                                                                                   
        PseudoPositioner interface function for calculating the readback.                                                                                                                     
                                                                                                                                                                                              
        Converts the real position of the DCCM theta motor to the calculated energy.                                                                                                          
        """
        real_pos = self.RealPosition(*real_pos)
        theta = real_pos.th1
        energy = self.thetaToSi111energy(th1)
        return self.PseudoPosition(energy=energy)


class DCCMEnergyWithACRStatus(DCCMEnergyWithVernier):                                                                                                                                   
    """                                                                                                                                                                                 
    CCM energy motor and ACR beam energy request with status.                                                                                                                           
    Note that in this case vernier indicates any ways that ACR will act on the                                                                                                          
    photon energy request. This includes the Vernier, but can also lead to                                                                                                              
    motion of the undulators or the K.                                                                                                                                                  
                                                                                                                                                                                        
    Parameters                                                                                                                                                                          
    ----------                                                                                                                                                                          
    prefix : str                                                                                                                                                                        
        The PV prefix of the Alio motor, e.g. XPP:MON:MPZ:07A                                                                                                                           
    hutch : str, optional                                                                                                                                                               
        The hutch we're in. This informs us as to which vernier
        PVs to write to. If omitted, we can guess this from the
        prefix.
    acr_status_sufix : str
        Prefix to the SIOC PV that ACR uses to report the move status.
        For HXR this usually is 'AO805'.
    """                                                                                                                                                                                 
    acr_energy = FCpt(BeamEnergyRequest, '{hutch}',                                                                                                                                     
                      pv_index='{pv_index}',                                                                                                                                            
                      acr_status_suffix='{acr_status_suffix}',                                                                                                                          
                      add_prefix=('suffix', 'write_pv', 'pv_index',                                                                                                                     
                                  'acr_status_suffix'),                                                                                                                                 
                      kind='normal',                                                                                                                                                    
                      doc='Requests ACR to move the energy.')                                                                                                                           
                                                                                                                                                                                        
    def __init__(                                                                                                                                                                       
        self,                                                                                                                                                                           
        prefix: str,                                                                                                                                                                    
        hutch: typing.Optional[str] = None,                                                                                                                                             
        acr_status_suffix='AO805',                                                                                                                                                      
        pv_index=2,                                                                                                                                                                     
        **kwargs                                                                                                                                                                        
    ):                                                                                                                                                                                  
        self.acr_status_suffix = acr_status_suffix                                                                                                                                      
        self.pv_index = pv_index                                                                                                                                                        
        super().__init__(prefix, **kwargs)


class DCCM(BaseInterface, GroupDevice):
    """
    The full DCCM assembly.

    Double Channel Cut Monochrometer controlled with a Beckhoff PLC.                                                                                             
    This includes five axes in total:                                                                                                                            
        - 2 for crystal manipulation (TH1/Upstream and TH2/Downstream)                                                                                           
        - 1 for chamber translation in x direction (TX)                                                                                                          
    - 2 for YAG diagnostics (TXD and TYD)                                                                                                                        
                                                                                                                                                                 
    Parameters
    ----------
    prefix : str
        Base PV for DCCM motors
    name : str, keyword-only
        name to use in bluesky
    """
    
    tab_component_names = True

    th1 = Cpt(BeckhoffAxis, ":MMS:TH1", doc="Bragg Upstream/TH1 Axis", kind="normal")
    th2 = Cpt(BeckhoffAxis, ":MMS:TH2", doc="Bragg Downstream/TH2 Axis", kind="normal")
    tx = Cpt(BeckhoffAxis, ":MMS:TX", doc="Translation X Axis", kind="normal")
    txd = Cpt(BeckhoffAxis, ":MMS:TXD", doc="YAG Diagnostic X Axis", kind="normal")
    tyd = Cpt(BeckhoffAxis, ":MMS:TYD", doc="YAG Diagnostic Y Axis", kind="normal")


    energy = Cpt(
        DCCMEnergy, '', kind='hinted',
        doc=(
            'PseudoPositioner that moves the theta motors in '
            'terms of the calculated DCCM energy.'
        ),
    )

    energy_with_vernier = Cpt(
        DCCMEnergyWithVernier, '', kind='normal',
        doc=(
            'PseudoPositioner that moves the theta motor in '
            'terms of the calculated DCCM energy while '
            'also requesting a vernier move.'
        ),
    )
    energy_with_acr_status = FCpt(
        DCCMEnergyWithACRStatus, '{prefix}', kind='normal',
        acr_status_suffix='{acr_status_suffix}',
        add_prefix=('suffix', 'write_pv', 'acr_status_suffix'),
        doc=(
            'PseudoPositioner that moves the alio in '
            'terms of the calculated CCM energy while '
            'also requesting an energy change to ACR. '
            'This will wait on ACR to complete the move.'
        ),
    )
    
    def __init__(
        self,
        *,
        prefix: typing.Optional[str] = None,
        in_pos: float,
        out_pos: float,
        **kwargs
    ):
        UCpt.collect_prefixes(self, kwargs)
        self._in_pos = in_pos
        self._out_pos = out_pos
        prefix = prefix or self.unrelated_prefixes['alio_prefix']
        self.acr_status_suffix = kwargs.get('acr_status_suffix', 'AO805')
        self.acr_status_pv_index = kwargs.get('acr_status_suffix', 2)
        super().__init__(prefix, **kwargs)


    def calc_lightpath_state(self, x_up: float) -> LightpathState:
        """                                                                                                                                                                             
        Update the fields used by the lightpath to determine in/out.                                                                                                                    
                                                                                                                                                                                        
        Compares the x position with the saved in and out values.                                                                                                                       
        """
        self._inserted = bool(np.isclose(x_up, self._in_pos))
        self._removed = bool(np.isclose(x_up, self._out_pos))
        if self._removed:
            self._transmission = 1
        else:
            # Placeholder "small attenuation" value                                                                                                                                     
            self._transmission = 0.9

        return LightpathState(
            inserted=self._inserted,
            removed=self._removed,
            output={self.output_branches[0]: self._transmission}
        )

        @property
    def inserted(self):
        return self._inserted

    @property
    def removed(self):
        return self._removed

    def insert(self, wait: bool = False) -> MoveStatus:
        """                                                                                                                                                                             
        Move the x motors to the saved "in" position.                                                                                                                                   
                                                                                                                                                                                        
        Parameters                                                                                                                                                                      
        ----------                                                                                                                                                                      
        wait : bool, optional                                                                                                                                                           
            If True, wait for the move to complete.                                                                                                                                     
            If False, return without waiting.                                                                                                                                           
                                                                                                                                                                                        
        Returns                                                                                                                                                                         
        -------                                                                                                                                                                         
        move_status : MoveStatus                                                                                                                                                        
            A status object that tells you information about the                                                                                                                        
            success/failure/completion status of the move.                                                                                                                              
        """
        return self.x.move(self._in_pos, wait=wait)

    def remove(self, wait: bool = False) -> MoveStatus:
        """                                                                                                                                                                             
        Move the x motors to the saved "out" position.                                                                                                                                  
                                                                                                                                                                                        
        Parameters                                                                                                                                                                      
        ----------                                                                                                                                                                      
        wait : bool, optional                                                                                                                                                           
            If True, wait for the move to complete.                                                                                                                                     
            If False, return without waiting.                                                                                                                                           
                                                                                                                                                                                        
        Returns                                                                                                                                                                         
        -------                                                                                                                                                                         
        move_status : MoveStatus                                                                                                                                                        
            A status object that tells you information about the                                                                                                                        
            success/failure/completion status of the move.                                                                                                                              
        """
        return self.x.move(self._out_pos, wait=wait)


