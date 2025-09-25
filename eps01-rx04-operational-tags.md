# Operational instrument TAGS for plc EPS01 (Reactor 04)

- Heating (Ensure preconditions are met manually (HW pump on/pressure etc))

  - Stop cooling water flow
  - Close XV_CWS_RX04
  - Close XV_CWR_RX04
  - Close XV_CHWS_RX04
  - Close XV_CHWR_RX04

  - Start hot water flow
  - Open XV_HWR_RX04
  - Open FCV_JACKET_RX04
  - Open XV_HWS_RX04

- Cooling (Ensure CW pump running / pressure /flow rate)

  - Stop hot water flow
  - Close XV_HWS_RX04
  - Close XV_HWR_RX04
  - Close XV_CHWS_RX04
  - Close XV_CHWR_RX04

  - Start cooling water flow
  - Open XV_HWR_RX04
  - Open FCV_JACKET_RX04 (Very low percent opening)
  - Open XV_HWS_RX04

- Agitator (Ensure agitator checks/preconditions)
  - Check if agitator trip
    - Reset if trip RCT_RX04_VFD_RST
  - Set Agitator to Auto Mode / Manual mode (Test which one works) (RCT_RX04_VFD_ATO)
  - Start Agitator (RCT_RX04_VFD_STR)
  - Gradually increase AGITATOR_VFD_SP
