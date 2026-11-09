import json
import re

with open('/home/orsted/Projects/reading-steiner/assets/lab_programs.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

prog_header_pattern = re.compile(r'^([0-9]+)\.\s+(.*)')
file_pattern = re.compile(r'^([a-zA-Z0-9_\-]+\.(html|js|java|xml|dtd|css))(\s*[-—]\s*(.*))?$')

unit_matchers = [
    (1, "1. HTML"),
    (6, "2. Bootstrap"),
    (10, "3. JavaScript"),
    (18, "4. JS Validation"),
    (19, "5. XML with DTD"),
    (21, "6. Servlets"),
    (25, "7. Weather App"),
    (26, "8. JDBC"),
    (28, "9. Node.js"),
    (31, "10. Extra: CSS")
]

unit_headers = [
    "1. HTML", "2. Bootstrap", "3. JavaScript", "4. JS Validation",
    "5. XML with DTD", "6. Servlets", "7. Weather App", "8. JDBC",
    "9. Arrow Functions", "9. Node.js", "10. Extra: CSS"
]

def get_unit_for_prog(prog_num):
    matched_unit = unit_matchers[0][1]
    for min_p, u_name in unit_matchers:
        if prog_num >= min_p:
            matched_unit = u_name
    return matched_unit

all_programs = []
i = 0
current_prog = None
current_file = None

while i < len(lines):
    line = lines[i]
    line_s = line.strip()
    
    # Check if this line is a unit header
    if any(line_s.startswith(u) for u in unit_headers) and not any(line_s.startswith(f"{x}.") for x in range(1, 33) if not line_s.startswith("1. HTML") and not line_s.startswith("2. Bootstrap")):
        current_file = None
        i += 1
        continue
        
    # Check if this line is a program header
    m = prog_header_pattern.match(line_s)
    if m:
        pnum = int(m.group(1))
        ptitle = m.group(2)
        # Verify it's a valid program 1..32 and not an instruction/unit
        if 1 <= pnum <= 32 and not any(ptitle.startswith(x) for x in ['Folder:', 'Open', 'Start', 'Browser:', 'In MySQL', 'Put', 'Compile:', 'Run:', 'Use your', 'Install', 'HTML', 'Bootstrap', 'JavaScript', 'JS Validation', 'XML with DTD', 'Servlets', 'Weather App', 'JDBC', 'Arrow Functions', 'Extra: CSS']):
            current_prog = {
                "number": pnum,
                "title": ptitle,
                "unit": get_unit_for_prog(pnum),
                "files": [],
                "instructions": []
            }
            all_programs.append(current_prog)
            current_file = None
            i += 1
            continue
            
    if current_prog:
        fm = file_pattern.match(line_s)
        if fm:
            fname = fm.group(1)
            ext = fm.group(2)
            fdesc = fm.group(4) or ""
            lang = "html"
            if ext == "js": lang = "javascript"
            elif ext == "java": lang = "java"
            elif ext == "xml" or ext == "dtd": lang = "xml"
            elif ext == "css": lang = "css"
            
            current_file = {
                "name": fname,
                "description": fdesc,
                "language": lang,
                "code_lines": []
            }
            current_prog["files"].append(current_file)
            i += 1
            continue
            
        if line_s.startswith("1. ") or line_s.startswith("Note:") or line_s.startswith("Register:") or line_s.startswith("Login:") or line_s.startswith("Steps"):
            current_prog["instructions"].append(line_s)
            current_file = None # Stop capturing code lines when a note/step appears!
            i += 1
            continue
            
        if current_file:
            # Clean leading tab if present
            clean_l = line
            if clean_l.startswith('\t'):
                clean_l = clean_l[1:]
            current_file["code_lines"].append(clean_l)
            
    i += 1

# Finalize code strings
final_list = []
for p in all_programs:
    files_clean = []
    for f in p["files"]:
        code = "".join(f["code_lines"]).strip()
        if code:
            files_clean.append({
                "name": f["name"],
                "description": f.get("description", ""),
                "language": f["language"],
                "code": code
            })
    p["files"] = files_clean
    p["instruction"] = "\n".join(p["instructions"])
    del p["instructions"]
    final_list.append(p)

with open('/home/orsted/Projects/reading-steiner/assets/lab_programs.json', 'w', encoding='utf-8') as out_f:
    json.dump(final_list, out_f, indent=2)

print(f"Regenerated {len(final_list)} programs cleanly into lab_programs.json")
