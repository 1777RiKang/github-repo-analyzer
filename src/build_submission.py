"""Build submission folder — run this directly with Python, not through bash pipe."""
import os
import shutil

BASE = os.path.dirname(__file__)
NAME = "24211870223_时航_GitHub仓库数据分析系统"
SUBMIT = os.path.join(BASE, NAME)

# Clean up any garbled old versions
for d in os.listdir(BASE):
    full = os.path.join(BASE, d)
    if os.path.isdir(full) and "24211870223" in d:
        if d != NAME:
            print(f"Removing garbled dir: {d}")
            shutil.rmtree(full)

# Create fresh
os.makedirs(SUBMIT, exist_ok=True)
for sub in ["src", "data", "output"]:
    os.makedirs(os.path.join(SUBMIT, sub), exist_ok=True)

# Copy source files
for f in ["main.py", "app.py", "github_api.py", "trending.py",
           "analyze.py", "visualize.py", "pdf_export.py"]:
    shutil.copy(os.path.join(BASE, f), os.path.join(SUBMIT, "src", f))

# Copy run_web.py to submission root
runweb = os.path.join(BASE, "run_web.py")
if os.path.exists(runweb):
    shutil.copy(runweb, os.path.join(SUBMIT, "run_web.py"))

# Copy requirements, readme
for f in ["requirements.txt", "README.md"]:
    shutil.copy(os.path.join(BASE, f), os.path.join(SUBMIT, f))

# Copy data
data_dir = os.path.join(BASE, "data")
for f in os.listdir(data_dir):
    if f.endswith(".csv"):
        shutil.copy(os.path.join(data_dir, f), os.path.join(SUBMIT, "data", f))

# Copy output
output_dir = os.path.join(BASE, "output")
for f in os.listdir(output_dir):
    shutil.copy(os.path.join(output_dir, f), os.path.join(SUBMIT, "output", f))

# Generate PDF report (optional — skip if generate_report module is missing)
try:
    from generate_report import build
    build()
except ImportError:
    print("  [SKIP] generate_report module not found, skipping PDF generation")

# Copy tests
tests_dir = os.path.join(os.path.dirname(BASE), "tests")
if os.path.exists(tests_dir):
    shutil.copytree(tests_dir, os.path.join(SUBMIT, "tests"), dirs_exist_ok=True)
    print("  已复制: tests/")

# Copy .gitignore
gitignore = os.path.join(BASE, ".gitignore")
if os.path.exists(gitignore):
    shutil.copy(gitignore, os.path.join(SUBMIT, ".gitignore"))

# Copy video script
script_path = os.path.join(BASE, "视频讲解稿.md")
if os.path.exists(script_path):
    shutil.copy(script_path, os.path.join(SUBMIT, "视频讲解稿.md"))
    print(f"  已复制: 视频讲解稿.md")
else:
    print("  [SKIP] 视频讲解稿.md not found")

# Verify
print(f"\nSubmission folder: {SUBMIT}")
print(f"Real path: {os.path.realpath(SUBMIT)}")
total = 0
for root, dirs, files in os.walk(SUBMIT):
    for f in files:
        total += 1
        rel = os.path.relpath(os.path.join(root, f), SUBMIT)
        size = os.path.getsize(os.path.join(root, f))
        print(f"  {rel}  ({size:,} bytes)")
print(f"\nTotal: {total} files")
