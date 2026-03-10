"""
LNS (LoRaWAN Network Server) Batch Export Module for Corona SmartFlux.

Exports device credentials in formats suitable for batch-registering devices
on TTN (The Things Network), ChirpStack, or generic LNS platforms.
"""

import csv
import json
import os
from datetime import datetime, timezone


class LNSExporter:
    """Exports device data for batch registration on LoRaWAN network servers."""

    def __init__(self, export_dir=None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.export_dir = export_dir or os.path.join(base, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # TTN (The Things Network) v3 — JSON format
    # ------------------------------------------------------------------
    def export_ttn_json(self, devices, app_id="corona-smartflux-prod",
                        frequency_plan="US_902_928_FSB_2", filename=None):
        """Export devices in TTN v3 bulk JSON format.

        Each device becomes an end_device object suitable for the
        `ttn-lw-cli end-devices create` command or the TTN Console CSV import.

        Args:
            devices: list of device dicts (from DeviceLogManager.get_all_devices)
            app_id: TTN application ID
            frequency_plan: TTN frequency plan ID
            filename: output filename (auto-generated if None)

        Returns:
            Path to the exported file.
        """
        filename = filename or f"ttn_devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.export_dir, filename)

        ttn_devices = []
        for dev in devices:
            lora = dev.get("lorawan_config", {})
            deveui = lora.get("deveui", "")
            joineui = lora.get("joineui", "")
            appkey = lora.get("appkey", "")
            serial = dev.get("device_serial", "")
            device_id = serial.lower().replace("_", "-") if serial else deveui.lower()

            ttn_dev = {
                "ids": {
                    "device_id": device_id,
                    "dev_eui": deveui,
                    "join_eui": joineui,
                },
                "name": serial,
                "description": f"Corona SmartFlux - {serial}",
                "lorawan_version": "MAC_V1_0_4",
                "lorawan_phy_version": "PHY_V1_0_3_REV_A",
                "frequency_plan_id": frequency_plan,
                "supports_join": True,
                "root_keys": {
                    "app_key": {"key": appkey},
                },
            }
            ttn_devices.append(ttn_dev)

        output = {
            "application_id": app_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "device_count": len(ttn_devices),
            "end_devices": ttn_devices,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return filepath

    # ------------------------------------------------------------------
    # TTN CSV (for Console bulk import)
    # ------------------------------------------------------------------
    def export_ttn_csv(self, devices, frequency_plan="US_902_928_FSB_2", filename=None):
        """Export devices as CSV for TTN Console bulk import.

        TTN expects columns: id, name, description, dev_eui, join_eui,
        app_key, lorawan_version, lorawan_phy_version, frequency_plan_id

        Returns:
            Path to the exported file.
        """
        filename = filename or f"ttn_devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(self.export_dir, filename)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "name", "description", "dev_eui", "join_eui",
                "app_key", "lorawan_version", "lorawan_phy_version",
                "frequency_plan_id"
            ])
            for dev in devices:
                lora = dev.get("lorawan_config", {})
                serial = dev.get("device_serial", "")
                device_id = serial.lower().replace("_", "-") if serial else lora.get("deveui", "").lower()
                writer.writerow([
                    device_id,
                    serial,
                    f"Corona SmartFlux - {serial}",
                    lora.get("deveui", ""),
                    lora.get("joineui", ""),
                    lora.get("appkey", ""),
                    "MAC_V1_0_4",
                    "PHY_V1_0_3_REV_A",
                    frequency_plan,
                ])

        return filepath

    # ------------------------------------------------------------------
    # ChirpStack JSON
    # ------------------------------------------------------------------
    def export_chirpstack_json(self, devices, device_profile_id="", filename=None):
        """Export devices for ChirpStack bulk import (JSON).

        Returns:
            Path to the exported file.
        """
        filename = filename or f"chirpstack_devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.export_dir, filename)

        cs_devices = []
        for dev in devices:
            lora = dev.get("lorawan_config", {})
            serial = dev.get("device_serial", "")
            cs_devices.append({
                "device": {
                    "devEUI": lora.get("deveui", ""),
                    "name": serial,
                    "description": f"Corona SmartFlux - {serial}",
                    "deviceProfileID": device_profile_id,
                },
                "deviceKeys": {
                    "nwkKey": lora.get("appkey", ""),
                    "appKey": lora.get("appkey", ""),
                },
            })

        output = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "device_count": len(cs_devices),
            "devices": cs_devices,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return filepath

    # ------------------------------------------------------------------
    # Production inventory CSV
    # ------------------------------------------------------------------
    def export_inventory_csv(self, devices, filename=None):
        """Export full production inventory as CSV.

        Columns: Serial, UID, DevEUI, JoinEUI, AppKey, FirmwareVersion,
        FlashDate, Operator, Batch, ProductClass, QC_Status, Notes

        Returns:
            Path to the exported file.
        """
        filename = filename or f"device_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(self.export_dir, filename)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Serial", "UID", "DevEUI", "JoinEUI", "AppKey",
                "FirmwareVersion", "FlashDate", "FlashDuration_s",
                "Operator", "Batch", "ProductClass", "QC_Status", "Notes"
            ])
            for dev in devices:
                lora = dev.get("lorawan_config", {})
                hw = dev.get("hardware_config", {})
                prod = dev.get("production_data", {})
                meta = dev.get("device_metadata", {})

                # Get latest flash event info
                events = dev.get("flash_events", [])
                latest = events[-1] if events else {}

                writer.writerow([
                    dev.get("device_serial", ""),
                    dev.get("device_uid", ""),
                    lora.get("deveui", ""),
                    lora.get("joineui", ""),
                    lora.get("appkey", ""),
                    latest.get("firmware_version", ""),
                    latest.get("timestamp", ""),
                    latest.get("flash_duration_seconds", ""),
                    latest.get("operator", ""),
                    prod.get("batch_number", ""),
                    hw.get("product_class", ""),
                    prod.get("qc_status", ""),
                    meta.get("notes", ""),
                ])

        return filepath

    # ------------------------------------------------------------------
    # Selective export
    # ------------------------------------------------------------------
    def export_devices_by_batch(self, devices, batch_number, fmt="ttn_csv"):
        """Export only devices from a specific batch.

        Args:
            devices: full device list
            batch_number: batch to filter by
            fmt: 'ttn_csv', 'ttn_json', 'chirpstack_json', 'inventory_csv'

        Returns:
            Path to the exported file.
        """
        filtered = [
            d for d in devices
            if d.get("production_data", {}).get("batch_number") == batch_number
        ]
        suffix = batch_number.lower().replace("-", "_")
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        if fmt == "ttn_csv":
            return self.export_ttn_csv(filtered, filename=f"ttn_{suffix}_{ts}.csv")
        elif fmt == "ttn_json":
            return self.export_ttn_json(filtered, filename=f"ttn_{suffix}_{ts}.json")
        elif fmt == "chirpstack_json":
            return self.export_chirpstack_json(filtered, filename=f"cs_{suffix}_{ts}.json")
        elif fmt == "inventory_csv":
            return self.export_inventory_csv(filtered, filename=f"inv_{suffix}_{ts}.csv")
        else:
            return self.export_ttn_csv(filtered, filename=f"ttn_{suffix}_{ts}.csv")

    # ------------------------------------------------------------------
    # Quick summary
    # ------------------------------------------------------------------
    @staticmethod
    def summary_text(devices):
        """Return a human-readable summary of devices for display."""
        lines = [f"Total devices: {len(devices)}", ""]
        for dev in devices:
            serial = dev.get("device_serial", "?")
            deveui = dev.get("lorawan_config", {}).get("deveui", "?")
            lines.append(f"  {serial}  DevEUI: {deveui}")
        return "\n".join(lines)
