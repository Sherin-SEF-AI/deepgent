#!/usr/bin/env bash
# Fetch freely-published (no-login) datasheets into datasheets/ for RAG ingest,
# and write datasheets/manifest.txt with chip/version tags so ingest carries
# provenance.
#
#   ./scripts/fetch_datasheets.sh
#
# Only PUBLIC, no-login documents are scripted here (vendor datasheets that the
# maker publishes for engineers to download). Login-walled documents (NVIDIA
# Jetson module datasheet, Sony IMX sensors, the MIPI CSI-2 spec, Hailo docs)
# CANNOT be scripted and are listed under MANUAL below with where to get them.
#
# This is a STARTER set of representative common edge-AV parts. Edit DOCS to
# match your real BOM: remove parts you do not use, add your own public URLs.
# PDFs are gitignored; they are vendor-copyrighted and never committed.
set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${repo}/datasheets"
manifest="${out}/manifest.txt"
mkdir -p "${out}"

# url | outfile | chip | version | feeds-skill
DOCS=(
  "https://www.ti.com/lit/ds/symlink/ds90ub960-q1.pdf|ti_ds90ub960.pdf|DS90UB960|fpd-link-iii|camera-bringup-fpdlink"
  "https://www.ti.com/lit/ds/symlink/ds90ub954-q1.pdf|ti_ds90ub954.pdf|DS90UB954|fpd-link-iii|camera-bringup-fpdlink"
  "https://www.ti.com/lit/ds/symlink/ds90ub953-q1.pdf|ti_ds90ub953.pdf|DS90UB953|fpd-link-iii|camera-bringup-fpdlink"
  "https://www.ti.com/lit/ds/symlink/tcan1042-q1.pdf|ti_tcan1042.pdf|TCAN1042|can|can-bus"
  "https://www.ti.com/lit/ds/symlink/tcan4550-q1.pdf|ti_tcan4550.pdf|TCAN4550|can-fd|can-bus"
  "https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf|nxp_tja1051.pdf|TJA1051|can|can-bus"
  "https://www.ti.com/lit/ds/symlink/iwr6843.pdf|ti_iwr6843.pdf|IWR6843|mmwave|radar-integration"
  "https://www.ti.com/lit/ds/symlink/ina226.pdf|ti_ina226.pdf|INA226|i2c-power|low-power-design"
  "https://www.st.com/resource/en/datasheet/lsm6dsr.pdf|st_lsm6dsr.pdf|LSM6DSR|imu|imu-integration"
  "https://www.st.com/resource/en/datasheet/vl53l1x.pdf|st_vl53l1x.pdf|VL53L1X|tof|lidar-integration"
  "https://content.u-blox.com/sites/default/files/ZED-F9P-04B_DataSheet_UBX-21044850.pdf|ublox_zed_f9p.pdf|ZED-F9P|gnss-rtk|gnss-rtk"
  "https://www.st.com/resource/en/reference_manual/rm0456-stm32u5-series-armbased-32bit-mcus-stmicroelectronics.pdf|st_rm0456_stm32u5.pdf|STM32U5|reference-manual|stm32-baremetal"
  "https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf|esp32_datasheet.pdf|ESP32|datasheet|esp-idf"
  "https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf|esp32_s3_datasheet.pdf|ESP32-S3|datasheet|esp-idf"
  "https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf|rpi5_product_brief.pdf|RaspberryPi-5|board|jetson-storage-boot-media"
  "https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf|rpi_cm4.pdf|RaspberryPi-CM4|board|jetson-storage-boot-media"
)

ok=0; skip=0; fail=0
: > "${manifest}.tmp"
echo "fetching ${#DOCS[@]} public datasheets into ${out} ..."
for entry in "${DOCS[@]}"; do
  IFS='|' read -r url file chip version skill <<< "${entry}"
  dest="${out}/${file}"
  if [[ -s "${dest}" ]]; then
    echo "  skip (exists): ${file}"
    echo "${file} | ${chip} | ${version}" >> "${manifest}.tmp"
    skip=$((skip+1)); continue
  fi
  ct=$(curl -fsSL --max-time 90 -w "%{content_type}" -o "${dest}.part" "${url}" 2>/dev/null)
  if [[ $? -eq 0 && "${ct}" == application/pdf* ]]; then
    mv "${dest}.part" "${dest}"
    echo "  ok: ${file}  (${chip}, feeds ${skill})"
    echo "${file} | ${chip} | ${version}" >> "${manifest}.tmp"
    ok=$((ok+1))
  else
    rm -f "${dest}.part"
    echo "  FAIL (${ct:-no response}): ${url}"
    fail=$((fail+1))
  fi
done
mv "${manifest}.tmp" "${manifest}"

echo
echo "done: ${ok} downloaded, ${skip} already present, ${fail} failed."
echo "manifest: ${manifest}"
echo
cat <<'MANUAL'
MANUAL (login-walled or NDA; the script cannot fetch these). Download by hand,
drop the PDF in datasheets/, and add a manifest.txt line:
  - NVIDIA Jetson AGX Orin module datasheet + design guide
      developer.nvidia.com/embedded/downloads  (requires NVIDIA developer login)
  - Your camera image sensor datasheet (Sony IMX / onsemi AR0xxx)
      usually NDA via the module vendor; use the vendor's public product brief
  - MIPI CSI-2 specification  (MIPI Alliance membership required)
  - Hailo dataflow compiler / model-zoo docs  (Hailo developer login)
Your own hardware facts (no public doc exists):
  - your vehicle DBC file  -> can-bus, vehicle-interface
  - your board's device tree / pinmux for the exact carrier -> jetson-device-tree
MANUAL
