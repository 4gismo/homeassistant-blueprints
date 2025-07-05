# PV Heating Rod Automation Blueprint for Home Assistant

This repository contains a Home Assistant automation blueprint for controlling heating rods based on photovoltaic (PV) surplus power and the battery state of charge (SOC).

---

## 📋 About This Blueprint

This automation automatically switches up to **three heating rods** according to the available PV surplus and the battery SOC.  
It also uses **delays** between switching actions to avoid sudden power spikes.

**Key Features:**
- Automatically adjusts heating rod power levels based on PV surplus
- Only activates heating rods when the battery SOC exceeds a defined limit
- Supports three independent heating rods (1 kW, 2 kW, 3 kW)
- Customizable thresholds for each rod
- Includes automatic step-down and shutdown logic

---

## 📂 Folder Structure

```
blueprints/
└── automation/
    └── pv_heating_rod/
        └── blueprint.yaml  # PV Heating Rod Automation Blueprint
```

---

## 🔧 Usage Instructions

1. Copy this folder into your Home Assistant configuration directory:
```
/config/blueprints/automation/pv_heating_rod/
```

2. In Home Assistant:
   - Navigate to **Settings → Automations & Scenes → Blueprints → Import Blueprint**
   - Select the blueprint from the local directory.

3. Configure the automation:
   - Select your PV surplus sensor and battery SOC sensor.
   - Set the minimum surplus thresholds for each heating rod.
   - Set the minimum battery SOC required for operation.
   - Assign the switches controlling each heating rod.

---

## ⚡ Supported Devices

This blueprint is designed for heating rod setups using:
- Photovoltaic (PV) surplus energy
- Home batteries with SOC monitoring
- Smart switches (e.g., Shelly, Zigbee, Z-Wave, etc.)

---

## 📜 License

This blueprint is released under the MIT License.

---

## 🙌 Contribution

Feel free to contribute improvements or adaptations by submitting a pull request.
