"""
Classes for cards attached to EK9000 bus couplers.
"""

from ophyd import Component as Cpt
from ophyd import Device
from ophyd import FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO

from pcdsdevices.variety import set_metadata


class El3174AiCh(Device):
    """
    EL3174 analog input card channel.

    Can be used to digitize a variety of sensors.

    Parameters
    ----------
    prefix : str
        The PV base of the card.
    """
    measured = Cpt(EpicsSignalRO, '.VAL', kind='normal', doc='Converted value')
    raw_adc = Cpt(EpicsSignalRO, '.RVAL', kind='config', doc='Raw ADC count')
    egu = Cpt(EpicsSignal, '.EGU', kind='config', doc='Engineering units')
    # TJ: These may be useful later, but not now
    # egu_max = Cpt(EpicsSignal, '.EGUF', kind='config')
    # egu_min = Cpt(EpicsSignal, '.EGUL', kind='config')
    slope = Cpt(EpicsSignal, '.ESLO', kind='config', doc='EGU per ADC count')
    offset = Cpt(EpicsSignal, '.EOFF', kind='config', doc='Offset in EGU')
    conversion = Cpt(EpicsSignal, '.LINR', kind='config')
    precision = Cpt(EpicsSignal, '.PREC', kind='config')


class EnvironmentalMonitor(Device):
    """
    Class for the MODS environmental monitoring system, which typically
    consists of three measurements: P, T, and %RH.
    """

    pressure = Cpt(El3174AiCh, ':1')
    humidity = Cpt(El3174AiCh, ':2')
    temperature = Cpt(El3174AiCh, ':3')


class SimpleShutter(Device):
    """
    Class for simple 24 VDC shutters controlled by a DC relay card.
    """

    actuate = FCpt(EpicsSignal, '{prefix}', kind='normal', doc='Actuate shutter')

    set_metadata(actuate, dict(variety='command-enum'))

    def __init__(self, prefix='', **kwargs):
        super().__init__(prefix, **kwargs)
        self.actuate.long_name = 'Actuate State'
