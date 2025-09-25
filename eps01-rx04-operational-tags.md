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

- VALVES

  - XV_HWS_RX04
    - 0x1966,6503,XV_110_STR,,Variable,84,float 32, , ,Digital,ON,OFF,OFF
    - 0x1968,6505,XV_110_RST,,Variable,85,float 32, , ,Digital,ON,OFF,OFF
    - 0x196A,6507,XV_110_STR_AM,,Variable,86,float 32, , ,Digital,ON,OFF,OFF
    - 0x20B8,8377,XV_110_OPEN_FB,,Signal Tag,93,float 32, , ,Digital,ON,OFF,Block 112 Output 13
    - 0x20BA,8379,XV_110_CLOSE_FB,,Signal Tag,94,float 32, , ,Digital,ON,OFF,Block 112 Output 14
    - 0x21C6,8647,XV_110_STR_ON,,Signal Tag,228,float 32, , ,Digital,ON,OFF,Block 129 Output 12
    - 0x2386,9095,XV_110_STR_CMD,,Signal Tag,452,float 32, , ,Digital,ON,OFF,Block 370 Output 11
    - 0x2388,9097,XV_110_STS,,Signal Tag,453,float 32,,0,Analog, , ,Block 370 Output 10
    - 0x238A,9099,XV_110_AM,,Signal Tag,454,float 32, , ,Digital,ON,OFF,Variable #:86
  - XV_HWR_RX04

    - 0x196C,6509,XV_111_STR,,Variable,87,float 32, , ,Digital,ON,OFF,OFF
    - 0x196E,6511,XV_111_RST,,Variable,88,float 32, , ,Digital,ON,OFF,OFF
    - 0x1970,6513,XV_111_STR_AM,,Variable,89,float 32, , ,Digital,ON,OFF,OFF
    - 0x20BC,8381,XV_111_OPEN_FB,,Signal Tag,95,float 32, , ,Digital,ON,OFF,Block 112 Output 15
    - 0x20BE,8383,XV_111_CLOSE_FB,,Signal Tag,96,float 32, , ,Digital,ON,OFF,Block 112 Output 16
    - 0x21C8,8649,XV_111_STR_ON,,Signal Tag,229,float 32, , ,Digital,ON,OFF,Block 129 Output 13
    - 0x238C,9101,XV_111_STR_CMD,,Signal Tag,455,float 32, , ,Digital,ON,OFF,Block 375 Output 11
    - 0x238E,9103,XV_111_STS,,Signal Tag,456,float 32,,0,Analog, , ,Block 375 Output 10
    - 0x2390,9105,XV_111_AM,,Signal Tag,457,float 32, , ,Digital,ON,OFF,Variable #:89

  - XV_CWS_RX04

    - 0x1996,6551,XV_118_STR,,Variable,108,float 32, , ,Digital,ON,OFF,OFF
    - 0x1998,6553,XV_118_RST,,Variable,109,float 32, , ,Digital,ON,OFF,OFF
    - 0x199A,6555,XV_118_STR_AM,,Variable,110,float 32, , ,Digital,ON,OFF,OFF
    - 0x20D8,8409,XV_118_OPEN_FB,,Signal Tag,109,float 32, , ,Digital,ON,OFF,Block 114 Output 13
    - 0x20DA,8411,XV_118_CLOSE_FB,,Signal Tag,110,float 32, , ,Digital,ON,OFF,Block 114 Output 14
    - 0x21D6,8663,XV_118_STR_ON,,Signal Tag,236,float 32, , ,Digital,ON,OFF,Block 130 Output 12
    - 0x23B6,9143,XV_118_STR_CMD,,Signal Tag,476,float 32, , ,Digital,ON,OFF,Block 410 Output 11
    - 0x23B8,9145,XV_118_STS,,Signal Tag,477,float 32,,0,Analog, , ,Block 410 Output 10
    - 0x23BA,9147,XV_118_AM,,Signal Tag,478,float 32, , ,Digital,ON,OFF,Variable #:110

  - XV_CWR_RX04

    - 0x199C,6557,XV_119_STR,,Variable,111,float 32, , ,Digital,ON,OFF,OFF
    - 0x199E,6559,XV_119_RST,,Variable,112,float 32, , ,Digital,ON,OFF,OFF
    - 0x19A0,6561,XV_119_STR_AM,,Variable,113,float 32, , ,Digital,ON,OFF,OFF
    - 0x20DC,8413,XV_119_OPEN_FB,,Signal Tag,111,float 32, , ,Digital,ON,OFF,Block 114 Output 15
    - 0x20DE,8415,XV_119_CLOSE_FB,,Signal Tag,112,float 32, , ,Digital,ON,OFF,Block 114 Output 16
    - 0x21D8,8665,XV_119_STR_ON,,Signal Tag,237,float 32, , ,Digital,ON,OFF,Block 130 Output 13
    - 0x23BC,9149,XV_119_STR_CMD,,Signal Tag,479,float 32, , ,Digital,ON,OFF,Block 415 Output 11
    - 0x23BE,9151,XV_119_STS,,Signal Tag,480,float 32,,0,Analog, , ,Block 415 Output 10
    - 0x23C0,9153,XV_119_AM,,Signal Tag,481,float 32, , ,Digital,ON,OFF,Variable #:113

  - XV_CHWS_RX04
    0x19C6,6599,XV_126_STR,,Variable,132,float 32, , ,Digital,ON,OFF,OFF
    0x19C8,6601,XV_126_RST,,Variable,133,float 32, , ,Digital,ON,OFF,OFF
    0x19CA,6603,XV_126_STR_AM,,Variable,134,float 32, , ,Digital,ON,OFF,OFF
    0x20F8,8441,XV_126_OPEN_FB,,Signal Tag,125,float 32, , ,Digital,ON,OFF,Block 116 Output 13
    0x20FA,8443,XV_126_CLOSE_FB,,Signal Tag,126,float 32, , ,Digital,ON,OFF,Block 116 Output 14
    0x21E6,8679,XV_126_STR_ON,,Signal Tag,244,float 32, , ,Digital,ON,OFF,Block 131 Output 12
    0x23E6,9191,XV_126_STR_CMD,,Signal Tag,500,float 32, , ,Digital,ON,OFF,Block 450 Output 11
    0x23E8,9193,XV_126_STS,,Signal Tag,501,float 32,,0,Analog, , ,Block 450 Output 10
    0x23EA,9195,XV_126_AM,,Signal Tag,502,float 32, , ,Digital,ON,OFF,Variable #:134

  - XV_CHWR_RX04
    0x19CC,6605,XV_127_STR,,Variable,135,float 32, , ,Digital,ON,OFF,OFF
    0x19CE,6607,XV_127_RST,,Variable,136,float 32, , ,Digital,ON,OFF,OFF
    0x19D0,6609,XV_127_STR_AM,,Variable,137,float 32, , ,Digital,ON,OFF,OFF
    0x20FC,8445,XV_127_OPEN_FB,,Signal Tag,127,float 32, , ,Digital,ON,OFF,Block 116 Output 15
    0x20FE,8447,XV_127_CLOSE_FB,,Signal Tag,128,float 32, , ,Digital,ON,OFF,Block 116 Output 16
    0x21E8,8681,XV_127_STR_ON,,Signal Tag,245,float 32, , ,Digital,ON,OFF,Block 131 Output 13
    0x23EC,9197,XV_127_STR_CMD,,Signal Tag,503,float 32, , ,Digital,ON,OFF,Block 455 Output 11
    0x23EE,9199,XV_127_STS,,Signal Tag,504,float 32,,0,Analog, , ,Block 455 Output 10
    0x23F0,9201,XV_127_AM,,Signal Tag,505,float 32, , ,Digital,ON,OFF,Variable #:137

  - FBV_RX04
    0x192A,6443,XVX_104_STR,,Variable,54,float 32, , ,Digital,ON,OFF,OFF
    0x192C,6445,XVX_104_RST,,Variable,55,float 32, , ,Digital,ON,OFF,OFF
    0x192E,6447,XVX_104_STR_AM,,Variable,56,float 32, , ,Digital,ON,OFF,OFF
    0x2090,8337,XVX_104_OPEN_FB,,Signal Tag,73,float 32, , ,Digital,ON,OFF,Block 110 Output 9
    0x2092,8339,XVX_104_CLOSE_FB,,Signal Tag,74,float 32, , ,Digital,ON,OFF,Block 110 Output 10
    0x21B2,8627,XVX_104_STR_ON,,Signal Tag,218,float 32, , ,Digital,ON,OFF,Block 128 Output 10
    0x234A,9035,XVX_104_STR_CMD,,Signal Tag,422,float 32, , ,Digital,ON,OFF,Block 320 Output 11
    0x234C,9037,XVX_104_STR_STS,,Signal Tag,423,float 32,,0,Analog, , ,Block 320 Output 10
    0x234E,9039,XVX_104_AM,,Signal Tag,424,float 32, , ,Digital,ON,OFF,Variable #:56

  - EMERGENCY_DR_XV_RX04
    0x19FC,6653,XV_135_STR,,Variable,159,float 32, , ,Digital,ON,OFF,OFF
    0x19FE,6655,XV_135_RST,,Variable,160,float 32, , ,Digital,ON,OFF,OFF
    0x1A00,6657,XV_135_STR_AM,,Variable,161,float 32, , ,Digital,ON,OFF,OFF
    0x211C,8477,XV_135_OPEN_FB,,Signal Tag,143,float 32, , ,Digital,ON,OFF,Block 118 Output 15
    0x211E,8479,XV_135_CLOSE_FB,,Signal Tag,144,float 32, , ,Digital,ON,OFF,Block 118 Output 16
    0x21F8,8697,XV_135_STR_ON,,Signal Tag,253,float 32, , ,Digital,ON,OFF,Block 132 Output 13
    0x241C,9245,XV_135_STR_CMD,,Signal Tag,527,float 32, , ,Digital,ON,OFF,Block 495 Output 11
    0x241E,9247,XV_135_STS,,Signal Tag,528,float 32,,0,Analog, , ,Block 495 Output 10
    0x2420,9249,XV_135_AM,,Signal Tag,529,float 32, , ,Digital,ON,OFF,Variable #:161

  - SLURRY_OL_XV_RX04
    0x19F6,6647,XV_134_STR,,Variable,156,float 32, , ,Digital,ON,OFF,OFF
    0x19F8,6649,XV_134_RST,,Variable,157,float 32, , ,Digital,ON,OFF,OFF
    0x19FA,6651,XV_134_STR_AM,,Variable,158,float 32, , ,Digital,ON,OFF,OFF
    0x2118,8473,XV_134_OPEN_FB,,Signal Tag,141,float 32, , ,Digital,ON,OFF,Block 118 Output 13
    0x211A,8475,XV_134_CLOSE_FB,,Signal Tag,142,float 32, , ,Digital,ON,OFF,Block 118 Output 14
    0x21F6,8695,XV_134_STR_ON,,Signal Tag,252,float 32, , ,Digital,ON,OFF,Block 132 Output 12
    0x2416,9239,XV_134_STR_CMD,,Signal Tag,524,float 32, , ,Digital,ON,OFF,Block 490 Output 11
    0x2418,9241,XV_134_STS,,Signal Tag,525,float 32,,0,Analog, , ,Block 490 Output 10
    0x241A,9243,XV_134_AM,,Signal Tag,526,float 32, , ,Digital,ON,OFF,Variable #:158

  - SLURRY_OL_XV_RX03
    0x19EA,6635,XV_132_STR,,Variable,150,float 32, , ,Digital,ON,OFF,OFF
    0x19EC,6637,XV_132_RST,,Variable,151,float 32, , ,Digital,ON,OFF,OFF
    0x19EE,6639,XV_132_STR_AM,,Variable,152,float 32, , ,Digital,ON,OFF,OFF
    0x2110,8465,XV_132_OPEN_FB,,Signal Tag,137,float 32, , ,Digital,ON,OFF,Block 118 Output 9
    0x2112,8467,XV_132_CLOSE_FB,,Signal Tag,138,float 32, , ,Digital,ON,OFF,Block 118 Output 10
    0x21F2,8691,XV_132_STR_ON,,Signal Tag,250,float 32, , ,Digital,ON,OFF,Block 132 Output 10
    0x240A,9227,XV_132_STR_CMD,,Signal Tag,518,float 32, , ,Digital,ON,OFF,Block 480 Output 11
    0x240C,9229,XV_132_STS,,Signal Tag,519,float 32,,0,Analog, , ,Block 480 Output 10
    0x240E,9231,XV_132_AM,,Signal Tag,520,float 32, , ,Digital,ON,OFF,Variable #:152

  - SLURRY_OL_XV_RX02
    0x19DE,6623,XV_130_STR,,Variable,144,float 32, , ,Digital,ON,OFF,OFF
    0x19E0,6625,XV_130_RST,,Variable,145,float 32, , ,Digital,ON,OFF,OFF
    0x19E2,6627,XV_130_STR_AM,,Variable,146,float 32, , ,Digital,ON,OFF,OFF
    0x2108,8457,XV_130_OPEN_FB,,Signal Tag,133,float 32, , ,Digital,ON,OFF,Block 117 Output 13
    0x210A,8459,XV_130_CLOSE_FB,,Signal Tag,134,float 32, , ,Digital,ON,OFF,Block 117 Output 14
    0x21EE,8687,XV_130_STR_ON,,Signal Tag,248,float 32, , ,Digital,ON,OFF,Block 131 Output 16
    0x23FE,9215,XV_130_STR_CMD,,Signal Tag,512,float 32, , ,Digital,ON,OFF,Block 470 Output 11
    0x2400,9217,XV_130_STS,,Signal Tag,513,float 32,,0,Analog, , ,Block 470 Output 10
    0x2402,9219,XV_130_AM,,Signal Tag,514,float 32, , ,Digital,ON,OFF,Variable #:146

  - SLURRY_OL_XV_RX01
    0x19D2,6611,XV_128_STR,,Variable,138,float 32, , ,Digital,ON,OFF,OFF
    0x19D4,6613,XV_128_RST,,Variable,139,float 32, , ,Digital,ON,OFF,OFF
    0x19D6,6615,XV_128_STR_AM,,Variable,140,float 32, , ,Digital,ON,OFF,OFF
    0x2100,8449,XV_128_OPEN_FB,,Signal Tag,129,float 32, , ,Digital,ON,OFF,Block 117 Output 9
    0x2102,8451,XV_128_CLOSE_FB,,Signal Tag,130,float 32, , ,Digital,ON,OFF,Block 117 Output 10
    0x21EA,8683,XV_128_STR_ON,,Signal Tag,246,float 32, , ,Digital,ON,OFF,Block 131 Output 14
    0x23F2,9203,XV_128_STR_CMD,,Signal Tag,506,float 32, , ,Digital,ON,OFF,Block 460 Output 11
    0x23F4,9205,XV_128_STS,,Signal Tag,507,float 32,,0,Analog, , ,Block 460 Output 10
    0x23F6,9207,XV_128_AM,,Signal Tag,508,float 32, , ,Digital,ON,OFF,Variable #:140

  - FCV_JACKET_RX04

