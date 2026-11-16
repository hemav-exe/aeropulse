"""reporting.py - incident reports (JSON / CSV / PDF). PDF is written by hand, so no extra dependency."""
import csv
import datetime
import io
import textwrap

FIELDS = ["id", "type_label", "lat", "lon", "severity", "region", "created_at", "detection_status", "status",
          "detected_at", "first_detected_by", "detected_by", "acknowledged_at", "resolved_at", "description"]


def build_report(inc):
    return {
        "report_generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "simulation_notice": "SIMULATION - incident was randomly generated; no real emergency or real drone is involved.",
        **{k: inc.get(k) for k in FIELDS},
        "detections": inc.get("detections", []),
    }


def export_csv(incidents):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    for i in incidents:
        row = {k: i.get(k) for k in FIELDS}
        row["detected_by"] = ";".join(i.get("detected_by", []))
        w.writerow(row)
    return buf.getvalue()


def _lines(incidents):
    out = ["SIMULATION ONLY - generated incidents, no real drones or emergencies", ""]
    for i in incidents:
        out += [f"{i['id']}  {i['severity']}  {i['type_label']}",
                f"  GPS: {i['lat']:.6f}, {i['lon']:.6f}   Region: {i['region']}",
                f"  Generated: {i['created_at']}   Status: {i['status']}",
                f"  Detected: {i.get('detected_at') or '-'} by {', '.join(i.get('detected_by', [])) or '-'}",
                f"  Acknowledged: {i.get('acknowledged_at') or '-'}   Resolved: {i.get('resolved_at') or '-'}"]
        out += ["  " + l for l in textwrap.wrap("Description: " + i["description"], 100)] + [""]
    return out


def _esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def export_pdf(incidents, title="AeroPulse AI - Incident Report"):
    lines = _lines(incidents) if incidents else ["No incidents."]
    pages = [lines[i:i + 60] for i in range(0, len(lines), 60)]
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    for i, pl in enumerate(pages):
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                     f"/Contents {5 + 2 * i} 0 R >>").encode())
        s = f"BT /F1 12 Tf 40 810 Td ({_esc(title)}) Tj /F1 8 Tf 0 -18 Td 11 TL\n"
        s += "".join(f"({_esc(l)}) '\n" for l in pl) + "ET"
        data = s.encode("latin-1", "replace")
        objs.append(b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream")
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    return bytes(out)
