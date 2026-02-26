#!/usr/bin/env python3
"""Fix Nexus Labs region to Aurora Labs"""
import json

# Read challenges
with open("app/data/challenges.json", encoding="utf-8") as f:
    challenges = json.load(f)

# Find and fix
bad_ones = [c for c in challenges if c.get("region") == "Nexus Labs"]
print(f"Found {len(bad_ones)} challenges with 'Nexus Labs'")

for c in bad_ones:
    print(f"  - {c['id']}: {c['title']}")
    c["region"] = "Aurora Labs"  # Fix to valid region

# Save
with open("app/data/challenges.json", "w", encoding="utf-8") as f:
    json.dump(challenges, f, indent=2, ensure_ascii=False)

print(f"\n✅ Fixed {len(bad_ones)} challenges: Nexus Labs → Aurora Labs")