- VFD

  - AGITATOR_VFD_SP_RX04
    0x1A5E,6751,RX_04_VFD_SP,,Variable,208,float 32,,0,Analog, , ,0.00

  - AGITATOR_VFD_AUTO_MODE
    0xEC70,60529,RCT_RX04_VFD_ATO,,Variable,865,float 32, , ,Digital,ON,OFF,OFF
  - AGITATOR_AGITATOR_VFD_START
    0x1914,6421,RCT_RX04_VFD_STR,,Variable,43,float 32, , ,Digital,ON,OFF,OFF
    0x1916,6423,RCT_RX04_VFD_RST,,Variable,44,float 32, , ,Digital,ON,OFF,OFF

0x21AA,8619,RCT_RX04_VFD_ON,,Signal Tag,214,float 32, , ,Digital,ON,OFF,Block 127 Output 14
0x2334,9013,RCT_RX04_VFD_CMD,,Signal Tag,411,float 32, , ,Digital,ON,OFF,Block 301 Output 11
0x2336,9015,RCT_RX04_VFD_STS,,Signal Tag,412,float 32,,0,Analog, , ,Block 301 Output 10
0x4374,17269,RCT_RX04_VFD_AT,,Signal Tag,1035,float 32, , ,Digital,ON,OFF,Variable #:865
0x22D8,8921,RX_04_VFD,,Signal Tag,365,float 32,,0,Analog, , ,Block 213 Output 4
0x22DE,8927,RX_04_VFD_AMP,,Signal Tag,368,float 32,,0,Analog, , ,Block 216 Output 4
0x246E,9327,RX_04_VFD_REF,,Signal Tag,568,float 32,,0,Analog, , ,Block 582 Output 4

