#!/usr/bin/env python3
"""Test for P-1: streaming/progreso/ETA in chat overlay."""
import sys
sys.path.insert(0, "E:/Agente_IA")

# Test that the OVERLAY_JS contains the required P-1 elements
with open("E:/Agente_IA/atlas_chat.py", "r", encoding="utf-8") as f:
    content = f.read()

# Check for progress bar elements
assert 'atlas-progress' in content, "Missing progress bar element"
assert 'atlas-progress-fill' in content, "Missing progress fill element"
assert 'atlas-eta' in content, "Missing ETA element"

# Check for fetch interception
assert 'window.fetch' in content, "Missing fetch interception"
assert 'showProgress' in content, "Missing showProgress function"
assert 'hideProgress' in content, "Missing hideProgress function"
assert 'updateETA' in content, "Missing updateETA function"

# Check for 10s warning
assert '10000' in content, "Missing 10s threshold check"
assert 'Sin feedback >10s' in content, "Missing 10s warning message"

# Check for ETA calculation
assert 'avgResponseTime' in content, "Missing avgResponseTime tracking"
assert 'turnCount' in content, "Missing turnCount tracking"

# Check for fetch interception on chat requests
assert '/session/' in content and '/message' in content, "Missing chat request detection"

print("All P-1 static checks passed!")
print("P-1: streaming/progreso/ETA overlay elements verified in atlas_chat.py")