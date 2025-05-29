# max31855.py
# Enhanced MAX31855 driver with detailed fault reporting

import struct
import time


class MAX31855:
    # Fault bit definitions
    FAULT_OPEN = 0x01  # D0: Open circuit
    FAULT_GND = 0x02  # D1: Short to GND
    FAULT_VCC = 0x04  # D2: Short to VCC
    FAULT_GENERIC = 0x10000  # D16: Any fault

    def __init__(self, spi, cs):
        self.spi = spi
        self.cs = cs
        self.cs.value(1)
        time.sleep(0.1)

    def read_raw(self):
        """Read 32 bits from MAX31855"""
        self.cs.value(0)
        time.sleep_us(10)
        data = bytearray(4)
        self.spi.readinto(data)
        self.cs.value(1)

        # If the sensor is disconnected, SPI bus may return all zeros or all ones
        if data == b"\x00\x00\x00\x00":
            return None, "No SPI response (disconnected)"
        if data == b"\xff\xff\xff\xff":
            return None, "SPI bus error (all high)"

        return struct.unpack(">I", data)[0], None

    def get_fault_string(self, raw_value):
        """Decode fault bits into human-readable string"""
        faults = []

        if raw_value & self.FAULT_OPEN:
            faults.append("Open Circuit")
        if raw_value & self.FAULT_GND:
            faults.append("Short to GND")
        if raw_value & self.FAULT_VCC:
            faults.append("Short to VCC")

        if faults:
            return " + ".join(faults)
        elif raw_value & self.FAULT_GENERIC:
            return "Unknown Fault"
        return None

    def read_all(self):
        """
        Read all data from MAX31855
        Returns dict with:
            - tc_temp: thermocouple temperature (°C) or None
            - internal_temp: internal temperature (°C) or None
            - fault: fault string or None
            - raw: raw 32-bit value
            - connected: bool indicating if sensor responded
        """
        raw_value, error = self.read_raw()

        result = {
            "tc_temp": None,
            "internal_temp": None,
            "fault": None,
            "raw": raw_value,
            "connected": raw_value is not None,
        }

        if not result["connected"]:
            result["fault"] = error
            return result

        # Check for faults
        if raw_value & self.FAULT_GENERIC:
            result["fault"] = self.get_fault_string(raw_value)
            # Still try to read internal temp even with fault

        # Decode thermocouple temperature (bits 31-18)
        if not result["fault"]:  # Only read TC temp if no fault
            tc_raw = (raw_value >> 18) & 0x3FFF
            if raw_value & 0x80000000:  # Sign bit
                tc_raw -= 0x4000
            result["tc_temp"] = tc_raw * 0.25

        # Decode internal temperature (bits 15-4)
        internal_raw = (raw_value >> 4) & 0x7FF
        if raw_value & 0x8000:  # Sign bit
            internal_raw -= 0x800
        result["internal_temp"] = internal_raw * 0.0625

        return result

    def read_temp_c(self):
        """
        Legacy method - returns just the thermocouple temperature
        Returns: float (temperature), None (fault), or False (disconnected)
        """
        data = self.read_all()

        if not data["connected"]:
            return False

        if data["fault"]:
            print(f"MAX31855 Fault: {data['fault']}")
            return None

        return data["tc_temp"]

    def read_internal(self):
        """
        Legacy method - returns just the internal temperature
        """
        data = self.read_all()
        print(data)

        if not data["connected"]:
            return False

        return data["internal_temp"]

    def diagnose(self):
        """
        Diagnostic method for troubleshooting
        Returns detailed string about sensor status
        """
        data = self.read_all()

        lines = []
        lines.append(f"Connected: {data['connected']}")

        if data["connected"]:
            lines.append(f"Raw value: 0x{data['raw']:08X}")
            if data["tc_temp"] is not None:
                lines.append(f"TC Temp: {data['tc_temp']:.2f}°C")
            if data["internal_temp"] is not None:
                lines.append(f"Internal: {data['internal_temp']:.2f}°C")
            if data["fault"]:
                lines.append(f"FAULT: {data['fault']}")
        else:
            lines.append(f"Error: {data['fault']}")

        return "\n".join(lines)
