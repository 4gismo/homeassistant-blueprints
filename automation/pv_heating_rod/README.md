
# PV Heating Rod Automation Blueprint for Home Assistant

This blueprint controls up to three heating rods based on photovoltaic (PV) surplus and the battery state of charge (SOC).

---

## 📋 About This Blueprint

This automation switches heating rods according to predefined PV surplus thresholds and the battery SOC.  
It uses a **stage-based control logic**, where each stage activates specific combinations of heating rods according to the available PV surplus.

---

### 🔥 Stage Table (Heating Rod Combination per Stage)

| Stage (kW) | Heating Rod 1 (1 kW) | Heating Rod 2 (2 kW) | Heating Rod 3 (3 kW) | Total Power |
|------------|----------------------|----------------------|----------------------|-------------|
| 0          | OFF                  | OFF                  | OFF                  | 0 kW        |
| 1          | ON                   | OFF                  | OFF                  | 1 kW        |
| 2          | OFF                  | ON                   | OFF                  | 2 kW        |
| 3          | OFF                  | OFF                  | ON                   | 3 kW        |
| 4          | ON                   | OFF                  | ON                   | 4 kW        |
| 5          | OFF                  | ON                   | ON                   | 5 kW        |
| 6          | ON                   | ON                   | ON                   | 6 kW        |

Each stage is triggered by a configurable PV surplus threshold (in watts).  
The heating rods are switched automatically according to the table above.

---

## 📂 Folder Structure

```
blueprints/
└── automation/
    └── pv_heating_rod_custom_stages/
        └── blueprint.yaml  # PV Heating Rod Automation Blueprint (Custom Stages)
```

---

## 🔧 Usage Instructions

1. Copy this folder into your Home Assistant configuration directory:
```
/config/blueprints/automation/pv_heating_rod_custom_stages/
```

2. In Home Assistant:
   - Navigate to **Settings → Automations & Scenes → Blueprints → Import Blueprint**
   - Select the blueprint from the local directory.

3. Configure the automation:
   - Select your PV surplus sensor and battery SOC sensor.
   - Set the minimum PV surplus thresholds for each stage.
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
