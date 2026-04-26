with open('dashboard.py', 'r') as f:
    content = f.read()

# Fix loop:
content = content.replace('''            # Aggregate Explanations
            for exp in result.get("explanations", []):
                if "Sanctuary:" in exp:
                    all_explanations.add(exp)''',
'''            # Aggregate Explanations
            for exp in result.get("explanations", []):
                all_explanations.add(exp)''')

# Fix UI bottom part:
import re
ui_regex = r'    with st.expander\("View Open Sanctuaries", expanded=True\):\n        for reason in sorted\(list\(all_explanations\)\):\n            st.write\(f"[⚪🟢] \{reason\}"\)'

new_ui = '''    with st.expander("Detailed Score Breakdown", expanded=True):
        def sort_key(x):
            if x.startswith("---"): return "0" + x
            x_lower = x.lower()
            if "crime" in x_lower or "anti-social" in x_lower: return "1" + x
            if "sanctuary" in x_lower: return "2" + x
            if "amenity" in x_lower: return "3" + x
            if "lamp" in x_lower or "infrastructure" in x_lower or "class" in x_lower: return "4" + x
            return "5" + x
            
        for reason in sorted(list(all_explanations), key=sort_key):
            if reason.startswith("---"):
                st.markdown(f"**{reason.replace('-', '').strip()}**")
            elif "Sanctuary" in reason:
                st.write(f"🟢 {reason}")
            elif "Amenity" in reason:
                st.write(f"🔵 {reason}")
            elif "crime" in reason.lower() or "anti-social" in reason.lower() or "caution" in reason.lower():
                st.write(f"🔴 {reason}")
            elif "lamp" in reason.lower() or "infrastructure" in reason.lower() or "class" in reason.lower() or "context" in reason.lower():
                st.write(f"💡 {reason}")
            else:
                st.write(f"ℹ️ {reason}")'''

content = re.sub(ui_regex, new_ui, content)

with open('dashboard.py', 'w') as f:
    f.write(content)
