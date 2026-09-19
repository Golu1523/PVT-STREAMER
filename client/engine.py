"""
engine.py - Prime Xiters memory engine (CHECK METHOD main.py se ekdam same copy)
AobScanner: pythonnet (clr) -> PrimeXitersMemory.dll (KrishuMemoryLib.MemoryAPI)
"""
import os
import sys
import struct

try:
    import clr
    CLR_OK = True
except Exception as _clr_err:
    print("[Engine] pythonnet (clr) load nahi hua:", _clr_err)
    CLR_OK = False


def _memory_dll_path():
    # PyInstaller frozen: sys._MEIPASS, warna script folder
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "PrimeXitersMemory.dll")
    if os.path.exists(p):
        return p
    p2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PrimeXitersMemory.dll")
    if os.path.exists(p2):
        return p2
    return p


class AobScanner:
    def __init__(self):
        self.memory = None
        self.current_pid = None
        self.is_attached = False
        self.dll_loaded = False

        # Load C# DLL
        self.load_dll()

    def load_dll(self):
        """Load the PrimeXitersMemory DLL"""
        try:
            dll_path = _memory_dll_path()
            if not os.path.exists(dll_path):
                print(f"[X] DLL not found: {dll_path}")
                return False

            clr.AddReference(dll_path)
            from KrishuMemoryLib import MemoryAPI  # type: ignore
            self.memory = MemoryAPI()
            self.dll_loaded = True
            print("[OK] Memory library loaded")
            return True
        except Exception as e:
            print(f"[X] Failed to load DLL: {e}")
            return False

    def attach_to_emulator(self):
        """Attach to HD-Player emulator"""
        if not self.dll_loaded:
            return {"success": False, "message": "DLL not loaded!"}

        try:
            # Find HD-Player
            import psutil
            emulator = None
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = proc.info['name']
                    if "HD-Player" in name or "aow_exe" in name or "LdVBoxHeadless" in name:
                        emulator = {
                            'pid': proc.info['pid'],
                            'name': name,
                            'type': name.replace('.exe', '')
                        }
                        break
                except Exception:
                    continue

            if not emulator:
                return {"success": False, "message": "HD-Player not found!"}

            self.current_pid = emulator['pid']
            if self.memory.Initialize(self.current_pid):
                self.is_attached = True
                return {"success": True, "message": f"Attached to {emulator['name']}", "emulator": emulator}
            else:
                return {"success": False, "message": "Failed to attach to process!", "emulator": emulator}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def attach_to_pid(self, pid):
        """Attach to a specific PID"""
        if not self.dll_loaded:
            return False

        try:
            self.current_pid = pid
            if self.memory.Initialize(pid):
                self.is_attached = True
                return True
            return False
        except Exception:
            return False

    def scan_only(self, pattern):
        """Scan for pattern without writing"""
        if not self.is_attached:
            return {"success": False, "message": "Not attached!"}

        try:
            pattern_clean = pattern.replace("??", "?").strip()
            result = self.memory.ScanPattern(pattern_clean, True, False)

            if result and len(result) > 0:
                addresses = list(result)
                return {"success": True, "addresses": addresses, "count": len(addresses)}
            else:
                return {"success": False, "message": "Pattern not found!"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def scan_and_swap(self, pattern, read_offset, write_offset):
        """Scan pattern, read value at read_offset, write to write_offset"""
        if not self.is_attached:
            return {"success": False, "message": "Not attached!"}

        try:
            pattern_clean = pattern.replace("??", "?").strip()
            result = self.memory.ScanPattern(pattern_clean, True, False)

            if not result or len(result) == 0:
                return {"success": False, "message": "Pattern not found!"}

            addresses = list(result)
            swapped_count = 0

            for addr in addresses:
                try:
                    read_addr = addr + read_offset
                    read_value = self.memory.ReadInt32(read_addr)
                    write_addr = addr + write_offset
                    if self.memory.WriteInt32(write_addr, read_value):
                        swapped_count += 1
                except Exception:
                    continue

            if swapped_count > 0:
                return {
                    "success": True,
                    "message": f"Swapped {swapped_count} addresses",
                    "count": len(addresses),
                    "swapped": swapped_count,
                    "addresses": addresses
                }
            else:
                return {
                    "success": False,
                    "message": "Write operation failed!",
                    "count": len(addresses),
                    "swapped": 0
                }

        except Exception as e:
            return {"success": False, "message": str(e)}

    def read_bytes(self, addr, length):
        """Read raw bytes from process memory (via ReadInt32 chunks)"""
        if not self.is_attached or length <= 0:
            return None
        try:
            out = bytearray()
            i = 0
            while i < length:
                chunk = min(4, length - i)
                v = self.memory.ReadInt32(addr + i)
                if v is None:
                    return None
                out += struct.pack('<i', int(v))[:chunk]
                i += 4
            return bytes(out)
        except Exception:
            return None

    def write_bytes(self, addr, data):
        """Write raw bytes to process memory"""
        if not self.is_attached:
            return False
        try:
            if isinstance(data, bytes):
                data = bytearray(data)
            return bool(self.memory.WriteBytes(addr, data))
        except Exception:
            return False

    def read_int32(self, addr):
        """Read a 32-bit integer from process memory"""
        data = self.read_bytes(addr, 4)
        if data is None or len(data) < 4:
            return None
        return struct.unpack('<i', data)[0]

    def write_int32(self, addr, value):
        """Write a 32-bit integer to process memory"""
        return self.write_bytes(addr, struct.pack('<i', int(value)))

    def close(self):
        """Close connection"""
        if self.is_attached and self.memory:
            try:
                self.memory.Close()
            except Exception:
                pass
        self.is_attached = False

