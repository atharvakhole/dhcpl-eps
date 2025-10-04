
@dataclass
class RegisterMapping:

    # CASCADE
    AG_AMP_R4 = Register("AG_AMP_R4", 8927, float)
    AG_RPM_R4 = Register("AG_RPM_R4", 8921, float)
    AG_SP_R4 = Register("AG_SP_R4", 6751, float)
    AG_SWTICH_ON_R4 = Register("AG_SWITCH_ON_R4", 60529, float)
    AG_IS_ON_R4 = Register("AG_IS_ON_R4", 8619, bool)

    AG_TRIP_FEEDBACK_R4 = Register("AG_TRIP_FEEDBACK_R4", 8321, bool)
    PT_R4 = Register("PT_R4", 8789, float)
    LT_R4 = Register("LT_R4", 8885, float)
    TE_MASS_UPPER_R4 = Register("TE_MASS_UPPER_R4", 8835, float)
    TE_MASS_LOWER_R4 = Register("TE_MASS_LOWER_R4", 8837, float)
    TE_JACKET_IN_R4 = Register("TE_JACKET_IN_R4", 8893, float)
    TE_JACKET_OUT_R4 = Register("TE_JACKET_OUT_R4", 8841, float)
    TE_HW_IN_R4 = Register("TE_HW_IN_R4", 8845, float)
    TE_HW_OUT_R4 = Register("TE_HW_OUT_R4", 8847, float)
    TE_CW_IN_R4 = Register("TE_CW_IN_R4", 8873, float)
    TE_CW_OUT_R4 = Register("TE_CW_OUT_R4", 8875, float)
    TE_CHW_IN_R4 = Register("TE_CHW_IN_R4", 8877, float)
    TE_CHW_OUT_R4 = Register("TE_CHW_OUT_R4", 8879, float)

    XV_HWS_R4 = Register("XV_HWS_R4", 6507, bool)
    XV_HWS_R4_FEEDBACK_OPEN = Register("XV_HWS_R4_FEEDBACK_OPEN", 8377, bool)
    XV_HWS_R4_FEEDBACK_CLOSE = Register("XV_HWS_R4_FEEDBACK_CLOSE", 8379, bool)

    XV_HWR_R4 = Register("XV_HWR_R4", 6513, bool)
    XV_HWR_R4_FEEDBACK_OPEN = Register("XV_HWR_R4_FEEDBACK_OPEN", 8381, bool)
    XV_HWR_R4_FEEDBACK_CLOSE = Register("XV_HWR_R4_FEEDBACK_CLOSE", 8383, bool)

    XV_CWS_R4 = Register("XV_CWS_R4", 6555, bool)
    XV_CWS_R4_FEEDBACK_OPEN = Register("XV_CWS_R4_FEEDBACK_OPEN", 8409, bool)
    XV_CWS_R4_FEEDBACK_CLOSE = Register("XV_CWS_R4_FEEDBACK_CLOSE", 8411, bool)

    XV_CWR_R4 = Register("XV_CWR_R4", 6561, bool)
    XV_CWR_R4_FEEDBACK_OPEN = Register("XV_CWR_R4_FEEDBACK_OPEN", 8413, bool)
    XV_CWR_R4_FEEDBACK_CLOSE = Register("XV_CWR_R4_FEEDBACK_CLOSE", 8415, bool)

    XV_CHWS_R4 = Register("XV_CHWS_R4", 6603, bool)
    XV_CHWS_R4_FEEDBACK_OPEN = Register("XV_CHWS_R4_FEEDBACK_OPEN", 8441, bool)
    XV_CHWS_R4_FEEDBACK_CLOSE = Register("XV_CHWS_R4_FEEDBACK_CLOSE", 8443, bool)

    XV_CHWR_R4 = Register("XV_CHWR_R4", 6609, bool)
    XV_CHWR_R4_FEEDBACK_OPEN = Register("XV_CHWR_R4_FEEDBACK_OPEN", 8445, bool)
    XV_CHWR_R4_FEEDBACK_CLOSE = Register("XV_CHWR_R4_FEEDBACK_CLOSE", 8447, bool)

    FCV_JACKET_SP_R4 = Register("FCV_JACKET_SP_R4", 7451, float)
    FCV_JACKET_SWITCH_ON_R4 = Register("FCV_JACKET_SWITCH_ON_R4", 6767, bool)

    FLOW_METER_JACKET_R4 = Register("FLOW_METER_JACKET_R4", 8925, float)

    # DRAIN
    FBV_R4 = Register("FBV_R4", 6447, bool)
    XV_ER_DRAIN_R4 = Register("XV_ER_DRAIN_R4", 6657, bool)
    XV_SLURRY_OL_R1 = Register("XV_SLURRY_OL_R1", 6611, bool)
    XV_SLURRY_OL_R2 = Register("XV_SLURRY_OL_R2", 6627, bool)
    XV_SLURRY_OL_R3 = Register("XV_SLURRY_OL_R3", 6639, bool)
    XV_SLURRY_OL_R4 = Register("XV_SLURRY_OL_R4", 6651, bool)

    # SLURRY COOLER
    # TE_SLURRY_IN_SC = Register("TE_SLURRY_IN_SC", 0, float)
    # TE_SLURRY_OUT_SC = Register("TE_SLURRY_OUT_SC", 0, float)
    # TE_CW_IN_SC = Register("TE_CW_IN_SC", 0, float)
    # FLOW_METER_JACKET_SC = Register("FLOW_METER_JACKET_SC", 0, float)
    # FCV_JACKET_SC = Register("FCV_JACKET_SC", 0, float)

    def __post_init__(self):
        self.registers: list[Register] = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, Register):
                attr.addr -= 1
                self.registers.append(attr)
