import glob, json
for f in sorted(glob.glob("runs/*.json")):
    s = json.load(open(f, encoding="utf-8"))["summary"]
    ok = s["provider_error_cases"] == 0 and s["measured_cases"] == s["total_cases"]
    print("HỢP LỆ   " if ok else "KHÔNG HL ", s["case_accuracy"], f)
