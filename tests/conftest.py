"""让测试能 import skill 的脚本(把 scripts 目录加入 sys.path)。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / ".claude" / "skills" / "accel-physics-writing" / "scripts"
sys.path.insert(0, str(SCRIPTS))
