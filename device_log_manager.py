"""
Device Flash Log Manager for Corona SmartFlux
Persistent JSON database for tracking all flashed STM32WLE5 devices.
"""

import json
import os
import shutil
from datetime import datetime, timezone


class DeviceLogManager:
    """Manages the device flash log JSON database."""

    DB_VERSION = "1.0"

    def __init__(self, db_path=None, backup_dir=None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path or os.path.join(base, "logs", "device_flash_log.json")
        self.backup_dir = backup_dir or os.path.join(base, "logs", "backups")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self._ensure_db()

    # ------------------------------------------------------------------
    # Database initialisation
    # ------------------------------------------------------------------
    def _ensure_db(self):
        """Create the database file if it does not exist."""
        if not os.path.isfile(self.db_path):
            db = self._empty_db()
            self._write_db(db)

    def _empty_db(self):
        return {
            "database_version": self.DB_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_devices": 0,
            "devices": [],
            "statistics": {
                "total_flash_events": 0,
                "success_rate_percent": 100.0,
                "firmware_versions": {},
                "production_batches": {},
                "product_classes": {},
                "operators": {},
            },
        }

    # ------------------------------------------------------------------
    # Read / Write helpers
    # ------------------------------------------------------------------
    def _read_db(self):
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_db(self, db):
        db["last_updated"] = datetime.now(timezone.utc).isoformat()
        db["total_devices"] = len(db.get("devices", []))
        tmp = self.db_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.db_path)

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------
    def create_backup(self):
        """Copy current database to backup directory with date stamp."""
        if not os.path.isfile(self.db_path):
            return None
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"device_flash_log_backup_{stamp}.json")
        shutil.copy2(self.db_path, backup_file)
        return backup_file

    # ------------------------------------------------------------------
    # Serial number generation
    # ------------------------------------------------------------------
    def next_serial_number(self, prefix="CORONA-FLUX-", digits=5):
        """Generate the next sequential serial number."""
        db = self._read_db()
        max_num = 0
        for dev in db.get("devices", []):
            serial = dev.get("device_serial", "")
            if serial.startswith(prefix):
                try:
                    num = int(serial[len(prefix):])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        next_num = max_num + 1
        return f"{prefix}{next_num:0{digits}d}"

    # ------------------------------------------------------------------
    # Device operations
    # ------------------------------------------------------------------
    def find_device_by_uid(self, uid):
        """Return device dict if UID already exists, else None."""
        db = self._read_db()
        uid_upper = uid.upper()
        for dev in db.get("devices", []):
            if dev.get("device_uid", "").upper() == uid_upper:
                return dev
        return None

    def add_device(self, device_entry):
        """Add a new device entry to the database.
        device_entry should follow the schema in the spec.
        """
        db = self._read_db()
        db["devices"].append(device_entry)
        self._update_statistics(db)
        self._write_db(db)

    def add_flash_event(self, uid, event):
        """Append a flash event to an existing device."""
        db = self._read_db()
        uid_upper = uid.upper()
        for dev in db.get("devices", []):
            if dev.get("device_uid", "").upper() == uid_upper:
                dev.setdefault("flash_events", []).append(event)
                dev.setdefault("device_metadata", {})["updated_at"] = datetime.now(timezone.utc).isoformat()
                total = dev["device_metadata"].get("total_flash_count", 0)
                dev["device_metadata"]["total_flash_count"] = total + 1
                break
        self._update_statistics(db)
        self._write_db(db)

    def update_device_field(self, uid, field_path, value):
        """Update a nested field on a device. field_path is dot-separated, e.g. 'production_data.batch_number'."""
        db = self._read_db()
        uid_upper = uid.upper()
        for dev in db.get("devices", []):
            if dev.get("device_uid", "").upper() == uid_upper:
                keys = field_path.split(".")
                obj = dev
                for k in keys[:-1]:
                    obj = obj.setdefault(k, {})
                obj[keys[-1]] = value
                break
        self._write_db(db)

    # ------------------------------------------------------------------
    # Build a full device entry
    # ------------------------------------------------------------------
    def build_device_entry(self, serial, uid, chip_id, flash_event, lorawan_config,
                           hardware_config=None, production_data=None, notes=""):
        """Construct a device entry dict ready for add_device()."""
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "device_serial": serial,
            "device_uid": uid,
            "chip_id": chip_id,
            "flash_events": [flash_event],
            "lorawan_config": lorawan_config,
            "hardware_config": hardware_config or {},
            "production_data": production_data or {},
            "device_metadata": {
                "created_at": now,
                "updated_at": now,
                "total_flash_count": 1,
                "notes": notes,
            },
        }
        return entry

    def build_flash_event(self, event_type, firmware_version, firmware_file,
                          firmware_checksum, flash_size_bytes, flash_duration_seconds,
                          programmer_id, operator, status, verification=None):
        """Build a flash event dict."""
        db = self._read_db()
        total_events = db["statistics"].get("total_flash_events", 0)
        event_id = f"FL-{total_events + 1:05d}"

        return {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "firmware_version": firmware_version,
            "firmware_file": firmware_file,
            "firmware_checksum": firmware_checksum,
            "flash_size_bytes": flash_size_bytes,
            "flash_duration_seconds": flash_duration_seconds,
            "programmer_id": programmer_id,
            "operator": operator,
            "status": status,
            "verification": verification or {
                "crc_match": True,
                "memory_test": "PASS",
                "boot_test": "PASS",
            },
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def _update_statistics(self, db):
        stats = db.setdefault("statistics", {})
        total_events = 0
        success_events = 0
        fw_versions = {}
        batches = {}
        classes = {}
        operators = {}

        for dev in db.get("devices", []):
            for ev in dev.get("flash_events", []):
                total_events += 1
                if ev.get("status") == "SUCCESS":
                    success_events += 1
                fv = ev.get("firmware_version", "unknown")
                fw_versions[fv] = fw_versions.get(fv, 0) + 1
                op = ev.get("operator", "unknown")
                operators[op] = operators.get(op, 0) + 1

            batch = dev.get("production_data", {}).get("batch_number", "")
            if batch:
                batches[batch] = batches.get(batch, 0) + 1
            pclass = dev.get("hardware_config", {}).get("product_class", "")
            if pclass:
                classes[pclass] = classes.get(pclass, 0) + 1

        stats["total_flash_events"] = total_events
        stats["success_rate_percent"] = round(
            (success_events / total_events * 100) if total_events else 100.0, 1
        )
        stats["firmware_versions"] = fw_versions
        stats["production_batches"] = batches
        stats["product_classes"] = classes
        stats["operators"] = operators

    def get_statistics(self):
        db = self._read_db()
        return db.get("statistics", {})

    def get_all_devices(self):
        db = self._read_db()
        return db.get("devices", [])

    def get_device_count(self):
        db = self._read_db()
        return len(db.get("devices", []))
