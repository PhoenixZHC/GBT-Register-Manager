# GBT Register Manager

<div align="right">

[简体中文](README.md) | [English](README_en.md)

</div>

## Overview

This application batch-operates **GBT (Agilebot)** robot **R**, **PR**, and **P** registers: read from the controller and export to Excel, import from Excel back to the robot, and batch-create registers.

Current app version: `v1.0.0`

## Compatible SDK


Agilebot Python SDK (GBT) | v2.0.1.0


## Feature list

1. **R / P / PR registers**: Numeric **R**, pose register **PR**, and program pose **P**; **P** requires the **program name** exactly as on the controller.

| Type | Meaning | Extra input |
|------|---------|-------------|
| **R** | Numeric register | — |
| **PR** | Pose register | — |
| **P** | Program pose point | **Program name** |

3. **Batch create**: Create registers of the selected type in a contiguous range by **start ID** and **count**; **P** requires a program name and is subject to **Limitations** below.

4. **Data export**: Read from the robot by **ID range** or **All**, preview in a table, and **export to Excel**. **All** reads sequentially from register **ID 1**; when **10 consecutive** reads fail, scanning stops and all successfully read records so far are returned (suited to data that is contiguous from ID 1).

5. **Data import**: **Import Excel**, preview, then **write to the robot**; if target IDs already exist, choose **overwrite**, **skip existing**, or **cancel**. **Export template** (headers only) is supported for offline editing.

6. **Languages**: Use the header switcher for **中文**, **English**, **日本語**, **한국어**, **Русский**.

## Typical workflow

1. Open the app, enter the controller **IP**, and click **Connect**.
2. In the left sidebar, choose **Batch create**, **Data export**, or **Data import**.
3. Select **R**, **P**, or **PR** first; for **P**, enter the **program name** wherever required.
4. **Export only**: set a range or **All** → **Read from robot** → check the table → **Export to Excel** if needed.
5. **Write from sheet**: **Import Excel** (or edit after read) → **Write to robot** → resolve conflicts if prompted.
6. When finished, click **Disconnect** in the header.

## Excel layout

- Use the **first worksheet**; **row 1** = headers, **from row 2** = data.
- Prefer **Export template** in the app to avoid header mistakes.

**R** headers: `type`, `ID`, `value`  

**P** headers: `Type`, `ID`, `X`, `Y`, `Z`, `A`, `B`, `C`, `TF`, `UF`, `Coord`  

**PR** headers: `TYPE`, `ID`, `X`, `Y`, `Z`, `A`, `B`, `C`, `coord`  


## Limitations (read before production use)

- **P (program points):** If the **ID** does not already exist under that **program name**, this app **cannot create** a new program point and can only **modify existing points**; **batch create** for **P** is subject to the same restriction.

- **“Read all”:** There is no small fixed ID window. Scanning starts at **ID 1** in order; each failed read adds to a **consecutive failure** count (a successful read resets it). After **10 consecutive failures**, scanning stops and only earlier successful reads are kept. If register IDs are **not contiguous** and there are large gaps, the result may stop before the real maximum ID—use a **custom range** instead. To avoid overly long scans, the implementation also stops at an **ID ceiling of 100000**.

## Changelog

### V1.0.0 (2026-04-22)

- First release: IP connect, robot model and controller version display, **R / P / PR** read/write, batch create, Excel import/export and blank templates, write conflict handling (overwrite / skip / cancel), multi-language UI.

- **Read all:** scans from **ID 1** in order and stops after **10 consecutive** read failures, returning all successful reads so far (no longer a fixed 0–199 window).

---