- INPUTS
- Reactor 04 pressure
  0x2254,8789,PT_111,,Signal Tag,299,float 32,,0,Analog, , ,Block 147 Output 4

- Reactor 04 Mass temperature top
  0x2282,8835,TT_113,,Signal Tag,322,float 32,,0,Analog, , ,Block 170 Output 4

- Reactor 04 Mass temperature bottom
  0x2284,8837,TT_114,,Signal Tag,323,float 32,,0,Analog, , ,Block 171 Output 4

- Jacket Inlet temperature
  0x22BC,8893,TT_R4JKTIL,,Signal Tag,351,float 32,,0,Analog, , ,Block 199 Output 4

- Flow jacket inlet
  0x22DC,8925,FT_R4JKTIL,,Signal Tag,367,float 32,,0,Analog, , ,Block 215 Output 4

- Level Transmitter
  0x22B4,8885,LT_112,,Signal Tag,347,float 32,,0,Analog, , ,Block 195 Output 4

- Jacket temperature
  0x2288,8841,TT_116,,Signal Tag,325,float 32,,0,Analog, , ,Block 173 Output 4

- HW Inlet temperature
  0x228C,8845,TT_118,,Signal Tag,327,float 32,,0,Analog, , ,Block 175 Output 4

- HW Outlet temperature
  0x228E,8847,TT_119,,Signal Tag,328,float 32,,0,Analog, , ,Block 176 Output 4

- CW Inlet temperature
  0x22A8,8873,TT_132,,Signal Tag,341,float 32,,0,Analog, , ,Block 189 Output 4

- CW Outlet temperature
  0x22AA,8875,TT_133,,Signal Tag,342,float 32,,0,Analog, , ,Block 190 Output 4

- CHW Inlet temperature
  0x22AC,8877,TT_134,,Signal Tag,343,float 32,,0,Analog, , ,Block 191 Output 4

- CHW Outlet temperature
  0x22AE,8879,TT_135,,Signal Tag,344,float 32,,0,Analog, , ,Block 192 Output 4
